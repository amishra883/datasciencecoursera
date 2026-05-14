"""YAML config loader. Single source of truth for config files in /config/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    path = CONFIG_DIR / f"{name}.yaml"
    with path.open() as fh:
        return yaml.safe_load(fh)


def reload(name: str) -> dict:
    load.cache_clear()
    return load(name)
