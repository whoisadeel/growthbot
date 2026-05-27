"""Shared utilities: config loader, slug helpers, IO."""
import re
import yaml
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yaml"


def load_config() -> dict:
    """Load config.yaml. Falls back to a minimal default if missing."""
    if not CONFIG_PATH.exists():
        return {"brand": {"name": "Noidea Solutions",
                          "website": "https://noidea.solutions"}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def slugify(text: str) -> str:
    """Simple URL-slug generator."""
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "untitled"


def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
