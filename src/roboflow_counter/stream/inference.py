#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roboflow-Inference (lokal) für roboflow-counter
- Liest Frames aus RTSP
- Endpoints: /<model_id> (Docker-Style, bevorzugt), /v1/infer, /infer, /infer/<model_id>, /infer/object_detection
- Gibt Detections als JSON-Lines aus (stdout)
- Optional: speichert Overlays als JPEG (Rotation: max. 20 Dateien)
"""

from __future__ import annotations
import os
import time
import json
import signal
import base64
from typing import Dict, Any, List, Optional
from pathlib import Path
from collections import deque

import cv2
import numpy as np
import requests

from roboflow_counter.config.loader import load_and_validate as load_config
from roboflow_counter.util.logging import setup_logger

LOG = setup_logger("inference")
STOP = False

API_KEY = os.environ.get("API_KEY", "d6jW6eD3w5L0ObSoDK6H")

# =============================================================================
# Signals
# =============================================================================
def _sig(_s, _f):
    """graceful stop"""
    global STOP
    STOP = True

signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)

# =============================================================================
# Helpers
# =============================================================================
def _project_root() -> Path:
    # .../src/roboflow_counter/stream/inference.py -> project root
    return Path(__file__).resolve().parents[3]

def _resolve_path(p: str) -> str:
    pth = Path(p)
    return str(pth if pth.is_absolute() else _project_root() / pth)

def _resolve_api_key(raw: str) -> str:
    """Falls YAML ${ROBOFLOW_API_KEY:-} nicht expandiert, ENV nutzen."""
    if not raw:
        return os.environ.get("ROBOFLOW_API_KEY", "")
    if raw.startswith("${") and "ROBOFLOW_API_KEY" in raw:
        return os.environ.get("ROBOFLOW_API_KEY", "")
    return raw

def _get_model_id(cfg: dict) -> str:
    """Model-ID aus config oder ENV bestimmen (ohne Workspace-Prefix)."""
    mid = (cfg.get("model") or {}).get("id") \
        or (cfg.get("tracker") or {}).get("model_id") \
        or os.environ.get("MODEL_ID") \
        or os.environ.get("ROBOFLOW_MODEL_ID")
    if not mid:
        raise KeyError("No model id found. Set model.id or tracker.model_id in config.yml or env MODEL_ID / ROBOFLOW_MODEL_ID.")
    return mid

def _compose_model_paths(model_id: str) -> List[str]:
    """Nur lokale IDs (ohne Workspace-Präfix)."""
    return [model_id.strip("/")]

def _draw_overlay(frame_bgr: np.ndarray, dets: List[Dict[str, Any]]) -> np.ndarray:
    out = frame_bgr.copy()
    h, w = out.shape[:2]
    for d in dets:
        x1, y1, x2, y2 = d["box"]
        x1 = max(0, min(int(x1), w - 1))
        y1 = max(0, min(int(y1), h - 1))
        x2 = max(0, min(int(x2), w - 1))
        y2 = max(0, min(int(y2), h - 1))
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{d.get('cls','obj')} {d.get('conf',0):.2f}"
        cv2.putText(out, label, (x1, max(0, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
    return out

# =============================================================================
# Core Inference
# =============================================================================
def _infer_once(
    host: str,
    model_id: str,
    api_key: str,
    frame_bgr: np.ndarray,
    timeout: int = 10,
    jpeg_quality: int = 85,
    class_filter: Optional[List[str]] = None,
    conf_thresh: float = 0.35,
) -> List[Dict[str, Any]]:
    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
    if not ok:
        LOG.warning("JPEG-Encode failed")
        return []

    f_bytes = buf.tobytes()
    files_file = {"file": ("frame.jpg", f_bytes, "image/jpeg")}
    files_image = {"image": ("frame.jpg", f_bytes, "image/jpeg")}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    paths = _compose_model_paths(model_id)

    data: Optional[Dict[str, Any]] = None
    last_status: Optional[int] = None
    last_text: str = ""

    # ---- 0) NEU: JSON-Schema /infer/object_detection mit Base64 ----
    try:
        img_b64 = base64.b64encode(f_bytes).decode("ascii")
        url = f"{host.rstrip('/')}/infer/object_detection"
        payload = {
            "api_key": api_key,
            "model_id": model_id,
            "image": {
                "type": "base64",
                "value": img_b64,
            },
        }
        r = requests.post(url, json=payload, timeout=timeout)
        last_status, last_text = r.status_code, r.text[:400]
        if r.ok:
            data = r.json()
        else:
            LOG.warning("json object_detection → HTTP %s: %s", last_status, last_text)
    except Exception as e:
        LOG.warning("json object_detection error: %s", e)

    # ---- 0.5) Wenn JSON-Schema klappt, brauchen wir alte Wege nicht ---
    if data is not None:
        pass
    else:
        # ---- 1) Docker-Style zuerst: /<model_path> (ohne Header, dann mit api_key Query) ----
        for path in paths:
            url = f"{host.rstrip('/')}/{path}"
            try:
                r = requests.post(url, files=files_file, timeout=timeout)  # KEIN Authorization-Header
                last_status, last_text = r.status_code, r.text[:400]
                if r.ok:
                    data = r.json()
                    break
                if api_key and r.status_code in (401, 403):
                    r = requests.post(url, params={"api_key": api_key}, files=files_file, timeout=timeout)
                    last_status, last_text = r.status_code, r.text[:400]
                    if r.ok:
                        data = r.json()
                        break
                LOG.warning("docker-path /%s → HTTP %s: %s", path, r.status_code, last_text)
            except Exception as e:
                LOG.warning("docker-path error (%s): %s", path, e)

        # ---- 2) Modern: /v1/infer ----
        if data is None:
            for path in paths:
                url = f"{host.rstrip('/')}/v1/infer"
                try:
                    r = requests.post(url, headers=headers, data={"model_id": path}, files=files_file, timeout=timeout)
                    last_status, last_text = r.status_code, r.text[:400]
                    if r.ok:
                        data = r.json()
                        break
                    LOG.warning("v1/infer [%s] → HTTP %s: %s", path, r.status_code, last_text)
                except Exception as e:
                    LOG.warning("v1/infer error (%s): %s", path, e)

        # ---- 3) /infer ----
        if data is None:
            for path in paths:
                url = f"{host.rstrip('/')}/infer"
                try:
                    r = requests.post(url, headers=headers, data={"model_id": path}, files=files_image, timeout=timeout)
                    last_status, last_text = r.status_code, r.text[:400]
                    if r.ok:
                        data = r.json()
                        break
                    if api_key and r.status_code in (401, 403, 405):
                        r = requests.post(
                            url,
                            params={"api_key": api_key},
                            data={"model_id": path},
                            files=files_image,
                            timeout=timeout,
                        )
                        last_status, last_text = r.status_code, r.text[:400]
                        if r.ok:
                            data = r.json()
                            break
                    LOG.warning("/infer [%s] → HTTP %s: %s", path, r.status_code, last_text)
                except Exception as e:
                    LOG.warning("/infer error (%s): %s", path, e)

        # ---- 4) Legacy: /infer/<model_path> ----
        if data is None:
            for path in paths:
                url = f"{host.rstrip('/')}/infer/{path}"
                try:
                    r = requests.post(url, headers=headers, files=files_image, timeout=timeout)
                    last_status, last_text = r.status_code, r.text[:400]
                    if r.ok:
                        data = r.json()
                        break
                    if api_key and r.status_code in (401, 403, 405):
                        r = requests.post(
                            url,
                            params={"api_key": api_key},
                            files=files_image,
                            timeout=timeout,
                        )
                        last_status, last_text = r.status_code, r.text[:400]
                        if r.ok:
                            data = r.json()
                            break
                    LOG.warning("legacy /infer/%s → HTTP %s: %s", path, r.status_code, last_text)
                except Exception as e:
                    LOG.warning("legacy error (%s): %s", path, e)

        # ---- 5) Typ-Endpoint alt: /infer/object_detection mit multipart ----
        if data is None:
            url = f"{host.rstrip('/')}/infer/object_detection"
            try:
                r = requests.post(
                    url,
                    headers=headers,
                    data={"model_id": model_id},
                    files=files_image,
                    timeout=timeout,
                )
                last_status, last_text = r.status_code, r.text[:400]
                if r.ok:
                    data = r.json()
                else:
                    LOG.warning("type-endpoint object_detection → HTTP %s: %s", last_status, last_text)
            except Exception as e:
                LOG.warning("type-endpoint error: %s", e)

    if data is None:
        LOG.warning("Inference failed – last HTTP %s: %s", last_status, last_text)
        return []

    # ---- Predictions filtern ----
    dets: List[Dict[str, Any]] = []
    for det in data.get("predictions", []):
        cls = det.get("class", "")
        conf = float(det.get("confidence", 0.0))
        if conf < conf_thresh:
            continue
        if class_filter and cls not in class_filter:
            continue
        if all(k in det for k in ("x", "y", "width", "height")):
            x = float(det["x"]); y = float(det["y"])
            w = float(det["width"]); h = float(det["height"])
            x1, y1, x2, y2 = x - w/2, y - h/2, x + w/2, y + h/2
        else:
            x1 = float(det.get("x1", 0)); y1 = float(det.get("y1", 0))
            x2 = float(det.get("x2", 0)); y2 = float(det.get("y2", 0))
        dets.append({"cls": cls, "conf": conf, "box": [x1, y1, x2, y2]})
    return dets

# =============================================================================
# CLI Hooks (mit konfigurierbaren Pfaden)
# =============================================================================
def run_smoke(cfg_path: str = "config/config.yml", env_file: str = "config/.env") -> int:
    """Testet Erreichbarkeit und Modellzugriff."""
    cfg = load_config(_resolve_path(cfg_path), _resolve_path(env_file))
    host = cfg["inference"]["host"]
    api_key = _resolve_api_key(cfg["inference"].get("api_key", ""))

    ok = True
    try:
        requests.get(host, timeout=int(cfg["inference"].get("timeout_sec", 10)))
    except Exception as e:
        LOG.warning("Host not reachable: %s", e)
        ok = False

    try:
        model_id = _get_model_id(cfg)
    except Exception as e:
        LOG.warning(str(e))
        model_id = "UNKNOWN"

    img = np.zeros((256, 256, 3), np.uint8)
    cv2.putText(img, "probe", (40, 140), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    if model_id != "UNKNOWN":
        _ = _infer_once(
            host, model_id, api_key, img,
            timeout=int(cfg["inference"].get("timeout_sec", 10)),
            jpeg_quality=int(cfg["inference"].get("jpeg_quality", 85)),
            class_filter=cfg["inference"].get("class_filter", []) or None,
            conf_thresh=float(cfg["inference"].get("conf_thresh", 0.35)),
        )

    LOG.info("smoke: host_ok=%s, auth=%s", ok, "Bearer" if bool(api_key) else "none")
    print(json.dumps({"host_ok": ok, "model_id": model_id, "auth": bool(api_key)}), flush=True)
    return 0 if ok else 2

def run_rtsp(
    source: Optional[str] = None,
    cfg_path: str = "config/config.yml",
    env_file: str = "config/.env",
) -> int:
    """RTSP-Inferenz-Loop (liest RTSP aus config, wenn source None)."""
    cfg = load_config(_resolve_path(cfg_path), _resolve_path(env_file))
    src = source or (cfg.get("input") or {}).get("rtsp_url")

    host = cfg["inference"]["host"]
    api_key = _resolve_api_key(cfg["inference"].get("api_key", ""))
    model_id = _get_model_id(cfg)

    timeout = int(cfg["inference"].get("timeout_sec", 10))
    jpeg_q = int(cfg["inference"].get("jpeg_quality", 85))
    class_filter = cfg["inference"].get("class_filter", []) or None
    conf_th = float(cfg["inference"].get("conf_thresh", 0.35))
    max_fps = float(cfg["inference"].get("max_fps", 3))
    period = 1.0 / max(max_fps, 0.1)

    tr = cfg.get("tracker", {})
    exp = tr.get("export", {}) if isinstance(tr, dict) else {}
    overlay_jpeg = bool(exp.get("overlay_jpeg", False))
    overlay_dir = Path(exp.get("overlay_dir", "/tmp/roboflow_overlays"))
    overlay_every_n = int(exp.get("overlay_every_n", 10))
    overlay_dir.mkdir(parents=True, exist_ok=True)
    saved_files: deque[Path] = deque(maxlen=20)

    cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        LOG.error("cannot open source: %s", src)
        return 2

    LOG.info("infer-rtsp: %s -> %s (fps<= %s, auth=%s)",
             src, host, max_fps, "Bearer" if bool(api_key) else "none")

    frames = 0
    last = 0.0
    try:
        while not STOP:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            now = time.time()
            if now - last < period:
                time.sleep(0.002)
                continue
            last = now
            frames += 1

            dets = _infer_once(
                host, model_id, api_key, frame,
                timeout=timeout, jpeg_quality=jpeg_q,
                class_filter=class_filter, conf_thresh=conf_th,
            )
            print(json.dumps({"ts": int(now), "frame": frames, "detections": len(dets)}), flush=True)

            if overlay_jpeg and (frames % overlay_every_n == 0):
                vis = _draw_overlay(frame, dets)
                fname = overlay_dir / f"overlay_{int(now)}_{frames}.jpg"
                try:
                    cv2.imwrite(str(fname), vis, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if len(saved_files) == saved_files.maxlen:
                        old = saved_files.popleft()
                        old.unlink(missing_ok=True)
                    saved_files.append(fname)
                except Exception as e:
                    LOG.warning("could not write overlay: %s", e)
    finally:
        cap.release()
    LOG.info("inference stopped")
    return 0
