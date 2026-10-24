"""Variables por cama a las 06:00 con lo que la finca conoce (sin la verdad del simulador)."""
import numpy as np
import pandas as pd

from prediccion import reglas
from sim import clima

VARIABLES = (
    "temp_media_24h", "temp_min_24h", "temp_max_24h", "temp_media_mojado_24h",
    "hr_media_24h", "hr_max_24h", "delta_hr_24h",
    "horas_mojado_24h", "horas_mojado_72h", "max_mojado_continuo_24h", "dias_seguidos_hr_alta",
    "dpd_min_24h", "indice_broome_24h",
    "confirmadas_misma_cama", "confirmadas_camas_vecinas", "distancia_a_confirmada_en_nave",
    "ventilacion_encendida", "es_borde", "edad_lectura_h",
)
HORAS_DIA = 24  # estructural: ventanas de 24 y 72 h del nombre de las variables


def _mojado(cfg: dict, T: np.ndarray, HR: np.ndarray, horas: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bool de hora mojada y W (periodo mojado actual) para cada hora de la ventana."""
    m = cfg["mojado"]
    riego = np.array([clima.es_hora_de_riego(cfg, int(h)) for h in horas])
    mojada = (HR >= m["umbral_hr"]) | riego[:, None]
    W = np.zeros(HR.shape[1], dtype=int)
    secas = np.zeros(HR.shape[1], dtype=int)
    out = np.zeros(HR.shape, dtype=int)
    for k in range(len(horas)):
        W, secas = clima.actualizar_mojado(W, secas, mojada[k], m["pausa_seca_reinicio_h"])
        out[k] = W
    return mojada, out


def _confirmadas(cfg: dict, geo, confirmadas: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Confirmadas en la misma cama, en camas vecinas de la nave y distancia (en camas) a la más cercana."""
    r = cfg["riesgo"]
    n = geo.n_camas
    misma = confirmadas.astype(int)
    d = np.abs(geo.cama_c[:, None] - geo.cama_c[None, :])
    misma_nave = geo.nave_global_c[:, None] == geo.nave_global_c[None, :]
    vecinas = (confirmadas[None, :] * misma_nave * (d >= 1) * (d <= r["vecinas_camas"])).sum(axis=1)
    dist = np.where(misma_nave & confirmadas[None, :].astype(bool), d, r["sin_confirmada_camas"]).min(axis=1) \
        if confirmadas.any() else np.full(n, r["sin_confirmada_camas"])
    return misma, vecinas, dist


def construir(cfg: dict, geo, hora: int, est_T: np.ndarray, est_HR: np.ndarray, ultima_lectura: np.ndarray,
              confirmadas: np.ndarray, vent_encendida: np.ndarray) -> pd.DataFrame:
    """Variables de cada cama en `hora`; usa solo lecturas estimadas, incidencias confirmadas y ventilación."""
    r = cfg["riesgo"]
    ini = max(0, hora - 3 * HORAS_DIA + 1)
    horas = np.arange(ini, hora + 1)
    T, HR = est_T[ini:hora + 1].astype(float), est_HR[ini:hora + 1].astype(float)
    n24 = min(HORAS_DIA, len(horas))
    mojada, W = _mojado(cfg, T, HR, horas)
    T24, HR24, m24, W24 = T[-n24:], HR[-n24:], mojada[-n24:], W[-n24:]
    sin_datos_ant = len(horas) <= HORAS_DIA
    previo = HR[-2 * n24:-n24] if not sin_datos_ant else HR24
    t_mojado = np.where(m24.any(axis=0), (T24 * m24).sum(axis=0) / np.maximum(m24.sum(axis=0), 1), T24.mean(axis=0))
    w_max = W24.max(axis=0)
    dias_alta = np.zeros(geo.n_camas)
    seguir = np.ones(geo.n_camas, dtype=bool)
    for k in range(len(horas) // HORAS_DIA):
        bloque = HR[len(horas) - (k + 1) * HORAS_DIA:len(horas) - k * HORAS_DIA]
        seguir &= bloque.mean(axis=0) >= r["hr_alta"]
        dias_alta += seguir
    misma, vecinas, dist = _confirmadas(cfg, geo, confirmadas)
    td = clima.punto_rocio(cfg, T24, HR24)
    df = pd.DataFrame({
        "temp_media_24h": T24.mean(axis=0), "temp_min_24h": T24.min(axis=0), "temp_max_24h": T24.max(axis=0),
        "temp_media_mojado_24h": t_mojado,
        "hr_media_24h": HR24.mean(axis=0), "hr_max_24h": HR24.max(axis=0),
        "delta_hr_24h": HR24.mean(axis=0) - previo.mean(axis=0),
        "horas_mojado_24h": m24.sum(axis=0), "horas_mojado_72h": mojada.sum(axis=0),
        "max_mojado_continuo_24h": w_max, "dias_seguidos_hr_alta": dias_alta,
        "dpd_min_24h": (T24 - td).min(axis=0),
        "indice_broome_24h": reglas.indice_broome(w_max, t_mojado, cfg),
        "confirmadas_misma_cama": misma, "confirmadas_camas_vecinas": vecinas,
        "distancia_a_confirmada_en_nave": dist,
        "ventilacion_encendida": vent_encendida[geo.nave_global_c].astype(int),
        "es_borde": geo.es_borde_c.astype(int),
        "edad_lectura_h": np.minimum(hora - ultima_lectura, r["edad_max_h"]),
    })
    return df[list(VARIABLES)]
