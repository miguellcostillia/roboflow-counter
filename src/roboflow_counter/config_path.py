import pathlib, yaml

def load():
    for path in (pathlib.Path("config.yml"), pathlib.Path("config/config.yml")):
        if path.exists():
            with open(path, "r") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError("Keine config.yml gefunden")
