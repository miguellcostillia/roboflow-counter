#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ohaus Print Bridge
- Liest Gewichtsdaten von der Ohaus-Waage über TCP
- Reagiert auf PRINT-Ausgaben
- Holt aktuelle Tracks aus tracker/status.json
- Schickt Gramm + Tracks + Larven/g + Ziel-Larven + Dosiervorschlag an Telegraf (Influx Line Protocol)
- Schreibt Overlay-JSON für den Tracker/Highlight-Overlay
- Triggert den Anzeige-Pi per SSH
- Bietet lokalen UDP-Trigger für Remote-PRINT („P“)

Konfiguration:
- Wird ausschließlich aus config/config.yml geladen
- Keine env_file-Unterstützung (load_config unterstützt das nicht)
"""

from __future__ import annotations

import os
import socket
import time
import logging
import re
import json
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from roboflow_counter.config.loader import load_config


# ============================================================================
# Dataclass für Ohaus-Konfiguration
# ============================================================================

@dataclass
class OhausConfig:
    scale_host: str
    scale_port: int
    telegraf_host: str
    telegraf_port: int
    tracker_status_json: str
    overlay_json: str
    overlay_duration_sec: int
    display_pi_host: str
    display_pi_user: str
    display_pi_cmd: str
    trigger_host: str
    trigger_port: int
    measurement: str
    tag_facility: str
    tag_host: str
    log_level: str
    log_path: str
    target_larvae_total: int
    num_portions: int
    db_delay_sec: int


_trigger_print_event = threading.Event()


# ============================================================================
# Konfigurations-Loader
# ============================================================================

def make_config(cfg: Optional[Dict[str, Any]]) -> OhausConfig:
    ohaus_cfg = (cfg or {}).get("ohaus") or {}

    scale_host = ohaus_cfg.get("scale_host", "10.10.150.215")
    scale_port = int(ohaus_cfg.get("scale_port", 9761))

    telegraf_host = ohaus_cfg.get("telegraf_host", "127.0.0.1")
    telegraf_port = int(ohaus_cfg.get("telegraf_port", 8094))

    tracker_status_json = ohaus_cfg.get(
        "tracker_status_json",
        os.path.expanduser("~/projects/roboflow-counter/export/tracker/status.json")
    )

    overlay_json = ohaus_cfg.get(
        "overlay_json",
        os.path.expanduser("~/projects/roboflow-counter/export/ohaus_overlay.json")
    )
    overlay_duration_sec = int(ohaus_cfg.get("overlay_duration_sec", 20))

    display_pi_host = ohaus_cfg.get("display_pi_host", "10.10.150.252")
    display_pi_user = ohaus_cfg.get("display_pi_user", "manager")
    display_pi_cmd = ohaus_cfg.get("display_pi_cmd", "sudo /usr/local/bin/show_tracker_20s.sh")

    trigger_host = ohaus_cfg.get("trigger_host", "127.0.0.1")
    trigger_port = int(ohaus_cfg.get("trigger_port", 9102))

    measurement = ohaus_cfg.get("measurement", "ohaus_waage")
    tag_facility = ohaus_cfg.get("tag_facility", "larvacounter")
    tag_host = ohaus_cfg.get("tag_host", "roboflow")

    # Ziel-Larven & Teilgaben & DB-Verzögerung
    target_larvae_total = int(ohaus_cfg.get("target_larvae_total", 0))
    num_portions = int(ohaus_cfg.get("num_portions", 1))
    db_delay_sec = int(ohaus_cfg.get("db_delay_sec", 20))

    log_level = "INFO"
    log_path = "/var/log/ohaus_print_bridge.log"

    return OhausConfig(
        scale_host=scale_host,
        scale_port=scale_port,
        telegraf_host=telegraf_host,
        telegraf_port=telegraf_port,
        tracker_status_json=tracker_status_json,
        overlay_json=overlay_json,
        overlay_duration_sec=overlay_duration_sec,
        display_pi_host=display_pi_host,
        display_pi_user=display_pi_user,
        display_pi_cmd=display_pi_cmd,
        trigger_host=trigger_host,
        trigger_port=trigger_port,
        measurement=measurement,
        tag_facility=tag_facility,
        tag_host=tag_host,
        log_level=log_level,
        log_path=log_path,
        target_larvae_total=target_larvae_total,
        num_portions=num_portions,
        db_delay_sec=db_delay_sec,
    )


# ============================================================================
# Logging einrichten
# ============================================================================

def setup_logging(cfg: OhausConfig) -> None:
    level = getattr(logging, cfg.log_level, logging.INFO)
    handlers = []

    # Datei-Logging versuchen
    try:
        log_dir = os.path.dirname(cfg.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        handlers.append(logging.FileHandler(cfg.log_path))
    except Exception:
        pass

    handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


# ============================================================================
# Trigger-Server (UDP) – Remote-PRINT anstoßen
# ============================================================================

def trigger_server(cfg: OhausConfig) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((cfg.trigger_host, cfg.trigger_port))
        logging.info("Ohaus-Trigger-Server läuft auf %s:%s", cfg.trigger_host, cfg.trigger_port)
        while True:
            data, addr = sock.recvfrom(1024)
            msg = (data or b"").decode("utf-8", errors="ignore").strip()
            logging.info("Trigger von %s: %r", addr, msg)
            _trigger_print_event.set()
    except Exception as e:
        logging.error("Trigger-Server Fehler: %s", e)
    finally:
        sock.close()


def maybe_send_print_command(sock: Optional[socket.socket]) -> None:
    if not _trigger_print_event.is_set():
        return
    if sock is None:
        logging.warning("PRINT-Trigger erhalten, aber keine aktive Verbindung zur Waage.")
        return
    try:
        logging.info("Sende 'P' an die Waage (Remote-Trigger).")
        sock.sendall(b"P\r\n")
    except Exception as e:
        logging.warning("Fehler beim Senden von 'P' an die Waage: %s", e)
    finally:
        _trigger_print_event.clear()


# ============================================================================
# Hilfsfunktionen
# ============================================================================

def get_current_tracks(cfg: OhausConfig) -> int:
    try:
        with open(cfg.tracker_status_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        tracks = int(data.get("tracks", 0))
        logging.info("Tracks aus %s: %d", cfg.tracker_status_json, tracks)
        return tracks
    except Exception as e:
        logging.warning("Konnte tracks nicht lesen (%s): %s", cfg.tracker_status_json, e)
        return 0


def send_to_telegraf(
    cfg: OhausConfig,
    weight_g: float,
    tracks: int,
    larvae_per_g: float,
    total_grams: Optional[float],
    portion_weight_g: Optional[float],
) -> None:
    fields = [
        f"gramm={weight_g}",
        f"tracks={tracks}",
        f"larven_pro_g={larvae_per_g}",
    ]

    if cfg.target_larvae_total > 0:
        fields.append(f"target_larven={cfg.target_larvae_total}")
    if cfg.num_portions > 0:
        fields.append(f"teilgaben={cfg.num_portions}")
    if total_grams is not None:
        fields.append(f"ziel_gramm_total={total_grams}")
    if portion_weight_g is not None:
        fields.append(f"ziel_gramm_pro_portion={portion_weight_g}")

    field_str = ",".join(fields)

    line = (
        f"{cfg.measurement},facility={cfg.tag_facility},host={cfg.tag_host} "
        f"{field_str}"
    )

    logging.info("→ Influx: %s", line)

    try:
        sock = socket.create_connection((cfg.telegraf_host, cfg.telegraf_port), timeout=2)
        sock.sendall(line.encode("utf-8") + b"\n")
        sock.close()
    except Exception as e:
        logging.warning("Fehler beim Senden an Telegraf: %s", e)


def update_overlay_json(
    cfg: OhausConfig,
    weight_g: float,
    tracks: int,
    larvae_per_g: float,
    total_grams: Optional[float],
    portion_weight_g: Optional[float],
) -> None:
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_sec": cfg.overlay_duration_sec,
        "weight_g": weight_g,
        "tracks": tracks,
        "larvae_per_g": larvae_per_g,
        "target_larvae": cfg.target_larvae_total,
        "num_portions": cfg.num_portions,
        "total_grams": total_grams,
        "portion_weight_g": portion_weight_g,
    }

    os.makedirs(os.path.dirname(cfg.overlay_json), exist_ok=True)
    tmp = cfg.overlay_json + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)

    os.replace(tmp, cfg.overlay_json)

    logging.info("Overlay aktualisiert: %s", cfg.overlay_json)


def trigger_display_pi(cfg: OhausConfig) -> None:
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-i", os.path.expanduser("~/.ssh/id_ohaus"),
        f"{cfg.display_pi_user}@{cfg.display_pi_host}",
        cfg.display_pi_cmd,
    ]
    try:
        logging.info("Trigger Anzeige-Pi: %s", " ".join(cmd))
        subprocess.Popen(cmd)
    except Exception as e:
        logging.error("Fehler beim Triggern des Anzeige-Pi: %s", e)


def parse_weight(line: str) -> Optional[float]:
    m = re.search(r"([-+]?\d+(\.\d+)?)\s*g", line.strip())
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _delayed_influx_push(
    cfg: OhausConfig,
    weight_g: float,
    tracks: int,
    larvae_per_g: float,
    total_grams: Optional[float],
    portion_weight_g: Optional[float],
) -> None:
    try:
        delay = max(0, int(cfg.db_delay_sec))
    except Exception:
        delay = 0
    if delay > 0:
        logging.info("Warte %d s vor Influx-Write (Bildstabilität)…", delay)
        time.sleep(delay)
    send_to_telegraf(cfg, weight_g, tracks, larvae_per_g, total_grams, portion_weight_g)


def handle_print(cfg: OhausConfig, weight_g: float) -> None:
    logging.info("PRINT: %.2f g", weight_g)

    tracks = get_current_tracks(cfg)
    larvae_per_g = tracks / weight_g if weight_g > 0 else 0.0

    # Dosiervorschlag berechnen
    total_grams: Optional[float] = None
    portion_weight_g: Optional[float] = None
    if larvae_per_g > 0 and cfg.target_larvae_total > 0 and cfg.num_portions > 0:
        total_grams = cfg.target_larvae_total / larvae_per_g
        portion_weight_g = total_grams / cfg.num_portions
        # für Anzeige sinnvoll runden
        total_grams = round(total_grams, 1)
        portion_weight_g = round(portion_weight_g)
        logging.info(
            "Dosiervorschlag: Ziel=%d Larven, Larven/g=%.2f → total=%.1f g, pro Portion=%.0f g (Teilgaben=%d)",
            cfg.target_larvae_total,
            larvae_per_g,
            total_grams,
            portion_weight_g,
            cfg.num_portions,
        )
    else:
        logging.info(
            "Keine Dosiervorschlag-Berechnung möglich (larven/g=%.3f, target=%d, teilgaben=%d)",
            larvae_per_g,
            cfg.target_larvae_total,
            cfg.num_portions,
        )

    # Overlay sofort aktualisieren (für Anzeige-Pi/Tracker)
    update_overlay_json(cfg, weight_g, tracks, larvae_per_g, total_grams, portion_weight_g)

    # Anzeige-Pi sofort triggern
    trigger_display_pi(cfg)

    # Influx-Write mit Verzögerung in separatem Thread
    t = threading.Thread(
        target=_delayed_influx_push,
        args=(cfg, weight_g, tracks, larvae_per_g, total_grams, portion_weight_g),
        daemon=True,
    )
    t.start()


# ============================================================================
# Hauptschleife
# ============================================================================

def run_loop(cfg: OhausConfig) -> None:
    while True:
        sock = None
        try:
            logging.info("Verbinde mit Ohaus %s:%s …", cfg.scale_host, cfg.scale_port)
            sock = socket.create_connection((cfg.scale_host, cfg.scale_port), timeout=10)
        except Exception as e:
            logging.warning("Verbindung fehlgeschlagen: %s", e)
            time.sleep(5)
            continue

        logging.info("Mit Ohaus verbunden.")
        sock.settimeout(5.0)

        buf = b""

        while True:
            # Remote-PRINT (P)
            maybe_send_print_command(sock)

            try:
                chunk = sock.recv(1024)
            except socket.timeout:
                continue
            except Exception as e:
                logging.warning("Fehler in Verbindung: %s", e)
                break

            if not chunk:
                logging.warning("Ohaus hat Verbindung geschlossen.")
                break

            buf += chunk

            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="ignore")

                weight = parse_weight(text)
                if weight is not None:
                    handle_print(cfg, weight)

        logging.info("Reconnecting in 5s …")
        time.sleep(5)


# ============================================================================
# Entry Points
# ============================================================================

def run_from_config_path(cfg_path: str = "config/config.yml") -> None:
    cfg = load_config(cfg_path)
    ocfg = make_config(cfg)
    setup_logging(ocfg)

    # UDP-Trigger-Server starten (PRINT-Trigger von außen)
    threading.Thread(target=trigger_server, args=(ocfg,), daemon=True).start()

    logging.info("Starte Ohaus Bridge mit config.yml …")
    run_loop(ocfg)


def main() -> None:
    run_from_config_path()


if __name__ == "__main__":
    main()
