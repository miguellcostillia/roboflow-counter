# 🪰 Roboflow Counter  
**GPU-basierte Motion-Detection, Tracking & Frame-Export für BSF-Larven-Streams**  
**Version v0.02 — 2025-11-07**

---

## 🧱 Projektüberblick

Der *Roboflow Counter* ist eine GPU-beschleunigte Bildverarbeitungs-Pipeline für die automatische Bewegungserkennung, Objektverfolgung und Frame-Extraktion von RTSP-Kamerastreams.  
Er wird in der BSF-Produktion (Hermetia illucens) zur Erkennung und Zählung von Larvenaktivität verwendet.

Das Projekt kombiniert:
- **OpenCV 4.10 mit CUDA/DNN** (GPU-Inferenz)
- **FFmpeg + MediaMTX** für Stream-Ingest und -Publish
- **Roboflow Inference Server (lokal)** für Objekterkennung
- **Systemd-Services** für Dauerbetrieb und automatische Neustarts

---

## ⚙️ Systemvoraussetzungen

**Betriebssystem:** Ubuntu 24.04 LTS (oder kompatibel)  
**GPU:** NVIDIA RTX-Serie (getestet mit RTX A4000)  
**CUDA:** 12.9  
**Python:** ≥3.12

---

## 🔩 CUDA- und OpenCV-Setup (GPU-Unterstützung)

### 1️⃣ NVIDIA-Treiber & CUDA installieren

```bash
sudo apt update
sudo apt install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall
sudo reboot
```

Nach Neustart prüfen:
```bash
nvidia-smi
```

Beispielausgabe:
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 575.57.08   Driver Version: 575.57.08   CUDA Version: 12.9       |
| GPU  Name        Temp  Perf  Pwr:Usage/Cap  Memory-Usage  GPU-Util          |
| 0  RTX A4000     62C   P2   40W / 140W     552MiB / 16376MiB   0%           |
+-----------------------------------------------------------------------------+
```

### 2️⃣ CUDA Toolkit & CuDNN installieren

```bash
sudo apt install -y nvidia-cuda-toolkit libcudnn9-dev
```

### 3️⃣ OpenCV mit CUDA-Unterstützung (empfohlen über Build-Skript)

```bash
sudo apt install -y build-essential cmake git libgtk-3-dev libavcodec-dev   libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev   libjpeg-dev libpng-dev libtiff-dev gfortran openexr python3-dev python3-numpy

# Beispiel: OpenCV 4.10
git clone https://github.com/opencv/opencv.git -b 4.10.0
git clone https://github.com/opencv/opencv_contrib.git -b 4.10.0
cd opencv && mkdir build && cd build

cmake -D CMAKE_BUILD_TYPE=Release       -D CMAKE_INSTALL_PREFIX=/usr/local       -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules       -D WITH_CUDA=ON -D ENABLE_FAST_MATH=ON -D CUDA_FAST_MATH=ON       -D WITH_CUDNN=ON -D OPENCV_DNN_CUDA=ON -D BUILD_EXAMPLES=OFF ..

make -j$(nproc)
sudo make install
```

### 4️⃣ Test

```bash
python3 - <<'PY'
import cv2
print("OpenCV:", cv2.__version__)
print("CUDA devices:", cv2.cuda.getCudaEnabledDeviceCount())
if cv2.cuda.getCudaEnabledDeviceCount():
    print("Device 0:", cv2.cuda.getDeviceName(0))
PY
```

---

## 📁 Projektstruktur (aktueller Stand)

roboflow-counter/
├── config/
│   ├── config.yml           # YAML-Konfiguration (Pipeline/Tracker)
│   ├── .env                 # Secrets (nicht committen)
│   ├── loader.py            # Config-Loader
│   └── schema.py            # Validierung
│
├── src/
│   └── roboflow_counter/
│       ├── main.py          # CLI-Entry (run-highlight, rtsp-test, cuda-check …)
│       ├── stream/          # Motion-Highlight
│       │   ├── highlight.py
│       │   └── rtsp.py
│       ├── tracker/         # Roboflow IoU-Tracker
│       │   └── run.py
│       ├── tools/
│       │   └── dump_and_clean.py
│       ├── util/
│       │   └── logging.py
│       └── web/
│           └── gallery_server.py
│
├── docs/
│   ├── CHANGELOG.md
│   ├── PROJECT_STATE.md
│   ├── ERROR_LOG.md
│   └── SUCCESS_VERSION.md
│
├── .gitignore
└── setup.cfg / pyproject.toml

---

## 🧩 Setup (Entwicklungsumgebung)

```bash
git clone git@github.com:ecofly-gmbh/roboflow-counter.git
cd roboflow-counter

python3 -m venv .venv
source .venv/bin/activate

pip install -U pip wheel
pip install -e .
```

---

## 🔧 Konfigurationsstruktur

config/
 ├── config.yml     → Versionierte Projekt-/Pipeline-Config  
 └── .env           → Secrets & lokale Overrides

Priorität: `.env` überschreibt `config.yml`  
Templates: `config/config.example.yml`, `config/.env.example`

---

## 🧭 CLI-Kommandos

| Zweck | Befehl |
|:------|:-------|
| Config anzeigen | `python src/roboflow_counter/main.py show-config` |
| CUDA / GPU-Test | `python src/roboflow_counter/main.py cuda-check` |
| RTSP testen | `python src/roboflow_counter/main.py rtsp-test <URL>` |
| Highlight starten | `python src/roboflow_counter/main.py run-highlight` |
| Dump & Cleanup | `python src/roboflow_counter/tools/dump_and_clean.py` |
| *(Optional)* Tracker starten | `python src/roboflow_counter/tracker/run.py` |

---

## 🧰 Systemd-Dienste

### roboflow-highlight.service  
GPU-beschleunigte Bewegungserkennung (RTSP-In → RTSP-Out).

### larvacounter-dump-clean.service  
Regelmäßiger Frame-Export (JPEG) + automatisches Aufräumen.

### roboflow-tracker.service *(optional)*  
Objekt-Tracking über Roboflow-Inference mit IoU-Logik.

> Alle Dienste verwenden dieselbe Konfiguration aus `config/config.yml` und `.env`.

Systemd-Befehle:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now roboflow-highlight larvacounter-dump-clean
sudo systemctl enable --now roboflow-tracker   # optional
sudo systemctl status roboflow-highlight --no-pager
```

---

## 🧠 Git-Workflow

```bash
git switch main && git pull
git switch -c feat/<task>-YYYY-MM-DD
git add .
git commit -m "feat: <beschreibung>"
git push -u origin feat/<task>-YYYY-MM-DD
git switch main
git merge --no-ff feat/<task>-YYYY-MM-DD
git push
```

---

## 📚 Dokumentation

| Datei | Zweck |
|:------|:------|
| `docs/CHANGELOG.md` | Änderungsverlauf (aktuell **v0.02 — 2025-11-07**) |
| `docs/PROJECT_STATE.md` | aktueller Stand / TODO |
| `docs/ERROR_LOG.md` | letzte Fehler / Debug-Hinweise |
| `docs/SUCCESS_VERSION.md` | letzte stabile Commit-ID |

---

## 🗓️ Changelog (Auszug)

**v0.02 — 2025-11-07**  
- GPU Motion-Highlight & Dump-Cleanup integriert  
- Tracker-Modul hinzugefügt  
- Systemd-Dienste bereinigt & vereinheitlicht  
- CUDA 12.9 Build stabil  
- Race-Condition beim Dump-Start behoben  

**v0.01 — 2025-11-03**  
- GPU-Build & Config-Basis  
- RTSP-Ingest geprüft  
- Grund-CLI eingeführt

---

## 🔜 Roadmap

- [ ] Tracker-Overlay → Highlight-Stream verbinden  
- [ ] InfluxDB / Telegraf Export  
- [ ] Validierung für Tracker in `config/schema.py`  
- [ ] GitHub-Release Tag `v0.02`

---

Maintainer: **Ecofly GmbH / R&D**  
📧 internal@ecofly.at 🌐 www.ecofly.at
