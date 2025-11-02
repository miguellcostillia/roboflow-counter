from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict
import yaml

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # optional

DEFAULT_CFG_PATH = Path("config/config.yml")
DEFAULT_ENV_PATH = Path("config/.env")

def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _load_env(env_path: Path) -> Dict[str, str]:
    # load variables from file into process env (if python-dotenv available)
    if load_dotenv is not None and env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
    # pick only keys we know about (extend easily)
    keys = [
        "ROBOFLOW_API_KEY",
        "RTSP_USERNAME", "RTSP_PASSWORD",
        "INFLUX_TOKEN",
        "OPCUA_ENDPOINT", "OPCUA_USERNAME", "OPCUA_PASSWORD",
    ]
    return {k: v for k, v in os.environ.items() if k in keys}

def _merge_env_over_yaml(cfg: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    # Ensure nested dicts exist
    def ensure(path: str) -> Dict[str, Any]:
        cur = cfg
        for p in path.split("."):
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        return cur

    # Map env -> cfg paths
    mapping = {
        "ROBOFLOW_API_KEY": "roboflow",
        "INFLUX_TOKEN": "metrics.influx",
        "RTSP_USERNAME": "input",
        "RTSP_PASSWORD": "input",
    }
    for env_key, val in env.items():
        if env_key not in mapping or not val:
            continue
        tgt = ensure(mapping[env_key])
        if env_key == "ROBOFLOW_API_KEY":
            tgt["api_key"] = val
        elif env_key == "INFLUX_TOKEN":
            tgt["token"] = val
        elif env_key in ("RTSP_USERNAME", "RTSP_PASSWORD"):
            tgt[env_key.lower()] = val

    # If username/password provided and rtsp_url present but without creds, inject
    inp = cfg.get("input", {})
    url = inp.get("rtsp_url")
    user = inp.get("rtsp_username") or inp.get("username")
    pwd = inp.get("rtsp_password") or inp.get("password")
    if url and user and pwd and "@" not in url:
        # inject creds: rtsp://user:pass@host/...
        try:
            if "rtsp://" in url:
                prefix, rest = url.split("rtsp://", 1)
                if "@" not in rest:
                    if "rtsps://" in url:
                        # unlikely mixed, but guard anyway
                        pass
                    cfg["input"]["rtsp_url"] = f"rtsp://{user}:{pwd}@{rest}"
            elif "rtsps://" in url:
                prefix, rest = url.split("rtsps://", 1)
                if "@" not in rest:
                    cfg["input"]["rtsp_url"] = f"rtsps://{user}:{pwd}@{rest}"
        except Exception:
            # don't fail config on URL compose
            pass

    return cfg

def load_config(cfg_path: str | Path = DEFAULT_CFG_PATH,
                env_path: str | Path = DEFAULT_ENV_PATH) -> Dict[str, Any]:
    """
    Load YAML config and overlay with .env secrets (ENV wins).
    Missing files are tolerated; returns {} if none exist.
    """
    cfg_path = Path(cfg_path)
    env_path = Path(env_path)
    yaml_cfg = _read_yaml(cfg_path)
    env_map = _load_env(env_path)
    return _merge_env_over_yaml(yaml_cfg, env_map)
