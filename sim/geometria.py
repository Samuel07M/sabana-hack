"""Geometría de la finca: camas con nomenclatura Bloque · Nave · Cama."""


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
