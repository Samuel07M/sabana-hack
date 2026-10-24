"""Métricas de una corrida (usa la verdad del simulador): anticipación, retraso, afectadas, errores."""
import numpy as np

from sim.enfermedad import LATENTE, PERDIDA, SINTOMAS


def _primera_hora_por_cama(cambios: np.ndarray, cama_de_planta: np.ndarray, estado: int, n_camas: int) -> np.ndarray:
    """Primera hora en que alguna planta de cada cama pasó a `estado` (NaN si nunca)."""
    sel = cambios[:, 2] == estado
    out = np.full(n_camas, np.inf)
    np.minimum.at(out, cama_de_planta[cambios[sel, 1]], cambios[sel, 0])
    return np.where(np.isinf(out), np.nan, out)


def _acumulado_de_infecciones(cambios: np.ndarray, cama_de_planta: np.ndarray, n_camas: int, n_horas: int) -> np.ndarray:
    """cum[h, cama] = infecciones nuevas (sana→latente) hasta la hora h inclusive."""
    inf = cambios[cambios[:, 2] == LATENTE]
    m = np.zeros((n_horas + 1, n_camas), dtype=np.int32)
    np.add.at(m, (inf[:, 0], cama_de_planta[inf[:, 1]]), 1)
    return m.cumsum(axis=0)


def _horas_por_cama(alertas: list, geo, tipo: str) -> dict[int, list[int]]:
    """Horas de las alertas de un tipo agrupadas por cama."""
    out: dict[int, list[int]] = {}
    for a in alertas:
        if a[6] == tipo:
            out.setdefault(geo.idx_cama[a[3]], []).append(a[2])
    return out


def extraer(sim) -> dict:
    """Métricas de una corrida terminada (anticipación en días: positivo = avisamos antes de que los síntomas aparezcan o aparecerían)."""
    cfg, g = sim.cfg, sim.geo
    an, horizonte = cfg["analisis"], cfg["riesgo"]["horizonte_h"]
    cambios = sim.cambios()
    infecc = _primera_hora_por_cama(cambios, g.cama_de_planta, LATENTE, g.n_camas)
    sint = _primera_hora_por_cama(cambios, g.cama_de_planta, SINTOMAS, g.n_camas)
    conf = np.full(g.n_camas, np.nan)
    for i in sim.inc.values():
        if i["hora_confirmada"] is not None:
            conf[i["cama"]] = np.nanmin([conf[i["cama"]], i["hora_confirmada"]])
    alto = _horas_por_cama(sim.buf["alertas"], g, "riesgo_7d")
    ventana = an["ventana_alto_antes_dias"] * 24
    # momento en que habrían aparecido los síntomas (infección + latencia): existe aunque el foco se frene a tiempo
    inf_ev = cambios[cambios[:, 2] == LATENTE]
    potencial = np.full(g.n_camas, np.inf)
    np.minimum.at(potencial, g.cama_de_planta[inf_ev[:, 1]], inf_ev[:, 0] + sim.enf.dur_latencia[inf_ev[:, 1]])
    potencial = np.where(np.isinf(potencial), np.nan, potencial)
    anticipacion = []
    for c in np.nonzero(~np.isnan(potencial))[0]:
        cand = [conf[c]] if not np.isnan(conf[c]) else []
        cand += [h for h in alto.get(c, []) if h >= infecc[c] - ventana]
        if cand:
            anticipacion.append((potencial[c] - min(cand)) / 24)
    retraso = [(i["hora_confirmada"] - infecc[i["cama"]]) / 24 for i in sim.inc.values()
               if i["hora_confirmada"] is not None and i["verdad_infectada"] == 1 and not np.isnan(infecc[i["cama"]])]
    cum = _acumulado_de_infecciones(cambios, g.cama_de_planta, g.n_camas, sim.n_horas)
    fin = lambda h: cum[min(h + horizonte, sim.n_horas)]
    falsas = sum(1 for c, hs in alto.items() for h in hs if fin(h)[c] - cum[h][c] == 0)
    sint_por_cama = np.bincount(g.cama_de_planta[cambios[cambios[:, 2] == SINTOMAS, 1]], minlength=g.n_camas)
    no_detectados = int(np.sum((sint_por_cama >= an["umbral_foco_no_detectado"]) & np.isnan(conf)))
    n = g.n_plantas
    estados = [i["estado"] for i in sim.inc.values()]
    return {
        "escenario": sim.escenario, "semilla": sim.semilla,
        "afectadas_final": sim.enf.afectadas[-1] / n, "afectadas_pico": sim.enf.afectadas.max() / n,
        "plantas_perdidas": int(np.sum(cambios[:, 2] == PERDIDA)),
        "camas_infectadas": int(np.sum(~np.isnan(infecc))), "camas_con_sintomas": int(np.sum(~np.isnan(sint))),
        "camas_frenadas": int(np.sum(~np.isnan(infecc) & np.isnan(sint))),
        "anticipacion_dias": float(np.mean(anticipacion)) if anticipacion else np.nan,
        "camas_avisadas": len(anticipacion), "camas_avisadas_antes": int(np.sum(np.array(anticipacion) > 0)),
        "retraso_deteccion_dias": float(np.mean(retraso)) if retraso else np.nan,
        "alertas_alto": sum(len(v) for v in alto.values()), "alertas_alto_falsas": falsas,
        "confirmaciones": sum(1 for i in sim.inc.values() if i["hora_confirmada"] is not None),
        "confirmaciones_falsas": sum(1 for i in sim.inc.values() if i["hora_confirmada"] is not None and i["verdad_infectada"] == 0),
        "descartadas": estados.count("descartada"), "focos_no_detectados": no_detectados,
        "ventilaciones_apagadas": sum(1 for v in sim.buf["ventilacion"] if v[4] == "apagada"),
    }


def serie_afectadas(sim) -> np.ndarray:
    """Fracción de plantas afectadas al final de cada día."""
    return sim.enf.afectadas.reshape(-1, 24)[:, -1] / sim.geo.n_plantas
