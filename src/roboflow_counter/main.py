import typer
from rich import print
from .settings import load_config
from .config.loader import load_and_validate

app = typer.Typer(add_completion=False)

@app.command()
def hello(name: str = "world"):
    print(f"[bold green]Hello {name}![/bold green] — Roboflow Counter ready 🚀")

@app.command()
def show_config(cfg_path: str = "config/config.yml", env_file: str = "config/.env"):
    cfg = load_config(cfg_path, env_file)
    print("[bold]Active Config:[/bold]")
    print(cfg.model_dump())

@app.command()
def cuda_check():
    """Check CUDA / GPU status."""
    import subprocess
    print("[bold cyan]Checking CUDA / GPU...[/bold cyan]")
    try:
        r = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if r.returncode == 0:
            print("[bold green]GPU detected via nvidia-smi ✅[/bold green]")
            print(r.stdout)
        else:
            print("[bold red]nvidia-smi failed[/bold red]")
            print(r.stderr)
    except FileNotFoundError:
        print("[bold red]nvidia-smi not found[/bold red] (NVIDIA drivers missing?)")
    try:
        import cv2
        c = cv2.cuda.getCudaEnabledDeviceCount()
        print(f"OpenCV CUDA devices: {c}")
        if c == 0:
            print("[yellow]OpenCV installed but no CUDA devices found[/yellow]")
    except Exception as e:
        print(f"[red]OpenCV CUDA unavailable[/red] ({e})")

@app.command(name="run-stream")
def run_stream(
    url: str | None = typer.Option(None, help="RTSP(S) URL; if omitted, taken from config"),
    cfg_path: str = typer.Option("config/config.yml", help="Path to YAML config"),
    env_file: str = typer.Option("config/.env", help="Path to .env (secrets)"),
    fps_target: float = typer.Option(0.0, help="Target FPS throttle (0=off)"),
    transport: str = typer.Option("tcp", help="RTSP transport: tcp|udp"),
    timeout_ms: int = typer.Option(5000, help="Open timeout in ms"),
    log_level: str = typer.Option("INFO", help="Log level: DEBUG|INFO|WARNING|ERROR"),
):
    """Open RTSP stream, print smoothed FPS, reconnect on failure."""
    from .stream.rtsp import run_rtsp_loop
    cfg = load_and_validate(cfg_path, env_file)
    if url is None:
        url = (cfg.get("input", {}) or {}).get("rtsp_url")
    if not url:
        print("[bold red]No RTSP URL provided or found in config.input.rtsp_url[/bold red]")
        raise typer.Exit(code=2)
    print(f"[bold cyan]Opening stream[/bold cyan]: {url}")
    print(f"[cyan]transport={transport}, timeout={timeout_ms} ms, fps_target={fps_target}, log={log_level}[/cyan]")
    try:
        run_rtsp_loop(
            url=url,
            fps_target=(fps_target if fps_target > 0 else None),
            open_timeout_ms=timeout_ms,
            transport=transport,
            log_level=log_level,
        )
    except KeyboardInterrupt:
        print("[yellow]Interrupted by user[/yellow]")

@app.command(name="run-highlight")
def run_highlight(
    url: str | None = typer.Option(None, help="RTSP(S) IN; else from config"),
    out_url: str | None = typer.Option(None, help="RTSP OUT; else from config"),
    cfg_path: str = typer.Option("config/config.yml", help="Config YAML"),
    env_file: str = typer.Option("config/.env", help=".env (secrets)"),
    fps_target: float = typer.Option(0.0, help="Target FPS, 0=auto"),
    timeout_ms: int = typer.Option(8000, help="Open timeout ms"),
    log_level: str = typer.Option("INFO", help="DEBUG|INFO|WARNING|ERROR"),
):
    """GPU Motion-Highlight (brighter larvae) → RTSP OUT."""
    from .stream.highlight import run_highlight_loop
    cfg = load_and_validate(cfg_path, env_file)
    if url is None:
        url = (cfg.get("input", {}) or {}).get("rtsp_url")
    if out_url is None:
        out_url = (cfg.get("output", {}) or {}).get("rtsp_url")
    if not url or not out_url:
        print("[bold red]Missing input/output RTSP in config[/bold red]")
        raise typer.Exit(code=2)
    print(f"[bold cyan]Motion-Highlight[/bold cyan] IN={url} → OUT={out_url}")
    try:
        run_highlight_loop(url, out_url, log=log_level, fps_target=fps_target, open_timeout_ms=timeout_ms)
    except KeyboardInterrupt:
        print("[yellow]Interrupted by user[/yellow]")

if __name__ == "__main__":
    app()
