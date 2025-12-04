#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from roboflow_counter.config.loader import load_config
from roboflow_counter.stream.tracker import run

def main():
    # lädt config/config.yml (dein Loader macht das bereits korrekt + .env)
    cfg = load_config()
    # 0 = endlos laufen lassen
    return run(cfg, duration_sec=0)

if __name__ == "__main__":
    sys.exit(main() or 0)
