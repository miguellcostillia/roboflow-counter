import subprocess, shlex, time
import cv2
import numpy as np

def _open_in(url, transport="tcp", timeout_ms=8000):
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
    return cap

def _open_out_ffmpeg(out_url, w, h, fps):
    cmd = (
        f"ffmpeg -loglevel warning -re "
        f"-f rawvideo -pix_fmt bgr24 -s {w}x{h} -r {fps:.2f} -i - "
        f"-c:v libx264 -preset veryfast -tune zerolatency -g {int(max(1,fps))} "
        f"-f rtsp -rtsp_transport tcp {shlex.quote(out_url)}"
    )
    return subprocess.Popen(shlex.split(cmd), stdin=subprocess.PIPE)

def run_highlight_loop(url_in, url_out, log="INFO", fps_target=0.0, open_timeout_ms=8000):
    # CUDA Primitives
    mog2 = cv2.cuda.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
    gauss = cv2.cuda.createGaussianFilter(cv2.CV_8UC1, cv2.CV_8UC1, (5,5), 0)
    morph = cv2.cuda.createMorphologyFilter(cv2.MORPH_OPEN, cv2.CV_8UC1, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
    toGray = cv2.cuda.createColorConvert(cv2.COLOR_BGR2GRAY)

    cap = _open_in(url_in, timeout_ms=open_timeout_ms)
    if not cap.isOpened():
        raise RuntimeError("Unable to open input stream")

    ok, frame = cap.read()
    if not ok: raise RuntimeError("No frames from input")
    h, w = frame.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if fps_target and fps_target>0: fps = fps_target

    pipe = _open_out_ffmpeg(url_out, w, h, fps)

    ema = None
    t0 = time.time()
    gpu_bgr = cv2.cuda_GpuMat()
    gpu_gray = cv2.cuda_GpuMat()
    gpu_mask = cv2.cuda_GpuMat()
    incr = cv2.cuda_GpuMat(h, w, cv2.CV_8UC3)
    incr.upload(np.full((h,w,3), 40, dtype=np.uint8))  # additive brighten scalar

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.2)
                continue

            gpu_bgr.upload(frame)
            # gray → blur → bg subtract → clean
            toGray.apply(gpu_bgr, gpu_gray)
            gpu_gray = gauss.apply(gpu_gray)
            gpu_mask = mog2.apply(gpu_gray)
            gpu_mask = morph.apply(gpu_mask)

            # Threshold to strong motion mask
            _, gpu_bin = cv2.cuda.threshold(gpu_mask, 80, 255, cv2.THRESH_BINARY)

            # 3-ch mask
            gpu_bin3 = cv2.cuda.cvtColor(gpu_bin, cv2.COLOR_GRAY2BGR)

            # brighten only motion areas: (bgr + 40) masked + original elsewhere
            gpu_bright = cv2.cuda.add(gpu_bgr, incr)
            motion = cv2.cuda.bitwise_and(gpu_bright, gpu_bin3)
            inv = cv2.cuda.bitwise_not(gpu_bin3)
            bg = cv2.cuda.bitwise_and(gpu_bgr, inv)
            out = cv2.cuda.add(motion, bg)

            frame_out = out.download()
            pipe.stdin.write(frame_out.tobytes())

            # FPS log
            if log in ("DEBUG","INFO"):
                now = time.time()
                ema = (0.9*ema + 0.1/(now-t0)) if ema else 1.0/(now-t0)
                if int(now) % 2 == 0:
                    print(f"[motion] fps~{1.0/(now-t0):.2f} (ema={ema:.2f})")
                t0 = now
    except KeyboardInterrupt:
        pass
    finally:
        try: pipe.stdin.close()
        except: pass
        pipe.terminate()
        cap.release()
