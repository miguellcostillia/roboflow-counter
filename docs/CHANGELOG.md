# Changelog


## v0.02 — 2025-11-07T12:45:00+01:00
### Added
- **Motion Highlight Stream (`roboflow-highlight.service`)**
  - GPU-basiertes RTSP-Ingest → RTSP-Publish mit `h264_nvenc`.
  - Dynamische Gaussian-Filterung, FPS-Anpassung und robuste Wiederverbindung.
  - Einheitliches Logging (INFO-Level) und automatischer Neustart via Systemd.
- **Dump & Cleanup Service (`larvacounter-dump-clean.service`)**
  - Periodischer Frame-Export (JPEG-Snapshots) über FFmpeg.
  - Automatisches Aufräumen alter Exporte (Rotations-Cleanup).
  - Start-Warteprobe, um RTSP-404-Fehler beim Boot zu vermeiden.
- **Tracker-Modul (`src/roboflow_counter/tracker/`)**
  - Neuer Entry-Point `run.py`, nutzt bestehende `config.loader`.
  - Leichtes IoU-Tracking, vorbereitet für SORT/ByteTrack-Upgrade.
  - YAML-Integration über neuen `tracker:`-Block in `config/config.yml`.
- **Systemd-Integration**
  - Alle Dienste (`highlight`, `dump-clean`, `tracker`) greifen auf dieselbe `.env` und YAML-Konfiguration zu.
  - Einheitliche Restart-Strategien und konsistentes Logging.

### Changed
- **Projektstruktur bereinigt**
  - Entfernt: Backups, `settings.py`, `config_path.py`, doppelte `gallery_server.py`.
  - Startbefehl vereinheitlicht: `python3 src/roboflow_counter/main.py …`.
  - `.gitignore` erweitert (Cache-Artefakte, Logs, Backups).
- **`highlight.py` verbessert**
  - Automatische Kernel- und Sigma-Berechnung.
  - Sauberere Logging-Ausgabe (Input/Output-Streams).
- **`dump_and_clean.py` optimiert**
  - Besseres Fehler- und Exit-Handling.
  - Geringerer Speicherverbrauch bei Langläufen.

### Fixed
- Race-Condition beim Dump-Start (404 → Retry).
- `ModuleNotFoundError` beim lokalen Start ohne `PYTHONPATH=src`.
- Doppelte `gallery_server.py`-Datei entfernt.

### Next
- Live-Overlay-Integration Tracker → Highlight.
- Statistiken und Zähler-Export nach InfluxDB/Telegraf.
- Validation-Schema für `tracker:`-Block in `config/schema.py`.


## v0.01 — 2025-11-03T16:29:17+00:00
### Added
- GPU-Streaming-Baseline mit OpenCV 4.10 (CUDA+DNN), RTSP Ingest stabil.
- ONNX Runtime GPU installiert (Vorbereitung für Inferenz).
- Logging: `logs/rtsp_*.log`, Debug-Level wählbar.

### Changed
- Zentrale Config nur in `config/config.yml` (kein Root-Config mehr).
- `.env` ausschließlich `config/.env`.

### Fixed
- OpenCV/NumPy ABI-Konflikt (NumPy<2 in venv).
- Hartnäckige Shell-Abbrüche (bereinigte Bash-Profile & robustes run-script).

### Next
- ONNX Modell-Download integrieren.
- TensorRT Engine-Build optional (trtexec/Polygraphy).
- Zähler/Overlay & Export (RTSP/RTMP) als Dienst.
## [v0.01-build-base] - 2025-11-03

### Added
- Baseline nach OpenCV(+CUDA) + ONNX Runtime GPU Setup (keine Binaries)
- Einheitliche Config: `config/config.yml`, Secrets: `config/.env`
- CLI: `show-config`, `run-stream` (RTSP geprüft; Exit sauber via `q` / SIGINT)

### Fixed
- Config-Pfad Fehler (Root → `config/`)
- FFmpeg-Devel unter Ubuntu 24.04 (`libswresample-dev` statt `libavresample-dev`)

### Notes
- Tag: `v0.01-build-base` als Startpunkt für Folgeprojekte / TensorRT
