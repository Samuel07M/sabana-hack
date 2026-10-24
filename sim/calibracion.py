"""Calibración de β_vec con la meta del PDF: un foco, f_ambiental = 1, cama contigua ≈ 5,5 % en 7 días."""
import numpy as np
from scipy.optimize import brentq


def fraccion_cama_contigua(cfg: dict, beta_vec: float, dias: int = 7) -> float:
    """Fracción esperada de plantas de la cama contigua infectadas tras `dias` por un foco con síntomas."""
    g, e = cfg["geometria"], cfg["enfermedad"]
    P = g["plantas_por_cama"]
    foco = P // 2
    pos = np.arange(P)
    d = np.hypot(g["separacion_camas_m"], (pos - foco) * g["separacion_plantas_m"])
    K = np.exp(-e["b_dispersion_por_m"] * d)
    K = np.where(K >= e["corte_nucleo"], K, 0.0)
    lam = beta_vec * e["peso_sintomas"] * K
    return float(np.mean(1.0 - np.exp(-lam * dias * 24)))


def calibrar_beta_vec(cfg: dict) -> float:
    """β_vec tal que fraccion_cama_contigua = meta_cama_adyacente_7d."""
    meta = cfg["enfermedad"]["meta_cama_adyacente_7d"]
    return float(brentq(lambda b: fraccion_cama_contigua(cfg, b) - meta, 1e-6, 1.0))


def main() -> None:
    """Imprime el β_vec calibrado."""
    from sim.config import cargar_config
    cfg = cargar_config()
    b = calibrar_beta_vec(cfg)
    print(f"beta_vec calibrado = {b:.5f} (en config: {cfg['enfermedad']['beta_vec']}) · "
          f"fracción a 7 días con el de config = {fraccion_cama_contigua(cfg, cfg['enfermedad']['beta_vec']):.3%}")


if __name__ == "__main__":
    main()
