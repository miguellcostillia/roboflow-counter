# 🚀 Chat Starter — roboflow-counter

**Nutze diesen Textblock immer, wenn du einen neuen Chat beginnst.**
Damit die AI sofort im richtigen Projektkontext arbeitet (laut AI_Playbook).

---

## 👇 Starttext in neuem Chat einfügen

Projekt: `roboflow-counter`  
Repository: [https://github.com/miguellcostillia/roboflow-counter](https://github.com/miguellcostillia/roboflow-counter)

Bitte:

- Repository laden & internen Projektkontext initialisieren  
- `docs/AI_Playbook.md` befolgen (Kommunikations- & Formatregeln)  
- `docs/PROJECT_STATE.md` prüfen (aktueller Entwicklungsstand)  
- `docs/CHANGELOG.md` berücksichtigen  
- `docs/ERROR_LOG.md` & `docs/SUCCESS_LOG.md` beachten (letzter Teststatus)  
- `docs/SESSION_START.md` wird als Einstiegspunkt genutzt  
- Nur 1 aktiver Branch laut Playbook: **main**

---

### 🧩 Projektumgebung

```bash
cd ~/projects/roboflow-counter
source .venv/bin/activate
```

**Python:** 3.12  
**GPU:** NVIDIA RTX A4000  
**CUDA:** 12.9  
**OpenCV:** 4.10 (mit CUDA/DNN)  
**MediaMTX:** aktiv auf Port 8554  
**Hauptdienste:**
- `roboflow-highlight.service` — Motion-Highlight Stream  
- `larvacounter-dump-clean.service` — Frame-Export + Cleanup  
- `roboflow-tracker.service` *(optional)* — IoU-Tracking / Roboflow-Inference  

---

### ⚙️ Antwortformat-Regeln

- Kurz und präzise  
- Code nur in **Patch- oder Command-Blöcken**  
- PR-Workflow beibehalten (`feat:`, `fix:`, `docs:` etc.)  
- Entscheidungen gemäß *AI_Playbook.md* treffen  
- Keine Wiederholungen, keine unnötigen Fragen  
- Nur bestätigte Files/Komponenten aus `main` berücksichtigen  

---

### 🧠 Projektkontext aktiv

- Highlight-Pipeline stabil  
- Dump- & Cleanup-System aktiv  
- Tracker integriert (Basisversion, Overlay in Arbeit)  
- GPU-Inferenz getestet (CUDA 12.9 + A4000)  
- Config-System (`config.loader`) und `.env` funktional  

---

Sage **„✅ ready“**, wenn Projekt geladen und Kontext aktiv ist.
