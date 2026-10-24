"""Tour guiado: recorre los pasos pausando en cada hito, ?paso=N, falta de la corrida demo y tope de reproducción."""
import sqlite3
from pathlib import Path

from streamlit.testing.v1 import AppTest

from dashboard.tour.pasos import PASOS
from hub import db

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


def _app(**query) -> AppTest:
    """App con los parámetros de URL dados."""
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in query.items():
        at.query_params[k] = v
    return at.run()


def _evento(at: AppTest, accion: str, n: list) -> AppTest:
    """Simula un evento del recuadro (el componente no corre en AppTest)."""
    n[0] += 1
    at.session_state["tour_evento"] = {"accion": accion, "n": f"t{n[0]}"}
    return at.run()


def test_tour_completo(finca_db):
    at, n = _app(tour="1"), [0]
    assert not at.exception, at.exception
    assert at.session_state["tour"]["paso"] == 0
    vistos, topes = [], []
    for _ in range(len(PASOS) * 40):
        t = at.session_state["tour"]
        if t is None:
            break
        if t["buscando"]:
            at = _evento(at, "tick", n)
        else:
            if not vistos or vistos[-1] != t["paso"]:
                vistos.append(t["paso"])
                r = at.session_state["repro"]
                topes.append(r["tope"] if r else None)
            at = _evento(at, "siguiente", n)
        assert not at.exception, at.exception
    assert vistos == list(range(len(PASOS)))
    demo = [h for h in topes if h is not None]
    assert demo == sorted(demo)                         # la simulación nunca retrocede
    assert at.session_state["repro"]["play"] is True    # al salir la simulación sigue corriendo


def test_paso_por_url_y_anterior(finca_db):
    at, n = _app(paso="6"), [0]
    assert not at.exception, at.exception
    t = at.session_state["tour"]
    assert t["paso"] == 5
    hito5 = PASOS[4].hito("demo", 0.0)
    assert at.session_state["repro"]["tope"] >= (hito5 or 0)
    while at.session_state["tour"]["buscando"]:
        at = _evento(at, "tick", n)
    tope = at.session_state["repro"]["tope"]
    at = _evento(at, "anterior", n)
    assert at.session_state["tour"]["paso"] == 4
    assert at.session_state["repro"]["tope"] == tope    # Anterior no rebobina
    at = _evento(at, "salir", n)
    assert at.session_state["tour"] is None and not at.exception


def test_sin_corrida_demo(finca_db):
    with sqlite3.connect(finca_db) as con:
        con.execute("DELETE FROM corridas WHERE corrida_id='demo'")
    at = _app(corrida="celular-12", tour="1")
    assert not at.exception, at.exception
    assert "demo" in at.session_state["tour"]["error"]


def test_tour_apagado_por_url(finca_db):
    at = _app(tour="0")
    assert not at.exception
    assert at.session_state["tour"] is None and at.session_state["tour_auto"]


def test_tope_oculta_lo_posterior(finca_db):
    try:
        db.fijar_tope(10.0)
        assert db.ahora("demo") <= 10.0
        assert (db.alertas("demo")["hora"] <= 10.0).all()
        inc = db.incidencias("demo")
        assert inc.empty or (inc["hora_creada"] <= 10.0).all()
        assert not (inc["hora_confirmada"] > 10.0).any()
    finally:
        db.fijar_tope(None)
    assert db.ahora("demo") == db.ahora_real("demo")


def test_bateria_en_porcentaje():
    from dashboard.componentes.panorama import bateria_pct
    assert bateria_pct(0.8) == 80 and bateria_pct(1.0) == 100     # simulador: fracción
    assert bateria_pct(52) == 52 and bateria_pct(100) == 100      # mock: porcentaje


def test_selector_de_bloque(finca_db):
    at = _app(corrida="demo", tour="0")
    boton = [b for b in at.button if b.key == "sg_bloque_3"]
    assert boton
    boton[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["bloque"] == 3


def test_play_vuelve_a_empezar_al_final(finca_db):
    at, n = _app(paso="12"), [0]
    at = _evento(at, "salir", n)
    r = at.session_state["repro"]
    assert r["play"] is True
    real = db.ahora_real("demo")
    r.update(tope=real, real=real, t_real=0.0)                     # llegó al final y la corrida ya no crece
    at = _evento(at, "tick", n)
    assert at.session_state["repro"]["tope"] == 0.0 and not at.exception
