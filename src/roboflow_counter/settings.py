import os
from pathlib import Path
from dotenv import load_dotenv
import yaml
from .config.schema import Config, SecretsCfg

def load_config(cfg_path: str = "config/config.yml", env_file: str = ".env") -> Config:
    # .env laden, falls vorhanden (für Secrets)
    if env_file and Path(env_file).exists():
        load_dotenv(env_file)

    # YAML laden
    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # Secrets aus ENV
    rf = os.environ.get("ROBOFLOW_API_KEY")
    if not rf:
        raise RuntimeError("ROBOFLOW_API_KEY fehlt — in .env eintragen")

    raw["secrets"] = SecretsCfg(roboflow_api_key=rf).model_dump()

    return Config(**raw)
