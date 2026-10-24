"""Carga y uso del modelo de IA (HistGradientBoosting) con su lista de variables."""
import json

import joblib
import numpy as np
import pandas as pd

from prediccion.variables import VARIABLES
from sim.config import RAIZ

DATA = RAIZ / "data"
VARIANTES = {"completo": "modelo_ia", "central": "modelo_ia_central"}  # central = solo sensor fijo


def rutas(variante: str):
    """Rutas (.joblib, .json) del modelo de la variante."""
    base = DATA / VARIANTES[variante]
    return base.with_suffix(".joblib"), base.with_suffix(".json")


def guardar(modelo, variante: str, extra: dict | None = None) -> None:
    """Guarda el modelo y la lista ordenada de variables."""
    DATA.mkdir(parents=True, exist_ok=True)
    pkl, js = rutas(variante)
    joblib.dump(modelo, pkl)
    with open(js, "w", encoding="utf-8") as f:
        json.dump({"variables": list(VARIABLES), **(extra or {})}, f, ensure_ascii=False, indent=2)


class Modelo:
    """Envuelve el clasificador y valida que las columnas coincidan con el JSON."""

    def __init__(self, clf, variables: list[str]):
        self.clf, self.variables = clf, variables

    def predecir(self, df: pd.DataFrame) -> np.ndarray:
        """Probabilidad de infección a 7 días por fila."""
        if list(df.columns) != self.variables:
            raise ValueError(f"columnas distintas a modelo_ia.json: {list(df.columns)}")
        return self.clf.predict_proba(df)[:, 1]


def cargar(variante: str = "completo", exigir: bool = False) -> Modelo | None:
    """Carga el modelo; sin archivo devuelve None (o ValueError si `exigir`)."""
    pkl, js = rutas(variante)
    if not pkl.exists():
        if exigir:
            raise ValueError("falta el modelo: corre `python -m prediccion.entrenar`")
        return None
    with open(js, encoding="utf-8") as f:
        variables = json.load(f)["variables"]
    if variables != list(VARIABLES):
        raise ValueError("modelo_ia.json no coincide con prediccion.variables.VARIABLES: reentrena")
    return Modelo(joblib.load(pkl), variables)
