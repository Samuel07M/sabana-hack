"""Carga de config/default.yaml para el hub y el dashboard."""
from functools import lru_cache
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_DEFAULT = RAIZ / "config" / "default.yaml"


@lru_cache(maxsize=1)
def cargar() -> dict:
    """Lee config/default.yaml (utf-8) una sola vez por proceso."""
    with open(CONFIG_DEFAULT, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
