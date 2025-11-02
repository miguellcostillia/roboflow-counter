# Project State

- Updated: 2025-11-02 14:43 UTC
- Branch: 20251102-1434_feat-config-rtsp-base
- HEAD: 39cc161

## Done today
- Config-Loader (ENV > YAML) implementiert
- RTSP-Basis (Open, Read, Reconnect, FPS-Throttle) + `run-stream` CLI

## Next steps
- Tests für Config-Merge (ENV > YAML) und Pfad-Validierung
- RTSP: Logging verbessern, Stats, Timeout/Backoff feinjustieren
- Docs: USER_GUIDE Abschnitt für `run-stream` ergänzen
- Nächster Branch: `<YYYYMMDD-HHMM>_feat-config-tests-and-rtsp-logging`

## Quick test commands
- python -m roboflow_counter.main run-stream --help
- python -m roboflow_counter.main run-stream
- python -m roboflow_counter.main run-stream --fps-target 5 rtsp://127.0.0.1:8554/larvacounter
