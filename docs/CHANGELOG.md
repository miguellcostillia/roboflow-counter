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
