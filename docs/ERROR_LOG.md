# 🧯 Roboflow Counter – ERROR LOG  
**Version v0.02 — 2025-11-07**  
**Dokumentiert: Fehler, Ursachen & Lösungen**

---

## ⚙️ System & Build-bezogene Fehler

### 🧩 1️⃣ OpenCV / CUDA Build-Fehler
**Fehler:**  
```
AttributeError: module 'cv2.cuda' has no attribute 'getDeviceName'
```
**Ursache:**  
In OpenCV 4.10 ist `getDeviceName()` nicht mehr verfügbar.  
Die Methode heißt jetzt `getDeviceInfo()` oder wird über `cv2.cuda.printCudaDeviceInfo()` abgebildet.

**Lösung:**  
```python
n = cv2.cuda.getCudaEnabledDeviceCount()
if n:
    info = cv2.cuda.printCudaDeviceInfo(0)
```

---

### 🧩 2️⃣ NumPy ABI / ImportError nach OpenCV-Build
**Fehler:**  
```
ImportError: numpy.core.multiarray failed to import
```
**Ursache:**  
OpenCV wurde mit einem älteren NumPy-ABI gebaut, nachträglich wurde NumPy ≥2 installiert.

**Lösung:**  
```bash
pip uninstall -y numpy opencv-python
pip install "numpy<2" opencv-python==4.10.*
```

---

### 🧩 3️⃣ `ModuleNotFoundError: No module named 'roboflow_counter'`
**Ursache:**  
Python findet das Paket nicht, weil das Projekt ein **src/**-Layout verwendet.  
`PYTHONPATH` wurde beim lokalen Start nicht gesetzt.

**Lösung (lokal):**
```bash
PYTHONPATH=src python3 -m roboflow_counter.main run-highlight
```
**Systemd:**  
Im Dienst ist `.venv/bin/python -m roboflow_counter.main …` gesetzt → kein Problem mehr.

---

### 🧩 4️⃣ CUDA-Treiber nicht aktiv
**Fehler:**  
```
cv2.error: CUDA driver version is insufficient for CUDA runtime version
```
**Lösung:**  
Nach Installation `sudo reboot` durchführen oder falsche CUDA-Version entfernen:
```bash
sudo apt purge nvidia-cuda-toolkit
sudo apt install nvidia-driver-575
sudo reboot
```
→ Danach mit `nvidia-smi` prüfen.

---

## 📡 RTSP / MediaMTX / Stream Fehler

### 🧩 5️⃣ RTSP 404 – „Server returned 404 Not Found“
**Fehler:**  
```
Error opening input file rtsp://127.0.0.1:8554/larvacounter. Server returned 404 Not Found
```
**Ursache:**  
Der Dump-&-Cleanup-Dienst startete, bevor der Highlight-Stream verfügbar war.

**Lösung:**  
Startreihenfolge korrigiert → Dump erst nach Highlight-Stream starten.

---

### 🧩 6️⃣ `method SETUP failed: 461 Unsupported Transport`
**Ursache:**  
Kamera erwartete TCP-Transport, MediaMTX nutzte UDP.

**Lösung:**  
In der Config:
```yaml
sourceProtocol: tcp
```
und in ffmpeg / highlight.py:
```bash
-rtsp_transport tcp
```

---

### 🧩 7️⃣ `json: unknown field "readTimeout"`
**Ursache:**  
MediaMTX-Konfiguration enthielt veraltete Felder.

**Lösung:**  
Aktualisierte Config laut neuer MediaMTX-Syntax. Alte Felder wie
```
readTimeout: 10s
```
entfernt.

---

### 🧩 8️⃣ Highlight Stream instabil nach Start
**Symptom:**  
VLC zeigt nur die ersten Sekunden, dann Ruckler.

**Ursache:**  
ffmpeg sendete mit variabler Framerate, MediaMTX verlor Sync.

**Lösung:**  
Fixe FPS erzwingen:
```bash
ffmpeg -re -f rawvideo -pix_fmt bgr24 -r 6 -i pipe:0 -vf format=yuv420p ...
```

---

### 🧩 9️⃣ `E: Paket libtbb2 kann nicht gefunden werden`
**Ursache:**  
Ubuntu 24.04 ersetzt `libtbb2` durch `libtbb12`.

**Lösung:**  
```bash
sudo apt install libtbb12
```

---

## ✅ Zusammenfassung

| Kategorie | Häufigster Fehler | Lösung |
|:-----------|:------------------|:--------|
| CUDA / Build | OpenCV nicht mit CUDA kompiliert | Neu-Build mit `-D WITH_CUDA=ON` |
| RTSP | Stream 404 / Transport UDP | `sourceProtocol: tcp` |
| OpenCV | NumPy ABI Konflikt | `pip install "numpy<2"` |
| Dump & Cleanup | Start zu früh | Startreihenfolge angepasst |
| Highlight | FPS instabil | Fixe Framerate `-r 6` gesetzt |

---

**Letzter Review:** 2025-11-07  
**Maintainer:** Ecofly GmbH / R&D  
📧 internal@ecofly.at 🌐 www.ecofly.at
