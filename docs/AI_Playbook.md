# Playbook – KI-Zusammenarbeit & Projektregeln

Dieses Playbook beschreibt, wie die KI mit diesem Repo arbeitet, damit Kontextverlust im Chat kein Problem mehr ist.

## Immer zuerst lesen
- `docs/PROJECT_STATE.md` → aktueller Arbeitsstand (Aktueller Branch, „Next step“)
- `docs/ERROR_LOG.md` → letzte Fehlermeldungen / offene Bugs
- `docs/SUCCESS_VERSION.md` → SHA der letzten 100% funktionierenden Version

## Branch-Strategie
- Features: `feat/<name>-YYYY-MM-DD`
- Fixes: `fix/<name>-YYYY-MM-DD`
- Docs: `docs/<name>-YYYY-MM-DD` oder `docs-<name>-YYYY-MM-DD`
- Cleanup: `cleanup-YYYY-MM-DD`
- Kein direktes Commit auf `main` (außer Bootstrap/Strukturphase).

## Dokumentationspflicht (auto-aktualisieren)
Wenn neue Funktionen/Workflows entstehen:
- `CHANGELOG.md` ergänzen
- `docs/USER_GUIDE.md` aktualisieren (wenn Nutzungsablauf betroffen)
- `docs/PLAYBOOK.md` aktualisieren (wenn KI-Verhalten/Regeln betroffen)
- Docs im **gleichen PR** wie der Code miterledigen.

## User-Präferenzen (Michael)
- Terminal-first, keine IDE erforderlich.
- `cat` zum Anzeigen von Code (statt Editor/Tree-Spam).
- Möglichst kleine, saubere Patches/PRs; keine langen Codeblöcke im Chat.
- Struktur: `config/` als zentraler Ort für Konfiguration.
- **Hybrid-Konfiguration**: 
  - `config/config.yml` für strukturierte Pipeline-Settings (versioniert).
  - `config/.env` für Secrets / Deployment-Spezifika (nicht versioniert).
- In Zukunft Branch-Namen mit Datum.

## Konfig-Philosophie
- YAML für komplexe, versionierbare Einstellungen (Pipelines, Kamera, Model-Settings, FPS/Buffer).
- `.env` für Secrets (Roboflow API Key, RTSP-Passwörter, ggf. Influx/OPC-UA).
- ENV überschreibt YAML (Priorität: ENV > YAML).
- Templates: `config/config.example.yml` und `config/.env.example`.

## Arbeitsablauf der KI
1. Repo-Stand prüfen, oben genannte Dateien lesen.
2. Changes planen und kurz zusammenfassen.
3. Feature-Branch anlegen (mit Datum).
4. Kleine, atomare Commits; sinnvolle Messages.
5. Docs aktualisieren (Playbook/User Guide/Changelog).
6. PR erstellen, klare Testhinweise & Befehle dazuschreiben.
7. Nach Merge: optional Cleanup-Branch oder nächste Aufgabe in `PROJECT_STATE.md` notieren.

## Sicherheitsnetz
- Keine Struktur-Refactorings ohne kurze Rückfrage (außer vereinbarte Cleanup-Branches).
- Keine Secrets in Commits/PRs.
- Keine großen Binärdateien einchecken (Videos, Modelle) – dafür später Storage/Release-Anlage.

## Bekannte Tools/Kommandos im Projekt
- CLI-Kommandos via `python -m roboflow_counter.main ...` (z. B. `hello`, `show_config`, `cuda_check`, `rtsp-test`).
- CUDA-Check: `nvidia-smi` + optional OpenCV CUDA count.
- RTSP-Tests: `rtsp-test <URL>` mit Positionsargument (kein `--url`).

## Zielbild
- Stabiler, reproduzierbarer Workflow ohne Chat-Abhängigkeit.
- Repo ist das Gedächtnis (STATE/LOG/SUCCESS).
- KI kann jederzeit anhand der Doku kontextvoll weiterarbeiten.
