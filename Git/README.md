# Git Workspace

Zentraler Ablageort für alle Git-bezogenen Artefakte:

- `hooks/` – Kopien/Referenzen der verwendeten Hooks (aktive Hooks werden weiterhin über `core.hooksPath` gesteuert)
- `scripts/` – Workflow-Helfer (z. B. `nb`, `prup`, `finish_branch`)
- weitere Repo-Maintenance-Tools (Branch-Aufräumen, Checks, usw.)

**Policy (laut AI_Playbook):**
- Root-Struktur (`config/`, `docs/`, `src/`, `tests/`, `tools/`, `Git/`) ist geschützt – Änderungen nur nach ausdrücklicher Bestätigung.
- Standard-Workflow: **nur `main` + 1 aktiver Feature-Branch**, PR-only, nie direkt auf `main` pushen.
- Doku-Änderungen bevorzugt mit `nano`/`cat`, keine großen Here-Docs.

**Hinweis:** Ein späterer Umzug aktiver Hooks nach `Git/hooks` (Änderung von `core.hooksPath`) erfolgt nur nach separater Bestätigung und eigenem PR.
