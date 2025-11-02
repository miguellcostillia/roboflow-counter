from __future__ import annotations
import time, math, os, signal
from typing import Optional, Dict, Any
from ..util.logging import setup_logger

_SHUTDOWN = False

def _sig_handler(signum, frame):
    global _SHUTDOWN
    _SHUTDOWN = True

# register soft shutdown
try:
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)
except Exception:
    pass

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
    RTSP reader with health logging:
    - Open/read with reconnect backoff (1s..10s)
    - Smoothed FPS (EMA)
    - Drop-rate and reconnect counters
    - Graceful shutdown on SIGINT/SIGTERM
    Returns exit code (0=ok).
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
    start = time.time()
    frames_ok = 0
    frames_fail = 0
    reconnects = 0
    ema_fps: Optional[float] = None
    alpha = 0.2

    def throttle(tgt_fps: Optional[float], t0: float):
        if not tgt_fps or tgt_fps <= 0: return
        min_dt = 1.0 / float(tgt_fps)
        dt = time.time() - t0
        if dt < min_dt:
            time.sleep(min_dt - dt)

    def log_health(event: str = "tick"):
        nonlocal ema_fps
        now = time.time()
        if now - last_log >= 2.0 or event != "tick":
            elapsed = max(now - start, 1e-6)
            inst_fps = frames_ok / elapsed
            ema_fps = inst_fps if ema_fps is None else (alpha * inst_fps + (1 - alpha) * ema_fps)
            total = frames_ok + frames_fail
            drop_pct = (frames_fail / total * 100.0) if total > 0 else 0.0
            log.info("event=%s ok=%d fail=%d drops=%.2f%% reconnects=%d fps~%.2f (ema=%.2f target=%s)",
                     event, frames_ok, frames_fail, drop_pct, reconnects, inst_fps, (ema_fps or 0.0),
                     (fps_target if fps_target else "∞"))
            return True
        return False

    try:
        while not _SHUTDOWN:
            if not cap.isOpened():
                log.warning("not opened, retry in %.1fs …", backoff)
                time.sleep(backoff)
                cap.release()
                cap = open_cap()
                reconnects += 1
                backoff = min(backoff * 2, 10)
                log_health(event="reopen")
                continue

            t0 = time.time()
            ok, _ = cap.read()
            if not ok:
                frames_fail += 1
                log.error("read failed (network jitter/timeout?). Reconnecting in %.1fs …", backoff)
                cap.release()
                time.sleep(backoff)
                cap = open_cap()
                reconnects += 1
                backoff = min(backoff * 2, 10)
                log_health(event="reconnect")
                continue

            # got a frame
            frames_ok += 1
            backoff = 1.0
            throttle(fps_target, t0)
            if log_health():
                last_log = time.time()
    except KeyboardInterrupt:
        log.info("interrupted by user")
    finally:
        try:
            cap.release()
        except Exception:
            pass
        log_health(event="shutdown")
    return 0
