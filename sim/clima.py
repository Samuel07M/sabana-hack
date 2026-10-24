"""Clima verdadero por cama y hora, mojado de Broome y punto de rocío."""
import numpy as np


def generar(cfg: dict, geo, n_horas: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """T y HR (sin efecto de ventilación, sin recortar) con forma (horas, camas)."""
    c = cfg["clima"]
    h = np.arange(n_horas)
    fase = np.sin(2 * np.pi * ((h % 24) - 9) / 24)[:, None]
    off_T = rng.normal(0, c["offset_nave_T_sd"], geo.n_naves)[geo.nave_global_c][None, :]
    off_HR = rng.normal(0, c["offset_nave_HR_sd"], geo.n_naves)[geo.nave_global_c][None, :]
    forma = (n_horas, geo.n_camas)
    T = c["T_media"] + c["A_T"] * fase + off_T + rng.normal(0, c["ruido_T_sd"], forma)
    HR = (c["HR_media"] - c["A_HR"] * fase + off_HR + c["extra_borde_hr"] * geo.es_borde_c[None, :]
          + rng.normal(0, c["ruido_HR_sd"], forma))
    HR += subidas_humedas(cfg, geo, n_horas, rng)
    return T.astype(np.float32), HR.astype(np.float32)


def subidas_humedas(cfg: dict, geo, n_horas: int, rng: np.random.Generator) -> np.ndarray:
    """Subida de HR (horas, camas): eventos aleatorios por bloque más los forzados de la config (bloque o una nave)."""
    c = cfg["clima"]
    n_bloques = int(geo.bloque_c.max())
    por_bloque = np.zeros((n_horas, n_bloques))
    dmin, dmax = c["duracion_evento_h"]
    inicios = rng.random((n_horas, n_bloques)) < c["eventos_humedos_por_dia"] / 24
    duraciones = rng.integers(dmin, dmax + 1, (n_horas, n_bloques))
    for hora, b in zip(*np.nonzero(inicios)):
        por_bloque[hora:hora + duraciones[hora, b], b] = c["subida_evento_hr"]
    subida = por_bloque[:, geo.bloque_c - 1]
    for ev in c["eventos_forzados"]:
        s = ev.get("subida_hr", c["subida_evento_hr"])
        sl = slice(ev["hora"], ev["hora"] + ev["duracion_h"])
        camas = geo.bloque_c == ev["bloque"]
        if "nave" in ev:
            camas &= geo.nave_c == ev["nave"]
        subida[sl, camas] = np.maximum(subida[sl, camas], s)
    return subida


def es_hora_de_riego(cfg: dict, hora: int) -> bool:
    """True si la hora del día cae dentro de un riego."""
    m = cfg["mojado"]
    hd = hora % 24
    return any(0 <= (hd - inicio) % 24 < m["riego_duracion_h"] for inicio in m["riego_horas"])


def hr_con_ventilacion(cfg: dict, hr_base: np.ndarray, vent_encendida: np.ndarray) -> np.ndarray:
    """HR de la hora: la ventilación encendida suma delta_ventilacion_hr; recorta al rango."""
    c = cfg["clima"]
    lo, hi = c["hr_rango"]
    return np.clip(hr_base + c["delta_ventilacion_hr"] * vent_encendida, lo, hi)


def actualizar_mojado(W: np.ndarray, secas: np.ndarray, mojada: np.ndarray, pausa_h: int):
    """Regla de Broome: W cuenta horas mojadas y se reinicia tras más de `pausa_h` h secas seguidas."""
    secas = np.where(mojada, 0, secas + 1)
    W = np.where(mojada, W + 1, W)
    return np.where(secas > pausa_h, 0, W), secas


def punto_rocio(cfg: dict, T: np.ndarray, HR: np.ndarray) -> np.ndarray:
    """Punto de rocío (Magnus): Td = b·γ/(a − γ)."""
    a, b = cfg["mojado"]["magnus_a"], cfg["mojado"]["magnus_b"]
    gamma = np.log(np.clip(HR, 1e-3, None) / 100.0) + a * T / (b + T)
    return b * gamma / (a - gamma)
