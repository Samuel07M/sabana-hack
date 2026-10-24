"""El dashboard carga sin errores en cada pantalla, corrida y en el detalle de cama (streamlit AppTest)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def _correr(corrida: str, **estado) -> AppTest:
    """Corre la app con la corrida y el estado de sesión dados."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["corrida"] = corrida
    for k, v in estado.items():
        at.session_state[k] = v
    return at.run()


@pytest.mark.parametrize("tab", ["finca", "alertas", "incidencias", "ventilacion", "analisis"])
def test_pantallas(finca_db, tab):
    for corrida in ("demo", "celular-12"):
        at = _correr(corrida, tab=tab)
        assert not at.exception, at.exception


def test_detalle_de_cama(finca_db):
    at = _correr("demo", cama="B1-N2-C14")
    assert not at.exception, at.exception


def test_pasa_el_celular_solo_sin_red(finca_db):
    assert not [b for b in _correr("demo").button if b.key == "celular"]
    at = _correr("celular-12")
    boton = [b for b in at.button if b.key == "celular"]
    assert boton
    boton[0].click().run()
    assert not at.exception
    from hub import db
    assert db.cola_pendiente("celular-12").empty


def test_corrida_desconocida(finca_db):
    at = _correr("no-existe")
    assert not at.exception
