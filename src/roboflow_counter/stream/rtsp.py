from __future__ import annotations
import time, math, os
from typing import Optional
from ..util.logging import setup_logger

def _set_transport_env(transport: str):
    if transport:
        try:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}"
        except Exception:
            pass

def run_rtsp_loop(url: str,
                  fps_target: Optional[float] = None,
                  open_timeout_ms: int = 5000,
                  transport: str = "tcp",
                  log_level: str = "INFO") -> int:
    """
    Minimal RTSP reader with logging:
    - Open/read with reconnect backoff
    - Smoothed FPS
    - Reconnect reason reporting
    """
    log = setup_logger("rtsp", log_level)

    try:
        import cv2  # type: ignore
    except Exception as e:
        print(f"[rtsp] OpenCV not available: {e}")
        return 2

    _set_transport_env(transport)

    def open_cap():
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        try:
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(open_timeout_ms))
        except Exception:
            pass
        return cap

    cap = open_cap()
    backoff = 1.0
    last_log = time.time()
    frames = 0
    start = time.time()
    # FPS smoothing with EMA
    ema_fps: Optional[float] = None
    alpha = 0.2

    def throttle(tgt_fps: Optional[float], t0: float):
        if not tgt_fps or tgt_fps <= 0: return
        min_dt = 1.0 / float(tgt_fps)
        dt = time.time() - t0
        if dt < min_dt:
            time.sleep(min_dt - dt)

    def log_rate():
        nonlocal ema_fps
        now = time.time()
        if now - last_log >= 2.0:
            elapsed = now - start
            inst = frames / elapsed if elapsed > 0 else 0.0
            ema_fps = inst if ema_fps is None else (alpha * inst + (1 - alpha) * ema_fps)
            log.info("frames=%d, fps~%.2f (ema=%.2f, target=%s)",
                     frames, inst, (ema_fps or 0.0), (fps_target if fps_target else "∞"))
            return True
        return False

    while True:
        if not cap.isOpened():
            log.warning("not opened, retry in %.1fs …", backoff)
            time.sleep(backoff)
            cap.release()
            cap = open_cap()
            backoff = min(backoff * 2, 10)
            continue

        t0 = time.time()
        ok, _ = cap.read()
        if not ok:
            # Try to detect reason: we can't access low-level ffmpeg here, so inform generic
            log.error("read failed (network jitter/timeout?). Reconnecting in %.1fs …", backoff)
            cap.release()
            time.sleep(backoff)
            cap = open_cap()
            backoff = min(backoff * 2, 10)
            continue

        frames += 1
        backoff = 1.0
        throttle(fps_target, t0)
        if log_rate():
            last_log = time.time()
    # unreachable; Ctrl+C handled by caller
