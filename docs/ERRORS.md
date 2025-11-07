# Häufige Fehler & Fixes

### `No module named cv2`
System-OpenCV in venv einbinden:
`.pth` in `$VENV_SITE` mit `/usr/local/lib/python3.12/dist-packages`

### NumPy ABI / OpenCV Crash
OpenCV gegen NumPy 1.x gebaut:
```bash
pip install "numpy<2"

## OpenCV import error: "No module named 'cv2'"
**Ursache:** System-OpenCV nicht im venv-Pfad.  
**Fix (bereits umgesetzt):** `.pth`/Symlink-Lösung entfernt; stattdessen sauberer System-Install + venv NumPy<2.

## NumPy 1.x vs 2.x ABI
**Ursache:** cv2 gegen NumPy 1.x gebaut; venv hatte NumPy 2.x.  
**Fix:** `pip install 'numpy<2'` in venv.

## RTSP Abbruch/Kein Exit
**Hinweis:** In `run-stream` mit `--timeout-ms` & `--log-level DEBUG` starten; Abbruch via Ctrl+C (mehrfach) oder `q`.
