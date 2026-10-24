"""Conversiones de identificadores y numeración continua de camas."""
import pytest

from hub import ubicacion as U


def test_ida_y_vuelta():
    assert U.cama_id(1, 2, 14) == "B1-N2-C14"
    assert U.cama_id(3, 1, 5) == "B3-N1-C05"
    assert U.partes("B1-N2-C14") == (1, 2, 14)
    assert U.partes("B3-N1-C05") == (3, 1, 5)


def test_numeracion_continua():
    assert U.nave_de_cama(1) == 1
    assert U.nave_de_cama(12) == 1
    assert U.nave_de_cama(13) == 2
    assert U.nave_de_cama(14) == 2
    assert U.nave_de_cama(61) == 6
    assert U.nave_de_cama(72) == 6
    assert U.cama_en_nave(14) == 2
    assert U.cama_en_nave(24) == 12


def test_textos():
    assert U.legible("B1-N2-C14") == "Bloque 1 · Nave 2 · Cama 14"
    assert U.corto("B1-N2-C14") == "B1 · Nave 2 · Cama 14"
    assert U.sin_bloque("B1-N2-C14") == "Nave 2 · Cama 14"
    assert U.bloque_de(None) is None


def test_invalido():
    with pytest.raises(ValueError):
        U.partes("cama 14")
