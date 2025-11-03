# Häufige Fehler & Fixes

### `No module named cv2`
System-OpenCV in venv einbinden:
`.pth` in `$VENV_SITE` mit `/usr/local/lib/python3.12/dist-packages`

### NumPy ABI / OpenCV Crash
OpenCV gegen NumPy 1.x gebaut:
```bash
pip install "numpy<2"
