"""Ubicación de la finca: 'B1-N2-C14' ↔ (1, 2, 14) ↔ 'Bloque 1 · Nave 2 · Cama 14'."""
import re

from hub.config import cargar

_PATRON = re.compile(r"^B(\d+)-N(\d+)-C(\d+)$")


def camas_por_nave() -> int:
    """Camas por nave según la geometría del YAML."""
    return int(cargar()["geometria"]["camas_por_nave"])


def cama_id(bloque: int, nave: int, cama: int) -> str:
    """Identificador de cama: B{bloque}-N{nave}-C{cama:02d}."""
    return f"B{bloque}-N{nave}-C{cama:02d}"


def partes(cid: str) -> tuple[int, int, int]:
    """(bloque, nave, cama) de un identificador; ValueError si no es válido."""
    m = _PATRON.match(cid or "")
    if not m:
        raise ValueError(f"cama_id inválido: {cid!r}")
    return int(m[1]), int(m[2]), int(m[3])


def nave_de_cama(cama: int) -> int:
    """Nave a la que pertenece una cama numerada de forma continua dentro del bloque."""
    return (cama - 1) // camas_por_nave() + 1


def cama_en_nave(cama: int) -> int:
    """Posición 1…camas_por_nave de la cama dentro de su nave."""
    return (cama - 1) % camas_por_nave() + 1


def legible(cid: str) -> str:
    """'Bloque 1 · Nave 2 · Cama 14'."""
    b, n, c = partes(cid)
    return f"Bloque {b} · Nave {n} · Cama {c}"


def corto(cid: str) -> str:
    """'B1 · Nave 2 · Cama 14'."""
    b, n, c = partes(cid)
    return f"B{b} · Nave {n} · Cama {c}"


def sin_bloque(cid: str) -> str:
    """'Nave 2 · Cama 14'."""
    _, n, c = partes(cid)
    return f"Nave {n} · Cama {c}"


def bloque_de(cid: str | None) -> int | None:
    """Bloque de un identificador, o None si no hay cama."""
    return partes(cid)[0] if cid else None
