# User Guide — roboflow-counter

## Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

## Konfigurationsstruktur
config/
 ├── config.yml      → versionierte Pipeline-/Projekt-Config
 └── .env            → secrets (nicht committen)

Hinweis:
ENV > YAML — .env Werte überschreiben config.yml
Templates folgen: config.example.yml & .env.example

## Nützliche CLI-Kommandos
python -m roboflow_counter.main hello
python -m roboflow_counter.main show_config
python -m roboflow_counter.main cuda-check
python -m roboflow_counter.main rtsp-test <URL>

## Git-Workflow
git switch main && git pull
git switch -c feat/<task>-YYYY-MM-DD
git add .
git commit -m "feat: ..."
git push -u origin feat/<task>-YYYY-MM-DD

## Projekt-Gedächtnis Dateien
docs/PROJECT_STATE.md     → aktueller Stand / TODO
docs/ERROR_LOG.md         → letzte Fehlermeldungen
docs/SUCCESS_VERSION.md   → letzte stabile Commit-ID
