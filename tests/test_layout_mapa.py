"""Geometría de dibujo del mapa: camas horizontales apiladas, pasillo central y conversión cama ↔ punto."""
import pytest

from dashboard.componentes.mapa3d import layout as LY
from hub import ubicacion as U
from hub.config import cargar

G = cargar()["geometria"]
P = G["plantas_por_cama"]
CAMAS = [(n, c) for n in range(1, G["naves_por_bloque"] + 1)
         for c in range((n - 1) * G["camas_por_nave"] + 1, n * G["camas_por_nave"] + 1)]


def _solapan(a, b) -> bool:
    """True si dos rectángulos (x, y, ancho, alto) comparten área."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _dentro(p, r) -> bool:
    """True si el punto está dentro del rectángulo."""
    return r[0] <= p[0] <= r[0] + r[2] and r[1] <= p[1] <= r[1] + r[3]


def test_72_camas_horizontales_sin_solaparse():
    assert len(CAMAS) == 72
    pasillo = LY.rect_pasillo(1)
    rects = [LY.rect_cama(1, n, c) for n, c in CAMAS]
    mitades = [m for n, c in CAMAS for m in LY.mitades_cama(1, n, c)]
    assert all(r[2] > r[3] for r in rects + mitades)
    assert all(4 <= m[2] / m[3] <= 6 for m in mitades)                 # cada mitad, entre 4:1 y 6:1
    assert not any(_solapan(a, b) for i, a in enumerate(rects) for b in rects[i + 1:])
    assert not any(_solapan(m, pasillo) for m in mitades)
    assert not any(_solapan(a, b) for i, a in enumerate(mitades) for b in mitades[i + 1:])


def test_pasillo_continuo_por_todo_el_bloque():
    x, y, w, h = LY.rect_pasillo(1)
    ancho, alto = LY.dimensiones(1)
    assert (y, h) == (0.0, alto) and 0 < x and x + w < ancho
    for n, c in CAMAS:
        izq, der = LY.mitades_cama(1, n, c)
        assert izq[0] + izq[2] == x and der[0] == x + w


def test_orden_de_arriba_hacia_abajo():
    ys = [LY.rect_cama(1, n, c)[1] for n, c in CAMAS]
    assert ys == sorted(ys) and len(set(ys)) == len(ys)
    nave2 = [c for n, c in CAMAS if n == 2]
    y2 = {c: LY.rect_cama(1, 2, c)[1] for c in nave2}
    assert min(y2, key=y2.get) == 13 and max(y2, key=y2.get) == 24
    assert LY.rect_nave(1, 2)[1] == LY.rect_cama(1, 2, 13)[1]
    with pytest.raises(ValueError):
        LY.rect_cama(1, 2, 25)                                         # la cama 25 es de la nave 3


def test_posiciones_a_cada_lado_del_pasillo():
    x, _, w, _ = LY.rect_pasillo(1)
    for n, c in CAMAS:
        izq, der = LY.mitades_cama(1, n, c)
        for pos in (1, P // 2):
            p = LY.punto_planta(1, n, c, pos)
            assert p[0] < x and _dentro(p, izq)
        for pos in (P // 2 + 1, P):
            p = LY.punto_planta(1, n, c, pos)
            assert p[0] > x + w and _dentro(p, der)
    xs = [LY.punto_planta(1, 2, 14, pos)[0] for pos in range(1, P + 1)]
    assert xs == sorted(xs)                                            # 1 en el borde izquierdo, P en el derecho
    with pytest.raises(ValueError):
        LY.punto_planta(1, 2, 14, P + 1)


def test_ida_y_vuelta_cama_id():
    for b in range(1, G["bloques"] + 1):
        for n, c in CAMAS:
            cid = U.cama_id(b, n, c)
            bb, nn, cc = U.partes(cid)
            x, y, w, h = LY.rect_cama(bb, nn, cc)
            assert LY.cama_en_punto(x + w / 2, y + h / 2, bloque=b) == cid
            for m in LY.mitades_cama(bb, nn, cc):
                assert LY.cama_en_punto(m[0] + m[2] / 2, m[1] + m[3] / 2, bloque=b) == cid
    m = cargar()["dashboard"]["mapa"]
    x, y, w, h = LY.rect_cama(1, 1, 12)
    assert LY.cama_en_punto(x + w / 2, y + h + m["sep_naves"] / 2) is None        # entre la nave 1 y la 2
    assert LY.cama_en_punto(-1, 0) is None


def test_robot_sobre_el_pasillo():
    x, _, w, _ = LY.rect_pasillo(1)
    xs = {LY.punto_robot(1, n, c)[0] for n, c in CAMAS}
    assert xs == {x + w / 2}                       # todas las camas sobre el mismo eje: ir de una a otra es recorrer el pasillo
    for n, c in CAMAS:
        assert _dentro(LY.punto_robot(1, n, c), LY.rect_cama(1, n, c))


def test_flecha_de_aire_de_arriba_hacia_abajo():
    for n in range(1, G["naves_por_bloque"] + 1):
        (x0, y0), (x1, y1) = LY.flecha_aire(1, n)
        primera, ultima = (n - 1) * G["camas_por_nave"] + 1, n * G["camas_por_nave"]
        assert x0 == x1 > LY.dimensiones(1)[0]                        # a la derecha de la nave
        assert y0 < y1                                                 # aguas abajo = número de cama mayor = más abajo
        assert _dentro((LY.rect_cama(1, n, primera)[0], y0), LY.rect_cama(1, n, primera))
        assert _dentro((LY.rect_cama(1, n, ultima)[0], y1), LY.rect_cama(1, n, ultima))
