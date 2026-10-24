"""Geometría de dibujo del mapa del bloque: ÚNICO lugar donde (bloque, nave, cama, posición) se vuelve coordenada.

Unidades del SVG antes de proyectar, con origen en la esquina superior izquierda de las camas del bloque
(x hacia la derecha, y hacia abajo). Las naves se apilan de arriba hacia abajo y, dentro de cada nave, las camas
también (la primera cama de la nave arriba). Un pasillo vertical central parte todas las camas en dos mitades:
posiciones 1…P/2 a la izquierda y P/2+1…P a la derecha. El robot de riel recorre ese pasillo.
Todas las medidas salen de config/default.yaml (geometria y dashboard.mapa). Rect = (x, y, ancho, alto).
"""
from hub import ubicacion as U
from hub.config import cargar

Rect = tuple[float, float, float, float]


def _g(cfg: dict | None) -> tuple[dict, dict]:
    """(geometria, dashboard.mapa) de la configuración."""
    cfg = cfg or cargar()
    return cfg["geometria"], cfg["dashboard"]["mapa"]


def _alto_nave(g: dict, m: dict) -> float:
    """Alto de las camas de una nave (sin la separación con la siguiente)."""
    k = g["camas_por_nave"]
    return k * m["cama_alto"] + (k - 1) * m["sep_camas"]


def dimensiones(bloque: int = 1, cfg: dict | None = None) -> tuple[float, float]:
    """(ancho, alto) del área de camas de un bloque."""
    g, m = _g(cfg)
    n = g["naves_por_bloque"]
    return 2 * m["mitad_ancho"] + m["pasillo_central"], n * _alto_nave(g, m) + (n - 1) * m["sep_naves"]


def _y_cama(nave: int, cama: int, g: dict, m: dict) -> float:
    """Borde superior de la cama (numeración continua dentro del bloque)."""
    k = (cama - 1) % g["camas_por_nave"]
    return (nave - 1) * (_alto_nave(g, m) + m["sep_naves"]) + k * (m["cama_alto"] + m["sep_camas"])


def _validar(nave: int, cama: int, g: dict) -> None:
    """ValueError si la cama no pertenece a la nave."""
    if (cama - 1) // g["camas_por_nave"] + 1 != nave:
        raise ValueError(f"la cama {cama} no está en la nave {nave}")


def rect_cama(bloque: int, nave: int, cama: int, cfg: dict | None = None) -> Rect:
    """Rectángulo completo de la cama, de borde a borde (incluye el tramo de pasillo que la cruza)."""
    g, m = _g(cfg)
    _validar(nave, cama, g)
    return 0.0, _y_cama(nave, cama, g, m), dimensiones(bloque, cfg)[0], float(m["cama_alto"])


def mitades_cama(bloque: int, nave: int, cama: int, cfg: dict | None = None) -> tuple[Rect, Rect]:
    """Las dos mitades con plantas de la cama: (izquierda, derecha), sin el pasillo."""
    _, m = _g(cfg)
    x, y, _, h = rect_cama(bloque, nave, cama, cfg)
    w = float(m["mitad_ancho"])
    return (x, y, w, h), (x + w + m["pasillo_central"], y, w, h)


def rect_pasillo(bloque: int = 1, cfg: dict | None = None) -> Rect:
    """Pasillo central: atraviesa todas las naves del bloque de arriba abajo."""
    _, m = _g(cfg)
    _, alto = dimensiones(bloque, cfg)
    return float(m["mitad_ancho"]), 0.0, float(m["pasillo_central"]), alto


def rect_nave(bloque: int, nave: int, cfg: dict | None = None) -> Rect:
    """Rectángulo de las camas de una nave."""
    g, m = _g(cfg)
    primera = (nave - 1) * g["camas_por_nave"] + 1
    _, y, ancho, _ = rect_cama(bloque, nave, primera, cfg)
    return 0.0, y, ancho, _alto_nave(g, m)


def placas_nave(bloque: int, nave: int, cfg: dict | None = None) -> tuple[Rect, Rect]:
    """Placas de suelo de la nave a cada lado del pasillo (el pasillo queda como suelo vacío)."""
    _, m = _g(cfg)
    _, y, _, h = rect_nave(bloque, nave, cfg)
    mg, w, p = m["margen_placa"], m["mitad_ancho"], m["pasillo_central"]
    return (-mg, y - mg, w + mg, h + 2 * mg), (w + p, y - mg, w + mg, h + 2 * mg)


def punto_planta(bloque: int, nave: int, cama: int, posicion: int, cfg: dict | None = None) -> tuple[float, float]:
    """Centro de la planta: 1…P/2 en la mitad izquierda (desde el borde) y P/2+1…P en la derecha (desde el pasillo)."""
    g, _ = _g(cfg)
    P = g["plantas_por_cama"]
    if not 1 <= posicion <= P:
        raise ValueError(f"posición fuera de la cama: {posicion}")
    mitad = P // 2
    izq, der = mitades_cama(bloque, nave, cama, cfg)
    x, y, w, h = izq if posicion <= mitad else der
    i, n = (posicion - 1, mitad) if posicion <= mitad else (posicion - mitad - 1, P - mitad)
    return x + (i + 0.5) * w / n, y + h / 2


def punto_robot(bloque: int, nave: int, cama: int, cfg: dict | None = None) -> tuple[float, float]:
    """Centro de la cama, sobre el riel del pasillo: ir de una cama a otra es recorrer el pasillo."""
    x, y, w, h = rect_cama(bloque, nave, cama, cfg)
    return x + w / 2, y + h / 2


def flecha_aire(bloque: int, nave: int, cfg: dict | None = None) -> tuple[tuple[float, float], tuple[float, float]]:
    """(inicio, fin) de la flecha de ventilación: a la derecha de la nave, de la primera a la última cama (aguas abajo)."""
    _, m = _g(cfg)
    x, y, w, h = rect_nave(bloque, nave, cfg)
    xf = x + w + m["margen_placa"] + m["sep_flecha"]
    return (xf, y + m["cama_alto"] / 2), (xf, y + h - m["cama_alto"] / 2)


def punto_etiqueta(bloque: int, nave: int, cfg: dict | None = None) -> tuple[float, float]:
    """Dónde va la etiqueta N1…N6: a la izquierda de la nave, a media altura."""
    _, m = _g(cfg)
    x, y, _, h = rect_nave(bloque, nave, cfg)
    return x - m["margen_placa"] - m["sep_etiqueta"], y + h / 2


def cama_en_punto(x: float, y: float, bloque: int = 1, cfg: dict | None = None) -> str | None:
    """cama_id de la cama que contiene el punto (incluido su tramo de pasillo), o None si cae entre camas o naves."""
    g, m = _g(cfg)
    ancho, alto = dimensiones(bloque, cfg)
    if not (0 <= x <= ancho and 0 <= y <= alto):
        return None
    paso_nave = _alto_nave(g, m) + m["sep_naves"]
    nave = int(y // paso_nave) + 1
    dy = y - (nave - 1) * paso_nave
    paso = m["cama_alto"] + m["sep_camas"]
    k = int(dy // paso)
    if k >= g["camas_por_nave"] or dy - k * paso > m["cama_alto"]:
        return None
    return U.cama_id(bloque, nave, (nave - 1) * g["camas_por_nave"] + k + 1)
