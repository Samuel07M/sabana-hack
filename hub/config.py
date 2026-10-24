"""Carga de config/default.yaml para el hub y el dashboard."""
from functools import lru_cache
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_DEFAULT = RAIZ / "config" / "default.yaml"


@lru_cache(maxsize=1)
def _leer(mtime_ns: int) -> dict:
    """Lee config/default.yaml (utf-8); la caché se renueva cuando cambia la fecha de modificación."""
    with open(CONFIG_DEFAULT, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cargar() -> dict:
    """Configuración vigente: se relee si el YAML cambió (Streamlit no reinicia el proceso al editarlo)."""
    return _leer(CONFIG_DEFAULT.stat().st_mtime_ns)
