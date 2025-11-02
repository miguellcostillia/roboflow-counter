import typer
from rich import print
from .settings import load_config
import subprocess

app = typer.Typer(add_completion=False)

@app.command()
def hello(name: str = "world"):
    print(f"[bold green]Hello {name}![/bold green] — Roboflow Counter ready 🚀")

@app.command()
def show_config(cfg_path: str = "config/config.yml", env_file: str = ".env"):
    cfg = load_config(cfg_path, env_file)
    print("[bold]Active Config:[/bold]")
    print(cfg.model_dump())


@app.command()
def cuda_check():
    """Check CUDA / GPU status."""
    from rich import print
    import subprocess
    print("[bold cyan]Checking CUDA / GPU...[/bold cyan]")
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            print("[bold green]GPU detected via nvidia-smi ✅[/bold green]")
            print(result.stdout)
        else:
            print("[bold red]nvidia-smi failed[/bold red]")
            print(result.stderr)
    except FileNotFoundError:
        print("[bold red]nvidia-smi not found[/bold red] (NVIDIA drivers missing or container runtime?)")
    try:
        import cv2
        count = cv2.cuda.getCudaEnabledDeviceCount()
        print(f"OpenCV CUDA devices: {count}")
        if count == 0:
            print("[yellow]OpenCV installed but no CUDA devices found[/yellow]")
    except Exception as e:
        print(f"[red]OpenCV CUDA unavailable[/red] ({e})")
if __name__ == "__main__":
    app()
