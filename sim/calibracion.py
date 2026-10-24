"""Calibración con las metas del PDF (f_ambiental = 1): β_vec entre camas y β_cama dentro de la cama."""
import numpy as np
from scipy.optimize import brentq

HORAS_DIA = 24


def _nucleo_cama_contigua(cfg: dict) -> np.ndarray:
    """Pesos K(d) desde una planta en la mitad de una cama hacia cada planta de la cama contigua."""
    g, e = cfg["geometria"], cfg["enfermedad"]
    P = g["plantas_por_cama"]
    d = np.hypot(g["separacion_camas_m"], (np.arange(P) - P // 2) * g["separacion_plantas_m"])
    K = np.exp(-e["b_dispersion_por_m"] * d)
    return np.where(K >= e["corte_nucleo"], K, 0.0)


def prob_cama_contigua(cfg: dict, beta_vec: float, dias: int = 7) -> float:
    """Probabilidad de que la cama contigua tenga al menos una planta infectada tras `dias` (un foco con síntomas)."""
    lam = beta_vec * cfg["enfermedad"]["peso_sintomas"] * _nucleo_cama_contigua(cfg)
    return float(1.0 - np.exp(-lam.sum() * dias * HORAS_DIA))


def suma_nucleo_misma_cama(cfg: dict) -> float:
    """Σ K(d) desde una planta en la mitad de la cama hacia las demás plantas de su cama."""
    g, e = cfg["geometria"], cfg["enfermedad"]
    P = g["plantas_por_cama"]
    d = np.abs(np.arange(P) - P // 2) * g["separacion_plantas_m"]
    K = np.exp(-e["b_dispersion_por_m"] * d)
    return float(np.sum(np.where((d > 0) & (K >= e["corte_nucleo"]), K, 0.0)))


def tasa_logistica_cama(cfg: dict, beta_cama: float) -> float:
    """r por día dentro de una cama en campo medio: r = 24 · β_cama · peso_latente · ΣK (las nuevas nacen latentes)."""
    return HORAS_DIA * beta_cama * cfg["enfermedad"]["peso_latente"] * suma_nucleo_misma_cama(cfg)


def calibrar_beta_vec(cfg: dict) -> float:
    """β_vec tal que la cama contigua se infecte con probabilidad meta_cama_adyacente_7d (PDF: 5,5 %)."""
    meta = cfg["enfermedad"]["meta_cama_adyacente_7d"]
    return float(brentq(lambda b: prob_cama_contigua(cfg, b) - meta, 1e-9, 1.0))


def calibrar_beta_cama(cfg: dict) -> float:
    """β_cama tal que un foco crezca dentro de su cama con r = tasa_logistica_r_dia (PDF: 0,2/día)."""
    return cfg["enfermedad"]["tasa_logistica_r_dia"] / tasa_logistica_cama(cfg, 1.0)


def main() -> None:
    """Imprime β_vec y β_cama calibrados frente a los de la config."""
    from sim.config import cargar_config
    cfg = cargar_config()
    e = cfg["enfermedad"]
    print(f"beta_vec  calibrado = {calibrar_beta_vec(cfg):.6f} (config {e['beta_vec']}) · "
          f"cama contigua en 7 días = {prob_cama_contigua(cfg, e['beta_vec']):.2%}")
    print(f"beta_cama calibrado = {calibrar_beta_cama(cfg):.6f} (config {e['beta_cama']}) · "
          f"r dentro de la cama = {tasa_logistica_cama(cfg, e['beta_cama']):.3f}/día")


if __name__ == "__main__":
    main()
