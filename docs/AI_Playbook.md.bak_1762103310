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



## Vorbereitung vor größeren Änderungen
Vor jedem größeren Change immer prüfen:
- `docs/CHANGELOG.md` – Verlauf & letzte wichtige Änderungen
- `docs/PROJECT_STATE.md` – aktueller Task / Next step
- `docs/ERROR_LOG.md` – letzte Fehlermeldungen
- `docs/SUCCESS_VERSION.md` – letzte stabile Commit-ID

---

## Arbeits-Checklisten

- **Session-Start:** Siehe `docs/SESSION_START.md`
- **Session-Ende:** Siehe `docs/SESSION_END.md`
- **PR-Workflow:** Pull Requests werden im Browser erstellt und gemerged. Vorlage: `.github/pull_request_template.md`

**Grundsatz:** Immer nur `main` + 1 aktiver Feature-Branch. Nach Merge: Branch archivieren & löschen (unsichtbar halten).


## Push & Merge Regeln
- **Nie direkt auf `main` pushen** (lokal blockiert durch Hook).
- **Befehl:** `prup` → pusht aktuellen Branch und öffnet/erstellt PR.
- **Nach Merge:** `finish_branch` → main aktualisieren & Feature-Branch löschen.
- **Wenn User sagt:** „pushen wir das ins main“ → **immer** PR-Workflow verwenden, keine direkten Merges.

### Schutzregeln (lokal)
- Commits/Pushes auf `main` sind lokal blockiert (Git-Hooks).
- Workflow: **Feature-Branch → PR → Browser-Merge → finish_branch**.
- Wenn der User sagt „pushen wir das ins main“, werden **immer** PR-Befehle geliefert (kein Direkt-Merge).
