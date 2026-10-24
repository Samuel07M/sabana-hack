"""Mediciones con ruido: sensor fijo central por bloque y lecturas del dron."""
import numpy as np


def medir(cfg: dict, T: np.ndarray, HR: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Temperatura y humedad medidas = verdad + ruido del sensor (HR recortada al rango)."""
    s = cfg["sensores"]
    lo, hi = cfg["clima"]["hr_rango"]
    T = np.asarray(T, dtype=float)
    HR = np.asarray(HR, dtype=float)
    return (T + rng.normal(0, s["ruido_T_sd"], T.shape),
            np.clip(HR + rng.normal(0, s["ruido_HR_sd"], HR.shape), lo, hi))


def filas_sensor_central(corrida_id: str, hora: int, geo, T: np.ndarray, HR: np.ndarray) -> list[tuple]:
    """Una fila de `lecturas` por bloque (cama central), fuente 'sensor_fijo'."""
    return [(corrida_id, hora, geo.camas[c]["cama_id"], round(float(T[k]), 2), round(float(HR[k]), 2), "sensor_fijo")
            for k, c in enumerate(geo.cama_central)]
