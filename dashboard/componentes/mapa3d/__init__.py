"""Mapa 3D del bloque como componente propio de Streamlit (index.html local, sin npm ni CDN)."""
from pathlib import Path

import streamlit.components.v1 as components

_componente = components.declare_component("mapa3d", path=str(Path(__file__).resolve().parent))


def mapa3d(datos: dict, key: str = "mapa3d") -> dict | None:
    """Pinta el mapa con los datos del bloque; devuelve {'cama', 't'} de la última cama clicada o {'bloque', 't'}."""
    return _componente(datos=datos, key=key, default=None)
