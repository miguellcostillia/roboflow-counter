# ✅ Session-Start-Checkliste

Ziel: Garantiert sauberer Start in der richtigen Umgebung & Branch.

1) SSH & Repo
   - [ ] `ssh manager@<server>`
   - [ ] `cd ~/projects/roboflow-counter`
   - [ ] `source .venv/bin/activate` (prüfen: `which python` -> .venv)

2) Git Sync
   - [ ] `git fetch --all --prune`
   - [ ] Aktiven Feature-Branch wählen (Regel: nur 1 aktiv):
         `git switch <YYYYMMDD-HHMM>_feat-...`
   - [ ] `git pull --ff-only`

3) Config prüfen
   - [ ] `ls config/` (Templates vorhanden?)
   - [ ] Falls nötig: `cp config/config.example.yml config/config.yml`
   - [ ] Falls nötig: `cp config/.env.example config/.env` (Secrets füllen!)

4) Schnelltests
   - [ ] `.venv/bin/python -m pytest -q` (falls Tests existieren)
   - [ ] `python -m roboflow_counter.main --help`
