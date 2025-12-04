#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entry-Point für den Larva-Watchdog.
- Setzt sys.path so, dass `tools` aus ./src importiert werden kann.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# WICHTIG: watchdog liegt in src/tools/watchdog.py
from tools.watchdog import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
