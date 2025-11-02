# ✅ Session-End-Checkliste

Ziel: Sauberer Abschluss, nachvollziehbarer Stand, kein Chaos morgen.

1) Kurztests
   - [ ] `.venv/bin/python -m pytest -q` (sofern relevant)
   - [ ] Manuelle Kernfunktion kurz anstoßen (falls sinnvoll)

2) Git Commit
   - [ ] `git status`
   - [ ] `git add -A`
   - [ ] `git commit -m "<kurzer, klarer Status>"`
   - [ ] `git push` (Upstream gesetzt? Falls nicht: `git push -u origin HEAD`)

3) Doku/Meta aktualisieren (falls relevant)
   - [ ] `docs/PROJECT_STATE.md` (aktueller Stand & Next Steps)
   - [ ] `docs/AI_Playbook.md` (Regeln/Präferenzen angepasst?)
   - [ ] `docs/CHANGELOG.md` (wichtige Änderungen eingetragen)

4) Branch-Hygiene
   - [ ] Nur **1** aktiver Feature-Branch offen (Regel!)
   - [ ] Merge ausschließlich via **Pull Request im Browser**
   - [ ] Nach Merge: Feature-Branch **archivieren & löschen** (siehe Playbook)

5) Notiz fürs Morgen (im Commit-Text oder PROJECT_STATE):
   - [ ] „Morgen starten bei: …“
