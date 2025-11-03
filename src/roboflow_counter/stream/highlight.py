#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU Motion-Highlight (OpenCV CUDA) – stabile Gauss/EMA-Pipeline
- Graustufen: CUDA-Fallback ohne cv2.cuda.cvtColor (dein Build buggt dort)
- Gauss: k ∈ {3..31}, sigma auto, kein borderType
- Motion: GPU-EMA (8-bit), keine cudabgsegm-Abhängigkeit
- Encoder: h264_nvenc (Default) oder libx264 via HL_ENCODER
"""

from __future__ import annotations
import os
import time
import subprocess
import argparse
import cv2
import numpy as np


# ---------------- Utilities ----------------

def dbg_mat(name, m):
    try:
        if m is None or m.empty():
            return f"{name}: EMPTY"
        w, h = m.size()
        return f"{name}: {w}x{h} type={m.type()}"
    except Exception:
        return f"{name}: ?"


def set_cuda_defaults():
    os.environ.setdefault("CUDA_LAUNCH_BLOCKING", "0")


def _ffmpeg_cmd(w: int, h: int, fps: float, url: str, loglevel: str) -> list[str]:
    """Baue FFmpeg-Command; NVENC (Default) oder libx264 via HL_ENCODER."""
    fps = max(1.0, fps)
    gop = max(1, int(round(fps * 2)))  # ~2s Keyframe-Intervall

    encoder = os.environ.get("HL_ENCODER", "h264_nvenc").lower().strip()
    base = [
        "ffmpeg", "-loglevel", loglevel, "-re",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}",
        "-r", f"{fps:.3f}",
        "-i", "pipe:0",
        # farbraum festnageln für Kompatibilität mit VLC/RTSP
        "-vf", "format=yuv420p",
    ]

    if encoder == "libx264":
        # CPU Encoder (Fallback)
        base += [
            "-c:v", "libx264",
            "-profile:v", "baseline", "-level:v", "4.0",
            "-g", str(gop), "-bf", "0",
            "-x264-params", f"scenecut=0:ref=1:keyint={gop}:min-keyint={gop}:bframes=0",
            "-tune", "zerolatency", "-preset", "veryfast",
        ]
    else:
        # NVIDIA NVENC (Default)
        base += [
            "-c:v", "h264_nvenc",
            "-preset", "p4",              # p1 slow .. p7 fastest
            "-tune", "ll",                # low-latency
            "-rc", "cbr",
            "-b:v", "6M",
            "-maxrate", "6M",
            "-bufsize", "3M",
            "-g", str(gop),
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            # keine B-Frames, keine Open-GOPs → stabiler für RTSP
            "-no-scenecut", "1",
            "-bf", "0",
        ]

    base += ["-f", "rtsp", "-rtsp_transport", "tcp", url]
    return base


def start_ffmpeg_writer(w: int, h: int, fps: float, url: str, loglevel: str = "warning") -> subprocess.Popen:
    cmd = _ffmpeg_cmd(w, h, fps, url, loglevel)
    print("[FFMPEG]", " ".join(cmd))
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


# --------------- CUDA helpers ----------------

def bgr_to_gray_cuda(d_bgr):
    """Robuster BGR->GRAY ohne cv2.cuda.cvtColor (dein Build zickt dort)."""
    b, g, r = cv2.cuda.split(d_bgr)
    tmp = cv2.cuda.addWeighted(b, 0.114, g, 0.587, 0.0)
    gray = cv2.cuda.addWeighted(tmp, 1.0, r, 0.299, 0.0)
    return gray  # 8UC1


def gray_to_bgr_safe(d_gray):
    """1ch->3ch: versuche CUDA-merge, sonst CPU-merge + Upload."""
    if d_gray.empty():
        raise RuntimeError("gray_to_bgr_safe: empty input")

    try:
        merged = cv2.cuda.merge([d_gray, d_gray, d_gray])
        if hasattr(merged, "download"):
            return merged
    except Exception:
        pass

    cpu = d_gray.download()
    cpu3 = cv2.merge([cpu, cpu, cpu])
    out = cv2.cuda_GpuMat()
    out.upload(cpu3)
    return out


def resize_like(src, ref):
    if src.size() == ref.size():
        return src
    w, h = ref.size()
    out = cv2.cuda_GpuMat()
    cv2.cuda.resize(src, (w, h), dst=out)
    return out


def make_gauss():
    k = int(os.environ.get("HL_GAUSS", "7"))
    k = max(3, min(31, k))
    k = k if (k % 2) else k + 1
    sigma = float(os.environ.get("HL_SIGMA", "0"))
    if sigma <= 0:
        sigma = max(0.1, (k - 1) / 6.0)
    f = cv2.cuda.createGaussianFilter(cv2.CV_8UC1, cv2.CV_8UC1, (k, k), sigma)
    print(f"[INFO] Gaussian k={k} sigma={sigma}")
    return f


# ---------------- Main ----------------

def run_highlight_loop(url_in, url_out, log="INFO", fps_target=0.0, open_timeout_ms=8000):

    set_cuda_defaults()

    if cv2.cuda.getCudaEnabledDeviceCount() <= 0:
        raise RuntimeError("CUDA GPU not available")

    cv2.cuda.setDevice(0)
    stream = cv2.cuda.Stream()

    cap = cv2.VideoCapture(url_in, cv2.CAP_FFMPEG)
    if open_timeout_ms > 0:
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(open_timeout_ms))

    if not cap.isOpened():
        raise RuntimeError(f"cannot open input {url_in}")

    # ersten gültigen Frame holen
    frame0 = None
    for _ in range(60):
        ok, f = cap.read()
        if ok and f is not None and f.size > 0:
            frame0 = f
            break
        time.sleep(0.05)
    if frame0 is None:
        raise RuntimeError("no first frame")

    h, w = frame0.shape[:2]
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 0.0
    fps = fps_target if fps_target > 0 else (fps_in if fps_in > 0 else 8.0)
    print(f"[INFO] Input {w}x{h} @ {fps:.2f}")

    gauss = make_gauss()
    alpha = float(os.environ.get("HL_EMA_ALPHA", "0.05"))  # 0..1
    thr = int(float(os.environ.get("HL_THRESH", "12")))    # 0..255

    # Init
    gpu_bgr = cv2.cuda_GpuMat()
    gpu_bgr.upload(frame0)
    gpu_gray = bgr_to_gray_cuda(gpu_bgr)

    gpu_blur = cv2.cuda_GpuMat()
    gpu_blur.create(h, w, cv2.CV_8UC1)
    gauss.apply(gpu_gray, gpu_blur)

    d_ema = cv2.cuda_GpuMat()
    d_ema.create(h, w, cv2.CV_8UC1)
    gpu_blur.copyTo(d_ema)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morph = cv2.cuda.createMorphologyFilter(cv2.MORPH_OPEN, cv2.CV_8UC1, kernel)

    pipe = None
    t_prev = time.time()
    ema = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                time.sleep(0.002)
                continue

            # Upload + Gray + Gauss
            gpu_bgr.upload(frame)
            gpu_gray = bgr_to_gray_cuda(gpu_bgr)
            gauss.apply(gpu_gray, gpu_blur)

            # EMA motion
            d_diff = cv2.cuda.absdiff(gpu_blur, d_ema)
            tmp1 = cv2.cuda.addWeighted(d_ema, 1 - alpha, d_ema, 0, 0)
            tmp2 = cv2.cuda.addWeighted(gpu_blur, alpha, gpu_blur, 0, 0)
            d_ema = cv2.cuda.add(tmp1, tmp2)

            gpu_mask = cv2.cuda_GpuMat()
            gpu_mask.create(h, w, cv2.CV_8UC1)
            cv2.cuda.threshold(d_diff, thr, 255, cv2.THRESH_BINARY, dst=gpu_mask)

            d_mask_clean = cv2.cuda_GpuMat()
            d_mask_clean.create(h, w, cv2.CV_8UC1)
            morph.apply(gpu_mask, d_mask_clean)

            gpu_mask3 = gray_to_bgr_safe(d_mask_clean)
            if gpu_mask3.size() != gpu_bgr.size():
                gpu_mask3 = resize_like(gpu_mask3, gpu_bgr)

            gain = float(os.environ.get("HL_GAIN", "0.70"))
            gpu_out = cv2.cuda.addWeighted(gpu_bgr, 1.0, gpu_mask3, gain, 0.0)

            # FFmpeg starten wenn nötig
            if pipe is None:
                pipe = start_ffmpeg_writer(w, h, fps, url_out, loglevel=("info" if log == "DEBUG" else "warning"))
                print(f"[INFO] Output -> {url_out}")

            # --- Frame aus GPU holen + sicher in die Pipe schreiben ---
            tmp = gpu_out.download()

            # Sanity-Check Form/Dtype
            if tmp.dtype != np.uint8 or tmp.ndim != 3 or tmp.shape[2] != 3:
                raise RuntimeError(f"bad frame shape/dtype: {tmp.shape} {tmp.dtype}")

            # Garantiert contiguous (verhindert grüne/versetzte Zeilen)
            out_cpu = np.ascontiguousarray(tmp)

            # Optional Größenprüfung (bgr24)
            expected = w * h * 3
            if out_cpu.nbytes != expected:
                raise RuntimeError(f"bad byte size: {out_cpu.nbytes} != {expected}")

            try:
                pipe.stdin.write(out_cpu.tobytes())
            except (BrokenPipeError, AttributeError):
                raise RuntimeError("ffmpeg pipe closed")

            # FPS
            t = time.time()
            dt = t - t_prev
            t_prev = t
            if dt > 0:
                inst = 1.0 / dt
                ema = inst if ema is None else (0.9 * ema + 0.1 * inst)
            if log == "DEBUG" and ema:
                print(f"[DEBUG] FPS ~ {ema:.2f}")

    except KeyboardInterrupt:
        print("[INFO] stop")
    finally:
        if pipe:
            try:
                pipe.stdin.flush()
            except Exception:
                pass
            try:
                pipe.stdin.close()
            except Exception:
                pass
            try:
                pipe.terminate()
            except Exception:
                pass
        cap.release()


# ------------- direct mode fallback --------------

def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="i")
    p.add_argument("--out", dest="o")
    p.add_argument("--fps", type=float, default=0.0)
    args = p.parse_args()
    if not args.i or not args.o:
        raise ValueError("need --in and --out")
    run_highlight_loop(args.i, args.o, fps_target=args.fps)


if __name__ == "__main__":
    _cli()
