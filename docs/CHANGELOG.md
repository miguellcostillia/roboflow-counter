
## [2025-11-02] (20251102-1434_feat-config-rtsp-base)
### Added
- Config-Loader (ENV > YAML) und RTSP-Basis mit `run-stream` CLI
- RTSP-Reconnect & FPS-Throttle (minimal)
- Erste Modulstruktur: `config/loader.py`, `stream/rtsp.py`

### Notes
- CLI testen:
  - `python -m roboflow_counter.main run-stream --help`
  - `python -m roboflow_counter.main run-stream` (nimmt URL aus `config/config.yml`)
  - `python -m roboflow_counter.main run-stream --fps-target 5 rtsp://127.0.0.1:8554/larvacounter`
