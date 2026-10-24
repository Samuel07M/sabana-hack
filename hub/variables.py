"""Variables de "Qué explica este riesgo": la misma lógica de variables() del prototipo.

La usan el mock (con sus datos en memoria) y hub/db.py (leyendo la base).
"""
import math

ESTADOS_CONFIRMADOS = ("confirmada", "en_tratamiento", "en_seguimiento")
SIN_CONFIRMADA = 99


def _media(v: list[float]) -> float | None:
    """Media o None si la lista está vacía."""
    return sum(v) / len(v) if v else None


def _clamp(x: float, a: float, b: float) -> float:
    """x recortado a [a, b]."""
    return max(a, min(b, x))


def calcular(lect_robot: list[tuple], sensor: dict, fin: int, *, ventana_h: int, validez_h: float,
             umbral_hr: float, hr_rango: tuple, dist: int, borde: int, ahora: float | None = None) -> dict:
    """Variables de una cama en las `ventana_h` horas antes de `fin` (excluida).

    lect_robot: [(hora, temp_c, hr, fuente)] del robot en la cama, ordenadas por hora.
    sensor: {hora: (temp_c, hr)} del sensor fijo del bloque.
    """
    lo, hi = hr_rango
    HR, T = [], []
    j = -1
    for x in range(fin - ventana_h, fin):
        if x < 0:
            HR.append(None)
            T.append(None)
            continue
        while j + 1 < len(lect_robot) and lect_robot[j + 1][0] <= x:
            j += 1
        l = lect_robot[j] if j >= 0 and x - lect_robot[j][0] <= validez_h else None
        s = sensor.get(x)
        s0 = sensor.get(int(math.floor(l[0]))) if l else None
        if l and s and s0:
            HR.append(_clamp(l[2] + (s[1] - s0[1]), lo, hi))
            T.append(l[1] + (s[0] - s0[0]))
        elif l:
            HR.append(l[2])
            T.append(l[1])
        else:
            HR.append(s[1] if s else None)
            T.append(s[0] if s else None)
    hr24 = [v for v in HR[-24:] if v is not None]
    hr_prev = [v for v in HR[-48:-24] if v is not None]
    t24 = [v for v in T[-24:] if v is not None]
    wet72 = sum(1 for v in HR if v is not None and v >= umbral_hr)
    wet24 = sum(1 for v in hr24 if v >= umbral_hr)
    hr_mean, hr_mean_prev = _media(hr24), _media(hr_prev)
    ult = lect_robot[-1] if lect_robot else None
    return {
        "wet72": wet72, "wet24": wet24, "t_mean": _media(t24), "hr_mean": hr_mean,
        "hr_max24": max(hr24) if hr24 else None,
        "delta_hr": hr_mean - hr_mean_prev if hr_mean is not None and hr_mean_prev is not None else 0.0,
        "dist": dist, "borde": int(borde),
        "edad": ((fin if ahora is None else ahora) - ult[0]) if ult else None,
        "ult_fuente": ult[3] if ult else "sensor_fijo",
    }


def distancia_confirmada(cama: int, confirmadas: list[int]) -> int:
    """Camas hasta la confirmada más cercana en la misma nave (99 si no hay)."""
    return min((abs(c - cama) for c in confirmadas), default=SIN_CONFIRMADA)
