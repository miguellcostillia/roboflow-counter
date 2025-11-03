# Changelog

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
