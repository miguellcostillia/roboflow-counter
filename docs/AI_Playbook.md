# AI_Playbook — KI-Zusammenarbeit & Projektregeln

Dieses Playbook beschreibt, wie Mensch & KI in diesem Repo zusammenarbeiten, damit Kontextverlust im Chat kein Problem mehr ist und Änderungen reproduzierbar bleiben.

## Immer zuerst lesen
- `docs/PROJECT_STATE.md` – aktueller Arbeitsstand (Branch, „Next step“)
- `docs/ERROR_LOG.md` – letzte Fehlermeldungen / offene Bugs
- `docs/SUCCESS_VERSION.md` – SHA der letzten 100 % funktionierenden Version

## Branch-Strategie
- Features: `feat/<name>-YYYY-MM-DD`
- Fixes: `fix/<name>-YYYY-MM-DD`
- Doku: `docs/<name>-YYYY-MM-DD` (oder `docs-<name>-YYYY-MM-DD`)
- Cleanup: `cleanup-YYYY-MM-DD`
- Kein direkter Commit auf `main` (außer in der initialen Strukturphase).

## Dokumentationsregel (verpflichtend)
Bei **jeder wichtigen Änderung** im Projekt **müssen** aktualisiert werden:
- `docs/USER_GUIDE.md`
- `docs/AI_Playbook.md`

Wenn Code, Struktur oder Workflow geändert wird, aber die Doku nicht angepasst ist, gilt der PR als **unvollständig** und darf nicht nach `main` gemerged werden.  
Die KI ist verantwortlich, diese Dateien vorzuschlagen/zu ergänzen, sobald neue Features, Workflows oder Benutzerpräferenzen entstehen. Änderungen an Code und Doku sollen im **gleichen PR** landen.

### ✅ Pull-Requests erstellen (Workflow)

- PRs werden per Skript erstellt: `./tools/pr.sh`
- Das Skript pusht den aktuellen Feature-Branch und erstellt einen **Draft-PR** gegen `main`.
- Merge erfolgt **manuell im Browser** (kein Auto-Merge).
- Nie auf `main` arbeiten (keine Commits/Pushes/PRs von `main`).


## User-Präferenzen (Michael)
- Terminal-first Workflow, keine IDE nötig.
- `cat` zum Anzeigen von Code (statt Editor/Tree-Spam).
- Kleine, saubere Patches/PRs; keine riesigen Codeblöcke im Chat.
- Konfiguration zentral unter `config/`.
- **Hybrid-Config**:
  - `config/config.yml` → strukturierte Pipeline-Settings (versioniert)
  - `config/.env` → Secrets/Deployment-Werte (nicht in Git)
- ENV-Werte überschreiben YAML (Priorität: **ENV > YAML**).
- Branch-Namen mit Datum.

## Konfig-Philosophie
- YAML für komplexe, versionierbare Einstellungen (Kameras, Modelle, FPS/Buffer, Pipelines).
- `.env` für Secrets (Roboflow API Key, RTSP-Passwörter, später ggf. Influx/OPC-UA).
- Templates: `config/config.example.yml` und `config/.env.example` (für neue Deployments).

## Arbeitsablauf der KI
1. Repo-Stand prüfen: STATE/ERROR/SUCCESS lesen.
2. Änderungsvorschlag kurz skizzieren (Ziele, Dateien, Auswirkungen).
3. Feature-Branch anlegen (mit Datum).
4. Kleine, atomare Commits mit klaren Messages.
5. Doku aktualisieren (Playbook/User Guide/Changelog).
6. PR erstellen inkl. Test-Hinweisen und Shell-Befehlen.
7. Nach Merge: nächsten Schritt in `PROJECT_STATE.md` notieren.

## Sicherheitsnetz
- Keine Struktur-Refactorings ohne kurze Rückfrage (außer vereinbarte Cleanup-Branches).
- Keine Secrets in Commits/PRs.
- Keine großen Binärdateien einchecken (Videos/Modelle) – dafür später Releases/Storage.

## Bekannte Tools/Kommandos im Projekt
- CLI: `python -m roboflow_counter.main <command>`
  - `hello`, `show_config`, `cuda-check`, `rtsp-test <URL>` (URL als Positionsargument, kein `--url`).
- CUDA-Check nutzt `nvidia-smi` + (optional) OpenCV CUDA device count.

## Zielbild
- Stabiler, reproduzierbarer Workflow ohne Chat-Abhängigkeit.
- Repo ist das Gedächtnis (STATE/ERROR/SUCCESS + Playbook/User Guide).
- KI kann jederzeit anhand der Doku kontextvoll weiterarbeiten.

## Branch-Namenskonvention (zeitlich sortiert)

Alle neuen Branches müssen mit einem Zeitstempel im Format `YYYYMMDD-HHMM` beginnen,
damit Branches chronologisch sortierbar sind und Workflow-Navigation erleichtert wird.

**Format:**
<YYYYMMDD>-<HHMM>_<type>-<name>

**Beispiele:**
20251102-2230_feat-rtsp-test
20251102-2232_docs-playbook
20251103-0710_fix-config-loader

**Branch-Typen:**
- feat    = neues Feature
- fix     = Bugfix
- docs    = Dokumentation
- cleanup = Aufräumen / Strukturpflege

**Regel:**

- Jeder neue Branch MUSS diesen Zeitpräfix haben.
- Änderungen gelten als unvollständig, wenn diese Regel ignoriert wird.

---

## 📁 Git-Ordner Architekturregel (2025-11-02)

- Es gibt **einen zentralen Ordner** für alles, was mit Git-Workflow zu tun hat:


Enthält:
- Hooks-Quellen
- Branch-Workflow-Skripte (`nb`, `prup`, `finish_branch`, Maintenance-Scripts)
- Git-Dokumentation & Policies
- Templates (PR/Bug Report Templates falls später genutzt)
- Git-Driver/Config Notes

- **Keine Git-bezogenen Dateien oder Hilfsskripte außerhalb von `/Git/`.**
- `.git` bleibt natürlich unverändert (git intern) — **aber alle Tools drumherum gehören in `/Git/`.**
- Wenn Git-Dateien außerhalb gefunden werden → AI muss nachfragen und anbieten, sie zu verschieben.

**Ziel:**  
Zentrale, klare Struktur.  
Git-Workflow ist jederzeit nachvollziehbar & versioniert.


## Vorbereitung vor größeren Änderungen
Vor jedem größeren Change immer prüfen:
- `docs/CHANGELOG.md` – Verlauf & letzte wichtige Änderungen
- `docs/PROJECT_STATE.md` – aktueller Task / Next step
- `docs/ERROR_LOG.md` – letzte Fehlermeldungen
- `docs/SUCCESS_VERSION.md` – letzte stabile Commit-ID

---


## 🧠 Branch-Verhalten der AI (2025-11-02)

- Die AI erstellt **nie automatisch einen Branch**.
- Wenn der User auf `main` ist, fragt die AI IMMER:

  > Du bist auf `main`. Willst du…
  > 1) zur letzten Feature-Branch zurück?
  > 2) einen neuen Feature-Branch erstellen?
  > 3) nur `main` aktualisieren und nichts ändern?

- Wenn der aktuelle Branch **nicht `main`** ist:
  - Weiterarbeiten in diesem Branch (standard)
  - Nur auf Nachfrage branch wechseln

- **Nie automatisch commits, pushes oder branch deletes**
- **Nie `prup` auf `main`**
- Feature-Branch Workflow:
  1 branch aktiv  
  Merge via PR  
  Danach `finish_branch`

**Ziel:** volle Kontrolle, AI darf nur assistieren, nie Git-Aktionen erzwingen.

---

## 🔒 Repository Architecture Rules (added 2025-11-02)

### Root folder structure is protected

Die folgenden Top-Level-Ordner sind **geschützt** und dürfen **nur nach expliziter Bestätigung** des Users geändert werden:
- `config/` – User- und Systemkonfiguration
- `docs/` – Dokumentation (Handbücher, Playbook, Logs)
- `src/` – Anwendungscode
- `tests/` – Tests
- `tools/` – Entwickler-Werkzeuge
- `Git/` – **alle Git-bezogenen Dateien** (Hooks, Hilfsskripte, Templates, Meta-Tools)

**Regel:**  
> Änderungen an der Root-Projektstruktur nur in Ausnahmefällen.  
> **Vor jeder Änderung fragt die AI nochmals um ausdrückliche Bestätigung.**

### Git folder rule

verwende Zentrales Git-Verzeichnis für alle files die mit git zusammenhängen


Beinhaltet:
- Git-Hooks
- Workflow-Skripte (`prup`, `finish_branch`, `nb`)
- Git-Config/Presets
- Repository-Maintenance-Skripte

**Hinweis:** Das Verschieben bestehender Git-Dateien (z. B. `.githooks/`) erfolgt **nur nach separater Bestätigung** in einem eigenen PR.


