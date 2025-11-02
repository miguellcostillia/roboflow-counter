from pathlib import Path
from src.roboflow_counter.config.loader import load_config, validate_config, load_and_validate

def test_env_over_yaml(tmp_path: Path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "config.yml").write_text("""
input:
  rtsp_url: "rtsp://example.com/stream"
  rtsp_transport: "tcp"
pipeline:
  fps_target: 5
roboflow:
  api_key: "from_yaml"
""", encoding="utf-8")
    (cfg_dir / ".env").write_text("ROBOFLOW_API_KEY=from_env\n", encoding="utf-8")
    cfg = load_config(cfg_dir/"config.yml", cfg_dir/".env")
    assert cfg["roboflow"]["api_key"] == "from_env"  # ENV wins
    ok, msg = validate_config(cfg)
    assert ok, msg
    cfg2 = load_and_validate(cfg_dir/"config.yml", cfg_dir/".env")
    assert cfg2["input"]["rtsp_url"].startswith("rtsp://")
