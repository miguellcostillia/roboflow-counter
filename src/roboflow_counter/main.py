#!/usr/bin/env python3
from __future__ import annotations
import os
from typing import Optional

# --- Typer optional machen ---------------------------------------------------
try:
    import typer  # type: ignore
    _HAS_TYPER = True
except Exception:  # ImportError etc.
    _HAS_TYPER = False
    typer = None  # type: ignore

from rich import print as rprint
from rich.table import Table

from .config.loader import load_and_validate
from .stream.highlight import run_highlight_loop

# -----------------------------------------------------------------------------
# Hilfsfunktionen (unverändert)
# -----------------------------------------------------------------------------
def _resolve_urls(cfg_path: str, env_path: str, url_in_cli: Optional[str], url_out_cli: Optional[str]):
    cfg = load_and_validate(cfg_path, env_path)
    ui = url_in_cli or (cfg.get("input") or {}).get("rtsp_url")
    uo = url_out_cli or (cfg.get("output") or {}).get("rtsp_url")
    if not ui or not uo:
        raise ValueError("missing rtsp url")
    return ui, uo, cfg

def _apply_env_from_cfg(cfg):
    hi = cfg.get("highlight") or {}
    mg = hi.get("gain", 0.70)
    os.environ["HL_GAIN"] = str(mg)
    ga = (hi.get("gauss") or {}).get("ksize", 7)
    os.environ["HL_GAUSS"] = str(ga)

    mo = cfg.get("motion") or {}
    os.environ["HL_EMA_ALPHA"] = str(mo.get("ema_alpha", 0.05))
    os.environ["HL_THRESH"] = str(mo.get("threshold", 12))

    # Hintergrund-Abdunklung
    bk = float(cfg.get("background_darken", 0.0) or 0.0)
    os.environ["HL_DARKEN"] = str(bk)

    rg = cfg.get("region") or {}
    os.environ["HL_MIN_REGION"] = str(rg.get("min_pixels", 50))
    os.environ["HL_GROW_ITERS"] = str(rg.get("grow_iters", 2))
    os.environ["HL_GROW_EDGE_T"] = str(rg.get("edge_threshold", 20))
    os.environ["HL_GROW_GRAY_DELTA"] = str(rg.get("gray_delta", 0))

    rt = cfg.get("runtime") or {}
    return float(rt.get("fps", 0.0)), int(rt.get("open_timeout_ms", 8000))

# -----------------------------------------------------------------------------
# Fallback-CLI (ohne Typer): immer run-highlight aus config
# -----------------------------------------------------------------------------
def _fallback_run():
    cfg_path = os.environ.get("RF_CFG", "config/config.yml")
    env_file = os.environ.get("RF_ENV", "config/.env")
    url_in, url_out, cfg = _resolve_urls(cfg_path, env_file, None, None)
    fps_cfg, timeout_cfg = _apply_env_from_cfg(cfg)
    print(f"Motion-Highlight {url_in} → {url_out}")
    run_highlight_loop(url_in, url_out, log="INFO", fps_target=fps_cfg, open_timeout_ms=timeout_cfg)

# -----------------------------------------------------------------------------
# Typer-CLI (wenn Typer vorhanden)
# -----------------------------------------------------------------------------
if _HAS_TYPER:
    app = typer.Typer(help="Roboflow Counter CLI")

    @app.command("show-config")
    def show_config(cfg_path: str = "config/config.yml", env_file: str = "config/.env"):
        cfg = load_and_validate(cfg_path, env_file)
        t = Table(title="Config")
        for sec, k, v in [
            ("input", "rtsp_url", (cfg.get("input") or {}).get("rtsp_url")),
            ("output", "rtsp_url", (cfg.get("output") or {}).get("rtsp_url")),
            ("highlight", "gain", (cfg.get("highlight") or {}).get("gain")),
            ("highlight.gauss", "ksize", (cfg.get("highlight") or {}).get("gauss", {}).get("ksize")),
            ("motion", "ema_alpha", (cfg.get("motion") or {}).get("ema_alpha")),
            ("region", "min_pixels", (cfg.get("region") or {}).get("min_pixels")),
            ("region", "grow_iters", (cfg.get("region") or {}).get("grow_iters")),
            ("region", "edge_threshold", (cfg.get("region") or {}).get("edge_threshold")),
            ("region", "gray_delta", (cfg.get("region") or {}).get("gray_delta")),
            ("runtime", "fps", (cfg.get("runtime") or {}).get("fps")),
        ]:
            t.add_row(sec, k, str(v))
        rprint(t)

    @app.command("run-highlight")
    def run_highlight(
        url: Optional[str] = None,
        out_url: Optional[str] = None,
        log_level: str = "INFO",
        cfg_path: str = "config/config.yml",
        env_file: str = "config/.env",
        fps_target_cli: float = 0.0,
        open_timeout_ms_cli: int = 0,
    ):
        ui, uo, cfg = _resolve_urls(cfg_path, env_file, url, out_url)
        fps_cfg, timeout_cfg = _apply_env_from_cfg(cfg)
        fps = fps_target_cli if fps_target_cli > 0 else fps_cfg
        timeout = open_timeout_ms_cli if open_timeout_ms_cli > 0 else timeout_cfg

        print(f"Motion-Highlight {ui} → {uo}")
        run_highlight_loop(ui, uo, log=log_level, fps_target=fps, open_timeout_ms=timeout)

    # --- Inference-Kommandos nur importieren, wenn benutzt ---
    @app.command("infer-smoke")
    def cli_infer_smoke(
        cfg_path: str = "config/config.yml",
        env_file: str = "config/.env",
    ):
        # Lazy import, um unnötige Abhängigkeiten zu vermeiden
        from .stream import inference as rf_infer  # type: ignore
        raise SystemExit(rf_infer.run_smoke())

    @app.command("infer-rtsp")
    def cli_infer_rtsp(
        source: Optional[str] = typer.Option(
            None, "--source",
            help="RTSP/RTSPS Quelle; Default: output.rtsp_url aus config"
        ),
        cfg_path: str = "config/config.yml",
        env_file: str = "config/.env",
    ):
        from .stream import inference as rf_infer  # type: ignore
        raise SystemExit(rf_infer.run_rtsp(source))

    def main():
        app()

else:
    # Kein Typer vorhanden: Service/ohne-CLI-Fall → direkt run-highlight
    def main():
        _fallback_run()

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
