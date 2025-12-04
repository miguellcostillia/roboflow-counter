#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, time, json, statistics, subprocess, signal
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Any
from collections import deque
from datetime import datetime, timezone  # NEU für Status/Overlay

# Pfad, wo der Tracker seine aktuelle Track-Anzahl für die Ohaus-Bridge ablegt
TRACKER_STATUS_JSON = os.getenv(
    "TRACKER_STATUS_JSON",
    os.path.expanduser(
        "~/projects/roboflow-counter/export/tracker/status.json"
    )
)

# Pfad zum Ohaus-Overlay (wird von der Ohaus-Bridge geschrieben)
OHAUS_OVERLAY_JSON = os.getenv(
    "OHAUS_OVERLAY_JSON",
    os.path.expanduser(
        "~/projects/roboflow-counter/export/ohaus_overlay.json"
    )
)


def write_tracker_status(tracks: int) -> None:
    """Schreibt aktuelle Track-Anzahl in eine JSON-Datei für ohaus_print_bridge."""
    try:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tracks": int(tracks),
        }
        dir_name = os.path.dirname(TRACKER_STATUS_JSON)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        tmp = TRACKER_STATUS_JSON + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, TRACKER_STATUS_JSON)
    except Exception as e:
        # Tracker darf wegen JSON-Speicherfehlern nicht sterben
        print(f"[WARN] Konnte TRACKER_STATUS_JSON nicht schreiben: {e}", file=sys.stderr)


def load_ohaus_overlay(path: Optional[str]) -> Optional[dict]:
    """Liest das Ohaus-Overlay-JSON und gibt es zurück, wenn es noch gültig ist."""
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    ts_str = data.get("timestamp")
    dur = float(data.get("duration_sec", 0) or 0)
    if not ts_str or dur <= 0:
        return None

    try:
        ts = datetime.fromisoformat(ts_str)
    except Exception:
        return None

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age = (now - ts).total_seconds()
    if age > dur:
        # Overlay ist abgelaufen
        return None

    return data


# --------- OpenCV / FFmpeg: RTSP Stabilität + Log-Lärm reduzieren ---------
# WICHTIG: diese Umgebungsvariablen MÜSSEN gesetzt sein,
# bevor cv2 importiert wird, sonst greifen sie nicht.

# Nur Video, TCP, mit Timeout (~8s)
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|allowed_media_types;video|stimeout;8000000"
)

# FFmpeg/Libav nur Fehler loggen (AV_LOG_ERROR = 24)
os.environ.setdefault("AV_LOG_FORCE_LEVEL", "24")

# OpenCV intern leiser
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import numpy as np
import requests

# OpenCV C++ Logging zusätzlich runterdrehen (falls verfügbar)
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass


# =================== Rolling Window (zeitbasiert) ===================
class RollingWindow:
    """Zeitbasiertes Fenster mit Median/Mean – unabhängig von FPS."""
    def __init__(self, window_sec: float):
        self.window_sec = float(window_sec)
        self.buf: deque[tuple[float, float]] = deque()

    def add(self, value: float, ts: Optional[float] = None) -> None:
        if ts is None:
            ts = time.time()
        self.buf.append((ts, value))
        self._trim(ts)

    def _trim(self, now: float) -> None:
        cutoff = now - self.window_sec
        while self.buf and self.buf[0][0] < cutoff:
            self.buf.popleft()

    def median(self) -> float:
        if not self.buf:
            return 0.0
        vals = [v for _, v in self.buf]
        return float(statistics.median(vals))

    def mean(self) -> float:
        if not self.buf:
            return 0.0
        vals = [v for _, v in self.buf]
        return float(sum(vals) / len(vals))

    def count(self) -> int:
        return len(self.buf)


# ================= Inference-Anbindung (via inference.py) ================
class Predictor:
    def __init__(self, infer_host: str, model_id: str, api_key: str, cfg: Dict):
        self.infer_host = infer_host
        self.model_id = model_id
        self.api_key = api_key or ""
        self.mode = "http"
        self._client: Any = None
        self._predict_func = None
        self.cache_dir = (
            (cfg.get("inference") or {}).get("cache_dir")
            or os.environ.get("INFER_CACHE_DIR")
            or os.path.expanduser("~/.cache/roboflow-counter")
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        try:
            from . import inference as rfi
            if hasattr(rfi, "get_client"):
                self._client = rfi.get_client(cfg)
                self.mode = "module"
            elif hasattr(rfi, "InferenceClient"):
                self._client = rfi.InferenceClient(
                    model_id=self.model_id,
                    api_key=self.api_key,
                    host=self.infer_host,
                    cache_dir=self.cache_dir
                )
                self.mode = "module"
            elif hasattr(rfi, "predict_bgr"):
                self._predict_func = lambda img: rfi.predict_bgr(
                    img, model_id=self.model_id, api_key=self.api_key, host=self.infer_host
                )
                self.mode = "module-func"
            elif hasattr(rfi, "predict"):
                self._predict_func = lambda img: rfi.predict(
                    img, model_id=self.model_id, api_key=self.api_key, host=self.infer_host
                )
                self.mode = "module-func"
        except Exception:
            self.mode = "http"
        if self.mode.startswith("http"):
            self.session = requests.Session()
            if self.api_key:
                self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def predict(self, bgr: np.ndarray, jpeg_quality: int = 85, timeout: float = 10.0) -> Dict:
        if self.mode == "module" and self._client is not None:
            for name in ("predict", "infer", "infer_bgr", "predict_bgr"):
                fn = getattr(self._client, name, None)
                if callable(fn):
                    return fn(bgr)
            ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
            if ok and hasattr(self._client, "infer_bytes"):
                return self._client.infer_bytes(buf.tobytes())
            return {"predictions": []}
        if self.mode == "module-func" and self._predict_func:
            try:
                return self._predict_func(bgr)
            except Exception:
                return {"predictions": []}
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
        if not ok:
            return {"predictions": []}
        files = {"file": ("frame.jpg", buf.tobytes(), "image/jpeg")}
        url1 = f"{self.infer_host.rstrip('/')}/{self.model_id}"
        try:
            r = self.session.post(url1, files=files, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        try:
            url2 = f"{self.infer_host.rstrip('/')}/infer/object_detection"
            data = {"model_id": self.model_id}
            r2 = self.session.post(url2, files=files, data=data, timeout=timeout)
            if r2.status_code == 200:
                return r2.json()
        except Exception:
            pass
        return {"predictions": []}


# ===================== IoU-Tracker =====================
def _iou(a: Tuple[int,int,int,int], b: Tuple[int,int,int,int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1 + 1), max(0, iy2 - iy1 + 1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax2 - ax1 + 1) * (ay2 - ay1 + 1)
    area_b = (bx2 - bx1 + 1) * (ay2 - ay1 + 1)
    return inter / float(area_a + area_b - inter)


@dataclass
class Track:
    tid: int
    box: Tuple[int,int,int,int]
    hits: int = 0
    age: int = 0
    missed: int = 0
    confirmed: bool = False


class IoUTracker:
    def __init__(self, iou_thresh: float, max_age: int, min_hits: int):
        self.iou_thresh = float(iou_thresh)
        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self._next_id = 1
        self.tracks: List[Track] = []
        self.confirmed_ids: set[int] = set()

    def update(self, boxes: List[Tuple[int,int,int,int]]) -> List[Track]:
        for t in self.tracks:
            t.age += 1
            t.missed += 1
        for b in boxes:
            best_iou, best_idx = 0.0, -1
            for i, t in enumerate(self.tracks):
                iou = _iou(t.box, b)
                if iou > best_iou:
                    best_iou, best_idx = iou, i
            if best_iou >= self.iou_thresh and best_idx >= 0:
                t = self.tracks[best_idx]
                t.box = b
                t.hits += 1
                t.missed = 0
                if not t.confirmed and t.hits >= self.min_hits:
                    t.confirmed = True
                    self.confirmed_ids.add(t.tid)
            else:
                t = Track(tid=self._next_id, box=b, hits=1, age=1, missed=0, confirmed=(self.min_hits <= 1))
                if t.confirmed:
                    self.confirmed_ids.add(t.tid)
                self._next_id += 1
                self.tracks.append(t)
        self.tracks = [t for t in self.tracks if t.missed <= self.max_age]
        return list(self.tracks)


# ================== FFmpeg (NVENC wie highlight.py) ==================
def _ffmpeg_cmd(w: int, h: int, fps: float, url: str) -> List[str]:
    fps = max(1.0, fps)
    gop_sec = float(os.environ.get("HL_GOP_SECONDS", 2))
    gop = max(1, int(round(fps * gop_sec)))
    enc = os.environ.get("HL_ENCODER", "h264_nvenc").strip().lower()
    bitrate = os.environ.get("HL_BITRATE", "6M")
    maxrate = os.environ.get("HL_MAXRATE", bitrate)
    bufsize = os.environ.get("HL_BUFSIZE", "3M")
    preset  = os.environ.get("HL_PRESET",  "p4")
    tune    = os.environ.get("HL_TUNE",    "ll")
    # Default-Loglevel von "warning" auf "error" reduziert, um Spam zu vermeiden
    loglevel = os.environ.get("HL_FFMPEG_LOGLEVEL", "error")

    base = [
        "ffmpeg", "-loglevel", loglevel, "-re",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}", "-r", f"{fps:.3f}",
        "-i", "pipe:0", "-vf", "format=yuv420p",
    ]
    if enc == "libx264":
        base += [
            "-c:v", "libx264",
            "-profile:v", "baseline", "-level:v", "4.0",
            "-g", str(gop), "-bf", "0",
            "-x264-params", f"scenecut=0:ref=1:keyint={gop}:min-keyint={gop}:bframes=0",
            "-tune", "zerolatency", "-preset", "veryfast",
        ]
    else:
        base += [
            "-c:v", "h264_nvenc",
            "-preset", preset,
            "-tune", tune,
            "-rc", "cbr",
            "-b:v", bitrate,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-g", str(gop),
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-no-scenecut", "1",
            "-bf", "0",
        ]
    base += ["-f", "rtsp", "-rtsp_transport", "tcp", url]
    return base


def _start_writer(w: int, h: int, fps: float, url: str) -> subprocess.Popen:
    cmd = _ffmpeg_cmd(w, h, fps, url)
    print("[FFMPEG]", " ".join(cmd))
    debug = os.environ.get("HL_FFMPEG_DEBUG")
    # eigene Prozessgruppe, damit wir sie sicher beenden können
    return subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=(None if debug else subprocess.DEVNULL),
        stderr=(None if debug else subprocess.STDOUT),
        bufsize=0,
        preexec_fn=os.setsid,
    )


# --------------- Graceful Shutdown (Signal-Handling) ----------------
_RUNNING = True
def _on_signal(sig, frame):
    global _RUNNING
    _RUNNING = False
    print(f"[INFO] tracker: signal {sig} received -> shutting down...", flush=True)

signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


# ========================== Main ==========================
def _draw_tracks(frame: np.ndarray, tracks: List[Track]) -> None:
    for t in tracks:
        x1, y1, x2, y2 = t.box
        color = (0,255,0) if t.confirmed else (0,165,255)
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
        cv2.putText(frame, f"ID {t.tid}", (x1, max(0,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def run(cfg: Dict, duration_sec: float = 0.0) -> int:
    tr_cfg = cfg.get("tracker") or {}
    src = tr_cfg.get("source_rtsp") or "rtsp://127.0.0.1:8554/larvacounter"
    out_url = tr_cfg.get("overlay_rtsp") or "rtsp://127.0.0.1:8554/larvacounter_tracks"
    infer_host = tr_cfg.get("infer_host") or (cfg.get("inference") or {}).get("host", "http://127.0.0.1:9001")
    model_id   = tr_cfg.get("model_id") or "dot_counting-plslb/33"
    api_key    = tr_cfg.get("api_key") or (cfg.get("inference") or {}).get("api_key") or ""
    conf_th    = float(tr_cfg.get("conf_thresh", 0.35))
    cls_filter = set(tr_cfg.get("class_filter") or [])
    iou_th   = float(tr_cfg.get("iou_match_thresh", 0.5))
    max_age  = int(tr_cfg.get("max_age", 20))
    min_hits = int(tr_cfg.get("min_hits", 3))
    target_fps = float(tr_cfg.get("target_fps", 3))
    jpeg_q   = int((cfg.get("inference") or {}).get("jpeg_quality", 85))
    timeout  = float((cfg.get("inference") or {}).get("timeout_sec", 10))

    # ---- Metrics-/Glättungs-Konfiguration (YAML) ----
    metrics_cfg = tr_cfg.get("metrics") or {}
    # bevorzugt tracker.metrics.smooth_sec, fallback auf hud_avg_window_sec (bestehender Key), dann 10.0
    smooth_sec = float(metrics_cfg.get("smooth_sec", tr_cfg.get("hud_avg_window_sec", 10.0)))
    emit_interval = float(metrics_cfg.get("interval_sec", 10.0))

    print(f"[INFO] tracker: {src} -> {infer_host} model={model_id} fps<={target_fps}")
    print(f"[INFO] metrics: smooth_sec={smooth_sec} interval_sec={emit_interval}")

    # ---- Rolling Windows (zeitbasiert) ----
    preds_win = RollingWindow(smooth_sec)
    tracks_win = RollingWindow(smooth_sec)
    last_emit = 0.0

    cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open RTSP source {src}")
    ok, frame = cap.read()
    if not ok or frame is None or frame.size == 0:
        raise RuntimeError("no first frame")
    h, w = frame.shape[:2]
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 0.0
    fps = target_fps if target_fps > 0 else (fps_in if fps_in > 0 else 5.0)
    writer = _start_writer(w, h, fps, out_url)
    tracker = IoUTracker(iou_thresh=iou_th, max_age=max_age, min_hits=min_hits)
    predictor = Predictor(infer_host, model_id, api_key, cfg)

    det_counts: List[int] = []
    t0 = time.time()

    try:
        while True:
            if not _RUNNING:
                break

            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                time.sleep(0.01)
                continue

            resp = predictor.predict(frame, jpeg_quality=jpeg_q, timeout=timeout)
            preds = resp.get("predictions", [])
            boxes: List[Tuple[int,int,int,int]] = []
            for p in preds:
                conf = float(p.get("confidence") or p.get("conf") or 0.0)
                if conf < conf_th:
                    continue
                cls = p.get("class") or p.get("cls") or ""
                if cls_filter and cls not in cls_filter:
                    continue
                if "x" in p and "y" in p and "width" in p and "height" in p:
                    x1 = int(max(0, p["x"] - p["width"]/2))
                    y1 = int(max(0, p["y"] - p["height"]/2))
                    x2 = int(min(w-1, x1 + p["width"]))
                    y2 = int(min(h-1, y1 + p["height"]))
                elif "box" in p and len(p["box"]) == 4:
                    x1, y1, x2, y2 = map(int, p["box"])
                else:
                    bx, by, bw, bh = int(p.get("bx",0)), int(p.get("by",0)), int(p.get("bw",0)), int(p.get("bh",0))
                    x1, y1, x2, y2 = bx, by, bx+bw, by+bh
                boxes.append((x1, y1, x2, y2))

            trks = tracker.update(boxes)
            _draw_tracks(frame, trks)

            # ---- HUD & Rolling-Stats ----
            now = time.time()
            preds_instant = float(len(preds))
            tracks_instant = float(len(trks))

            # Tracks für Ohaus-Bridge in JSON schreiben
            write_tracker_status(int(tracks_instant))

            preds_win.add(preds_instant, now)
            tracks_win.add(tracks_instant, now)

            med_preds = preds_win.median()
            med_tracks = tracks_win.median()

            # HUD oben rechts (Larven + Zielwert + Gewicht + Larven/g + Waage/Kippungen)
            lines: List[str] = []

            # Zeile 1: Larven (Median der Tracks)
            lines.append(f"Larven: {med_tracks:.0f}")

            # Ohaus-Overlay (Gewicht, Larven/g, Zielwert, Dosiervorschlag)
            ov = load_ohaus_overlay(OHAUS_OVERLAY_JSON)
            if ov:
                try:
                    weight_g = float(ov.get("weight_g", 0.0) or 0.0)
                    larvae_per_g = float(ov.get("larvae_per_g", 0.0) or 0.0)
                    target_larvae = int(ov.get("target_larvae", 0) or 0)
                    total_grams = ov.get("total_grams")
                    portion_weight_g = ov.get("portion_weight_g")
                    num_portions = ov.get("num_portions")
                except Exception:
                    weight_g = 0.0
                    larvae_per_g = 0.0
                    target_larvae = 0
                    total_grams = None
                    portion_weight_g = None
                    num_portions = None

                if target_larvae > 0:
                    lines.append(f"Zielwert: {target_larvae} Larven")

                lines.append(f"Gewicht: {weight_g:.2f} g")
                lines.append(f"Larven/g: {larvae_per_g:.1f}")

                # Dosiervorschlag
                try:
                    if portion_weight_g is not None and num_portions:
                        portion_weight_g_f = float(portion_weight_g)
                        num_portions_int = int(num_portions)
                        lines.append(f"Waage = {portion_weight_g_f:.0f} g  {num_portions_int} Kippungen")
                except Exception:
                    pass

            if lines:
                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 2.0          # große Schrift
                thickness = 4        # dicker
                line_spacing = 12
                margin = 30

                sizes = [cv2.getTextSize(t, font, scale, thickness)[0] for t in lines]
                max_width = max(s[0] for s in sizes)
                line_height = max(s[1] for s in sizes)

                # oben rechts, rechtsbündig
                x = w - max_width - margin
                y = margin + line_height

                for text in lines:
                    # Outline (schwarz)
                    cv2.putText(
                        frame, text, (x, y),
                        font, scale,
                        (0, 0, 0), thickness + 2, cv2.LINE_AA
                    )
                    # Vordergrund (gelb)
                    cv2.putText(
                        frame, text, (x, y),
                        font, scale,
                        (0, 255, 255), thickness, cv2.LINE_AA
                    )
                    y += line_height + line_spacing

            # Periodische JSON-Metriken (im Journal auslesbar)
            if now - last_emit >= emit_interval:
                out = {
                    "ts": now,
                    "window_sec": smooth_sec,
                    "preds_instant": preds_instant,
                    "tracks_instant": tracks_instant,
                    "preds_median": med_preds,
                    "tracks_median": med_tracks,
                    "preds_mean": preds_win.mean(),
                    "tracks_mean": tracks_win.mean(),
                    "samples_in_window": int(min(preds_win.count(), tracks_win.count())),
                }
                print(json.dumps(out, ensure_ascii=False))
                last_emit = now

            # ---- Writer robust halten ----
            if writer.poll() is not None:
                print("[WARNING] tracker: FFmpeg died, restarting writer…")
                writer = _start_writer(w, h, fps, out_url)
            try:
                writer.stdin.write(np.ascontiguousarray(frame).tobytes())
            except Exception:
                print("[WARNING] tracker: FFmpeg write failed (Broken pipe?) -> restarting writer")
                try:
                    writer.stdin.close()
                except Exception:
                    pass
                try:
                    writer.terminate()
                except Exception:
                    pass
                time.sleep(0.2)
                writer = _start_writer(w, h, fps, out_url)

            det_counts.append(len(preds))
            if duration_sec > 0 and (time.time() - t0) >= duration_sec:
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            cap.release()
        except Exception:
            pass
        # ffmpeg sauber beenden, dann hart, dann Prozessgruppe killen
        try:
            if writer and writer.stdin:
                try:
                    writer.stdin.flush()
                except Exception:
                    pass
                try:
                    writer.stdin.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if writer:
                writer.terminate()
                try:
                    writer.wait(timeout=2)
                except Exception:
                    pass
                if writer.poll() is None:
                    writer.kill()
                    try:
                        writer.wait(timeout=2)
                    except Exception:
                        pass
                try:
                    os.killpg(writer.pid, signal.SIGKILL)
                except Exception:
                    pass
        except Exception:
            pass

    # Zusammenfassung wie bisher
    if det_counts:
        avg = sum(det_counts) / len(det_counts)
        mn  = min(det_counts)
        mx  = max(det_counts)
        std = statistics.pstdev(det_counts) if len(det_counts) > 1 else 0.0
        med = statistics.median(det_counts)
    else:
        avg = mn = mx = std = med = 0.0
    summary = {
        "summary": {
            "duration_sec": round(time.time() - t0, 3),
            "frames": len(det_counts),
            "unique_tracks": len(tracker.confirmed_ids),
            "avg_detections_per_frame": round(avg, 2),
            "min_detections": mn,
            "max_detections": mx,
            "std_detections": round(std, 2),
            "median_detections": med,
        }
    }
    print(json.dumps(summary))
    return 0
