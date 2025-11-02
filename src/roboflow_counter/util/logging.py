from __future__ import annotations
import logging, sys
from typing import Optional

_LEVELS = {"CRITICAL":50,"ERROR":40,"WARNING":30,"INFO":20,"DEBUG":10,"NOTSET":0}

def setup_logger(name: str = "roboflow_counter", level: str = "INFO") -> logging.Logger:
    lvl = _LEVELS.get(str(level).upper(), 20)
    logger = logging.getLogger(name)
    logger.setLevel(lvl)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
        h.setFormatter(fmt)
        logger.addHandler(h)
    return logger

def get_level_name(level: int) -> str:
    for k,v in _LEVELS.items():
        if v == level: return k
    return str(level)
