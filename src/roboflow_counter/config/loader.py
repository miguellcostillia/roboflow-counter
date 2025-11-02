from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, Tuple
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
    if load_dotenv is not None and env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
    keys = [
        "ROBOFLOW_API_KEY",
        "RTSP_USERNAME", "RTSP_PASSWORD",
        "INFLUX_TOKEN",
        "OPCUA_ENDPOINT", "OPCUA_USERNAME", "OPCUA_PASSWORD",
    ]
    return {k: v for k, v in os.environ.items() if k in keys}

def _ensure_path(cfg: Dict[str, Any], dotted: str) -> Dict[str, Any]:
    cur = cfg
    for p in dotted.split("."):
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    return cur

def _merge_env_over_yaml(cfg: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    mapping = {
        "ROBOFLOW_API_KEY": "roboflow",
        "INFLUX_TOKEN": "metrics.influx",
        "RTSP_USERNAME": "input",
        "RTSP_PASSWORD": "input",
    }
    for env_key, val in env.items():
        if env_key not in mapping or not val:
            continue
        tgt = _ensure_path(cfg, mapping[env_key])
        if env_key == "ROBOFLOW_API_KEY":
            tgt["api_key"] = val
        elif env_key == "INFLUX_TOKEN":
            tgt["token"] = val
        elif env_key in ("RTSP_USERNAME", "RTSP_PASSWORD"):
            tgt[env_key.lower()] = val

    # inject creds into rtsp_url if user+pass provided
    inp = cfg.get("input", {}) or {}
    url = inp.get("rtsp_url")
    user = inp.get("rtsp_username") or inp.get("username")
    pwd  = inp.get("rtsp_password") or inp.get("password")
    if url and user and pwd and "@" not in url:
        try:
            if url.startswith("rtsp://"):
                rest = url[len("rtsp://"):]
                if "@" not in rest:
                    cfg["input"]["rtsp_url"] = f"rtsp://{user}:{pwd}@{rest}"
            elif url.startswith("rtsps://"):
                rest = url[len("rtsps://"):]
                if "@" not in rest:
                    cfg["input"]["rtsp_url"] = f"rtsps://{user}:{pwd}@{rest}"
        except Exception:
            pass
    return cfg

def load_config(cfg_path: str | Path = DEFAULT_CFG_PATH,
                env_path: str | Path = DEFAULT_ENV_PATH) -> Dict[str, Any]:
    cfg_path = Path(cfg_path)
    env_path = Path(env_path)
    yaml_cfg = _read_yaml(cfg_path)
    env_map = _load_env(env_path)
    return _merge_env_over_yaml(yaml_cfg, env_map)

def validate_config(cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """Return (ok, message)."""
    if not isinstance(cfg, dict):
        return False, "Config root must be a mapping/dict."
    inp = cfg.get("input") or {}
    url = inp.get("rtsp_url")
    if not url or not isinstance(url, str):
        return False, "input.rtsp_url missing (provide in config.yml or CLI)."
    trans = (inp.get("rtsp_transport") or "tcp")
    if trans not in ("tcp", "udp"):
        return False, "input.rtsp_transport must be 'tcp' or 'udp'."
    pipe = cfg.get("pipeline") or {}
    fps = pipe.get("fps_target", 0)
    if fps is not None and fps != 0 and (not isinstance(fps, (int, float)) or fps < 0):
        return False, "pipeline.fps_target must be >=0 (0=off)."
    return True, "ok"

def load_and_validate(cfg_path: str | Path = DEFAULT_CFG_PATH,
                      env_path: str | Path = DEFAULT_ENV_PATH) -> Dict[str, Any]:
    cfg = load_config(cfg_path, env_path)
    ok, msg = validate_config(cfg)
    if not ok:
        raise ValueError(f"Invalid config: {msg}")
    return cfg
