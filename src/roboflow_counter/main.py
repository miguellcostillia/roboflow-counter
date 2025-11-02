import typer
from rich import print
from .settings import load_config

app = typer.Typer(add_completion=False)

@app.command()
def hello(name: str = "world"):
    print(f"[bold green]Hello {name}![/bold green] — Roboflow Counter ready 🚀")

@app.command()
def show_config(cfg_path: str = "config/config.yml", env_file: str = ".env"):
    cfg = load_config(cfg_path, env_file)
    print("[bold]Active Config:[/bold]")
    print(cfg.model_dump())

if __name__ == "__main__":
    app()
