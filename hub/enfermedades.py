"""Nombre de la enfermedad que se muestra en pantalla por bloque (config: dashboard.enfermedades_por_bloque).

El simulador solo modela Botrytis; el tablero reetiqueta esos mismos eventos según el bloque de la cama.
Nada cambia en la base ni en el simulador: solo el texto que se ve.
"""
import pandas as pd

from hub import ubicacion as U
from hub.config import cargar

MODELADA = "Botrytis"   # nombre que escribe el simulador en títulos y mensajes


def nombres() -> list[str]:
    """Enfermedades en el orden de los bloques."""
    return list(cargar()["dashboard"]["enfermedades_por_bloque"])


def de_cama(cama_id: str | None) -> str:
    """Enfermedad mostrada para una cama (por su bloque); Botrytis si no hay cama."""
    b = U.bloque_de(cama_id) if isinstance(cama_id, str) and cama_id else None
    ns = nombres()
    return ns[(b - 1) % len(ns)] if b and ns else MODELADA


def reetiquetar(texto, cama_id: str | None):
    """Cambia 'Botrytis' por la enfermedad de la cama en un texto (None/NaN pasan igual)."""
    return texto.replace(MODELADA, de_cama(cama_id)) if isinstance(texto, str) else texto


def alertas(df: pd.DataFrame) -> pd.DataFrame:
    """Títulos y mensajes de alertas con el nombre de la enfermedad de cada cama."""
    if df.empty:
        return df
    df = df.copy()
    for col in ("titulo", "mensaje"):
        df[col] = [reetiquetar(t, c) for t, c in zip(df[col], df["cama_id"])]
    return df
