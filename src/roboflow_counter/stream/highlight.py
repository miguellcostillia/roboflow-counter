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

    # Filter / Parameter einmalig erstellen (unabhängig von Reconnects)
    gauss = make_gauss()
    alpha = float(os.environ.get("HL_EMA_ALPHA", "0.05"))  # 0..1
    thr = int(float(os.environ.get("HL_THRESH", "12")))    # 0..255

    # statische Hintergrundabdunklung (0..1)
    darken = float(os.environ.get("HL_DARKEN", "0.0"))
    darken = max(0.0, min(0.95, darken))  # clamp

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morph = cv2.cuda.createMorphologyFilter(cv2.MORPH_OPEN, cv2.CV_8UC1, kernel)

    # wie lange ohne neuen "guten" Frame, bevor wir die Verbindung neu aufbauen
    MAX_NO_GOOD_SEC = 10.0

    while True:  # Reconnect-Schleife
        print(f"[INFO] Highlight: (Re)connect to {url_in}")
        cap = cv2.VideoCapture(url_in, cv2.CAP_FFMPEG)
        if open_timeout_ms > 0:
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(open_timeout_ms))

        if not cap.isOpened():
            print(f"[WARN] Highlight: cannot open input {url_in}, retry in 2s")
            time.sleep(2.0)
            continue

        # ersten gültigen Frame holen
        frame0 = None
        start_wait = time.time()
        for _ in range(60):
            ok, f = cap.read()
            if ok and f is not None and f.size > 0:
                frame0 = f
                break
            time.sleep(0.05)

        if frame0 is None:
            print("[WARN] Highlight: no first frame, closing and retrying…")
            cap.release()
            time.sleep(2.0)
            continue

        h, w = frame0.shape[:2]
        fps_in = cap.get(cv2.CAP_PROP_FPS) or 0.0
        fps = fps_target if fps_target > 0 else (fps_in if fps_in > 0 else 8.0)
        print(f"[INFO] Input {w}x{h} @ {fps:.2f}")

        # GPU-Init für diese Verbindung
        gpu_bgr = cv2.cuda_GpuMat()
        gpu_bgr.upload(frame0)
        gpu_gray = bgr_to_gray_cuda(gpu_bgr)

        gpu_blur = cv2.cuda_GpuMat()
        gpu_blur.create(h, w, cv2.CV_8UC1)
        gauss.apply(gpu_gray, gpu_blur)

        d_ema = cv2.cuda_GpuMat()
        d_ema.create(h, w, cv2.CV_8UC1)
        gpu_blur.copyTo(d_ema)

        pipe = None
        t_prev = time.time()
        ema = None

        # Tracking des letzten "guten" Frames
        last_good_frame = frame0.copy()
        last_good_ts = time.time()

        try:
            while True:
                ok, frame = cap.read()
                now = time.time()

                if ok and frame is not None and frame.size > 0:
                    # neuer gültiger Frame von der Kamera
                    last_good_frame = frame
                    last_good_ts = now
                    frame_to_process = frame
                else:
                    # kaputter Frame -> letztes gutes Bild wiederverwenden
                    if last_good_frame is None:
                        # wir haben überhaupt noch keinen gültigen Frame – kurz warten
                        time.sleep(0.05)
                        continue

                    # Wenn zu lange kein guter Frame: Reconnect erzwingen
                    if now - last_good_ts > MAX_NO_GOOD_SEC:
                        print(f"[WARN] Highlight: no good frame for {MAX_NO_GOOD_SEC}s – reconnecting…")
                        raise RuntimeError("no good frames, reconnect")

                    # Wiederhole einfach das letzte gute Bild
                    frame_to_process = last_good_frame

                # ---- ab hier mit frame_to_process weiterarbeiten ----
                gpu_bgr.upload(frame_to_process)
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

                # 3-Kanal Maske (0/255) für die bewegten Bereiche
                gpu_mask3 = gray_to_bgr_safe(d_mask_clean)
                if gpu_mask3.size() != gpu_bgr.size():
                    gpu_mask3 = resize_like(gpu_mask3, gpu_bgr)

                # 1) Bewegte Bereiche highlighten (altes Verhalten)
                gain = float(os.environ.get("HL_GAIN", "0.70"))
                highlighted = cv2.cuda.addWeighted(gpu_bgr, 1.0, gpu_mask3, gain, 0.0)

                # 2) Statische Hintergrund-Abdunklung nur dort, wo KEINE Bewegung ist
                if darken > 0.0:
                    inv_mask = cv2.cuda.bitwise_not(d_mask_clean)   # 255 für Hintergrund
                    inv_mask3 = gray_to_bgr_safe(inv_mask)

                    # Hintergrund-Version: Original dunkler skaliert
                    bg_dark = cv2.cuda.addWeighted(gpu_bgr, (1.0 - darken), gpu_bgr, 0.0, 0.0)

                    # Ausmaskieren und zusammensetzen
                    bg_part = cv2.cuda.bitwise_and(bg_dark,     inv_mask3)  # nur Hintergrund
                    fg_part = cv2.cuda.bitwise_and(highlighted, gpu_mask3)  # nur Bewegung
                    gpu_out = cv2.cuda.add(bg_part, fg_part)
                else:
                    gpu_out = highlighted

                # FFmpeg starten wenn nötig
                if pipe is None:
                    pipe = start_ffmpeg_writer(
                        w, h, fps, url_out,
                        loglevel=("info" if log == "DEBUG" else "warning")
                    )
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

                # FPS-EMA
                t = time.time()
                dt = t - t_prev
                t_prev = t
                if dt > 0:
                    inst = 1.0 / dt
                    ema = inst if ema is None else (0.9 * ema + 0.1 * inst)
                if log == "DEBUG" and ema:
                    print(f"[DEBUG] FPS ~ {ema:.2f}")

        except KeyboardInterrupt:
            print("[INFO] Highlight: stop requested (KeyboardInterrupt)")
            # komplett raus – kein weiterer Reconnect
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
            break
        except Exception as e:
            # Irgendein Fehler (z.B. 10s keine Frames, ffmpeg kaputt) -> Reconnect
            print(f"[WARN] Highlight: loop error: {e} – reconnecting in 2s …")
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
            time.sleep(2.0)
            # geht zurück an den Anfang der while True (Reconnect-Schleife)

    # Ende run_highlight_loop


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
