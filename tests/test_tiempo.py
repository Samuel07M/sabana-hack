"""Hora simulada → día, fecha y textos."""
from hub import tiempo as T

INI = "2026-11-01T00:00:00"


def test_dia():
    assert T.dia(0) == 0
    assert T.dia(23) == 0
    assert T.dia(24) == 1
    assert T.dia(78.5) == 3


def test_textos():
    assert T.hhmm(14) == "14:00"
    assert T.hhmm(30.5) == "06:30"
    assert T.corta(0, INI) == "1 nov"
    assert T.etiqueta(38, INI) == "2 nov · 14:00"
    assert T.etiqueta(None) == "—"
    assert T.fecha_larga(0, INI) == "Domingo, 1 de noviembre de 2026"
    assert T.fecha_larga(24 * 30, INI) == "Martes, 1 de diciembre de 2026"


def test_hace():
    assert T.hace(10, 10.5) == "hace menos de 1 h"
    assert T.hace(10, 15) == "hace 5 h"
    assert T.hace(0, 72) == "hace 3 días"
    assert T.hace(None, 5) == "—"
