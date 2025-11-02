from __future__ import annotations
import time
from typing import Optional

def run_rtsp_loop(url: str,
                  fps_target: Optional[float] = None,
                  open_timeout_ms: int = 5000,
                  transport: str = "tcp") -> int:
    """
    Minimal RTSP reader using OpenCV (if available).
    - Tries to open the stream and reads frames in a loop.
    - Prints periodic FPS estimate.
    - Reconnects on failure with backoff.
    Returns process exit code (0 = ok).
    """
    try:
        import cv2  # type: ignore
    except Exception as e:
        print(f"[rtsp] OpenCV not available: {e}")
        return 2

    # Optional: hint OpenCV FFMPEG to use TCP
    try:
        import os
        if transport:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}"
    except Exception:
        pass

    def open_cap() -> "cv2.VideoCapture":
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        # Some builds support CAP_PROP_OPEN_TIMEOUT_MSEC, many don't—ignore failures.
        try:
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(open_timeout_ms))
        except Exception:
            pass
        return cap

    cap = open_cap()
    backoff = 1.0
    last_print = time.time()
    frames = 0
    start = time.time()

    def throttle(tgt_fps: Optional[float], t_frame_start: float):
        if not tgt_fps or tgt_fps <= 0:
            return
        min_dt = 1.0 / float(tgt_fps)
        dt = time.time() - t_frame_start
        if dt < min_dt:
            time.sleep(min_dt - dt)

    while True:
        if not cap.isOpened():
            print(f"[rtsp] not opened, retry in {backoff:.1f}s …")
            time.sleep(backoff)
            cap.release()
            cap = open_cap()
            backoff = min(backoff * 2, 10)
            continue

        t0 = time.time()
        ok, _ = cap.read()
        if not ok:
            print(f"[rtsp] read failed, reconnecting …")
            cap.release()
            time.sleep(backoff)
            cap = open_cap()
            backoff = min(backoff * 2, 10)
            continue

        # got a frame
        frames += 1
        backoff = 1.0
        throttle(fps_target, t0)

        now = time.time()
        if now - last_print >= 2.0:
            elapsed = now - start
            fps = frames / elapsed if elapsed > 0 else 0.0
            print(f"[rtsp] {frames} frames, ~{fps:.2f} fps (target={fps_target or '∞'})")
            last_print = now
    # unreachable in normal loop; KeyboardInterrupt will exit caller
