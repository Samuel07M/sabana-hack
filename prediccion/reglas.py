"""Línea base biológica: índice de Broome et al. (1995)."""
import numpy as np


def indice_broome(W, T, cfg: dict):
    """índice = c0 + c1·W + c2·W·T + c3·W·T², con T recortada a broome_T_rango."""
    c0, c1, c2, c3 = cfg["riesgo"]["broome_coef"]
    T = np.clip(T, *cfg["riesgo"]["broome_T_rango"])
    return c0 + c1 * W + c2 * W * T + c3 * W * T ** 2


def nivel_broome(indice: float, cfg: dict) -> str:
    """Texto del nivel de Broome: nulo ≤ 0 < bajo ≤ 0,5 < moderado ≤ 1 < alto."""
    a, b, c = cfg["riesgo"]["broome_niveles"]
    return "nulo" if indice <= a else "bajo" if indice <= b else "moderado" if indice <= c else "alto"


def riesgo_reglas(vars_df, cfg: dict) -> np.ndarray:
    """riesgo_reglas ∈ [0,1] = min(1, sigmoide(índice)·(1 + bonus si hay confirmadas cerca))."""
    y = 1.0 / (1.0 + np.exp(-vars_df["indice_broome_24h"].to_numpy()))
    cerca = (vars_df["confirmadas_misma_cama"] + vars_df["confirmadas_camas_vecinas"]).to_numpy() > 0
    y = np.where(cerca, y * (1.0 + cfg["riesgo"]["bonus_confirmadas"]), y)
    return np.clip(y, 0.0, 1.0)


def nivel_de(prob, cfg: dict) -> np.ndarray:
    """'alto' si prob ≥ umbral_alto, 'medio' si ≥ umbral_medio, si no 'bajo'."""
    r = cfg["riesgo"]
    prob = np.asarray(prob, dtype=float)
    return np.where(prob >= r["umbral_alto"], "alto", np.where(prob >= r["umbral_medio"], "medio", "bajo"))
