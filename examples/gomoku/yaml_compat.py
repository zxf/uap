"""Minimal YAML-like config loader. Uses PyYAML if available, falls back to JSON."""

from pathlib import Path


def load(path: str | Path) -> dict:
    text = Path(path).read_text()
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        import json
        return json.loads(text)
