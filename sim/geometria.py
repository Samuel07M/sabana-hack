"""Geometría de la finca: camas (Bloque · Nave · Cama), plantas, vecindad y corriente de aire."""
from dataclasses import dataclass

import numpy as np
from scipy import sparse


def cama_id(bloque: int, nave: int, cama: int) -> str:
    """Identificador de cama, ej. 'B1-N2-C14'."""
    return f"B{bloque}-N{nave}-C{cama:02d}"


def listar_camas(cfg: dict) -> list[dict]:
    """Una fila por cama; camas numeradas continuas dentro del bloque."""
    g = cfg["geometria"]
    por_nave = g["camas_por_nave"]
    camas = []
    for bloque in range(1, g["bloques"] + 1):
        for nave in range(1, g["naves_por_bloque"] + 1):
            primera = (nave - 1) * por_nave + 1
            ultima = nave * por_nave
            for cama in range(primera, ultima + 1):
                camas.append({
                    "cama_id": cama_id(bloque, nave, cama),
                    "bloque": bloque,
                    "nave": nave,
                    "cama": cama,
                    "es_borde": int(cama in (primera, ultima)),
                    "tiene_ventilacion": int(g["tiene_ventilacion"]),
                })
    return camas


@dataclass
class Geo:
    """Arreglos de geometría (índice de cama y de planta en el orden de `listar_camas`)."""
    camas: list
    n_camas: int
    n_plantas: int
    plantas_por_cama: int
    n_naves: int                 # naves globales (bloque, nave)
    bloque_c: np.ndarray         # por cama: 1..bloques
    nave_c: np.ndarray           # por cama: 1..naves_por_bloque
    cama_c: np.ndarray           # por cama: número continuo dentro del bloque
    nave_global_c: np.ndarray    # por cama: índice 0.. de nave global
    es_borde_c: np.ndarray       # por cama (bool)
    tiene_vent_c: np.ndarray     # por cama (bool)
    cama_de_planta: np.ndarray   # por planta: índice de cama
    posicion_p: np.ndarray       # por planta: 1..plantas_por_cama
    es_borde_planta: np.ndarray  # por planta (bool) · solo interno de sim/
    V: sparse.csc_matrix         # vecindad exponencial (simétrica, sin diagonal)
    A_aire: np.ndarray           # (camas, camas): A[destino, origen], aguas abajo en la nave
    cama_central: np.ndarray     # por bloque (índice 0..bloques-1): cama del sensor central
    idx_cama: dict               # cama_id -> índice


def _matriz_vecindad(cfg: dict, n_plantas: int, cama_local: np.ndarray, pos0: np.ndarray) -> sparse.csc_matrix:
    """Núcleo exponencial K(d) = exp(-b·d) entre plantas de la misma nave, recortado en `corte_nucleo`."""
    g, e = cfg["geometria"], cfg["enfermedad"]
    P, C = g["plantas_por_cama"], g["camas_por_nave"]
    d_max = np.log(1.0 / e["corte_nucleo"]) / e["b_dispersion_por_m"]
    base = np.arange(n_plantas)
    filas, cols, pesos = [], [], []
    for dc in range(-(C - 1), C):
        d_cama = abs(dc) * g["separacion_camas_m"]
        if d_cama > d_max:
            continue
        for dp in range(-(P - 1), P):
            d = np.hypot(d_cama, dp * g["separacion_plantas_m"])
            peso = np.exp(-e["b_dispersion_por_m"] * d)
            if (dc == 0 and dp == 0) or peso < e["corte_nucleo"]:
                continue
            ok = (cama_local + dc >= 0) & (cama_local + dc < C) & (pos0 + dp >= 0) & (pos0 + dp < P)
            i = base[ok]
            filas.append(i)
            cols.append(i + dc * P + dp)
            pesos.append(np.full(i.size, peso))
    V = sparse.coo_matrix((np.concatenate(pesos), (np.concatenate(filas), np.concatenate(cols))),
                          shape=(n_plantas, n_plantas))
    return V.tocsc()


def _matriz_aire(cfg: dict, geo_camas: dict) -> np.ndarray:
    """A[destino, origen] = exp(-d/L) para camas aguas abajo (número de cama mayor) de la misma nave."""
    L = cfg["enfermedad"]["L_aire_camas"]
    nave, cama = geo_camas["nave_global"], geo_camas["cama"]
    d = cama[:, None] - cama[None, :]
    misma_nave = nave[:, None] == nave[None, :]
    return np.where(misma_nave & (d >= 1), np.exp(-d / L), 0.0)


def construir(cfg: dict) -> Geo:
    """Construye todos los arreglos de geometría a partir de config.geometria."""
    g = cfg["geometria"]
    camas = listar_camas(cfg)
    P = g["plantas_por_cama"]
    n_camas, n_plantas = len(camas), len(camas) * P
    bloque = np.array([c["bloque"] for c in camas])
    nave = np.array([c["nave"] for c in camas])
    cama = np.array([c["cama"] for c in camas])
    es_borde = np.array([c["es_borde"] for c in camas], dtype=bool)
    nave_global = (bloque - 1) * g["naves_por_bloque"] + (nave - 1)
    cama_de_planta = np.repeat(np.arange(n_camas), P)
    pos0 = np.tile(np.arange(P), n_camas)
    cama_local = (cama[cama_de_planta] - 1) % g["camas_por_nave"]
    izq, der = g["posiciones_esquina"]
    esquina = (pos0 < izq) | (pos0 >= P - der)
    # sensor central: cama central de la nave central del bloque
    nave_central = (g["naves_por_bloque"] + 1) // 2
    local_central = (g["camas_por_nave"] - 1) // 2
    cama_central = np.array([
        (b * g["naves_por_bloque"] + nave_central - 1) * g["camas_por_nave"] + local_central
        for b in range(g["bloques"])])
    return Geo(
        camas=camas, n_camas=n_camas, n_plantas=n_plantas, plantas_por_cama=P,
        n_naves=g["bloques"] * g["naves_por_bloque"],
        bloque_c=bloque, nave_c=nave, cama_c=cama, nave_global_c=nave_global,
        es_borde_c=es_borde, tiene_vent_c=np.array([c["tiene_ventilacion"] for c in camas], dtype=bool),
        cama_de_planta=cama_de_planta, posicion_p=pos0 + 1,
        es_borde_planta=es_borde[cama_de_planta] | esquina,
        V=_matriz_vecindad(cfg, n_plantas, cama_local, pos0),
        A_aire=_matriz_aire(cfg, {"nave_global": nave_global, "cama": cama}),
        cama_central=cama_central,
        idx_cama={c["cama_id"]: i for i, c in enumerate(camas)},
    )
