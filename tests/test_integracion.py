"""Integración: lo que escribe el simulador lo lee el hub y lo muestra el tablero (sin la base mock)."""
import json
import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from hub import celular, db
from sim.config import cargar_config
from sim.run_temporada import correr

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")
CORRIDAS = {"temporada-9": ("robots", 9), "celular-12": ("robots_celular", 12)}


@pytest.fixture(scope="module")
def base_real(tmp_path_factory):
    """Base escrita por el simulador: una temporada con red local y otra sin red (10 días, con un foco temprano)."""
    cfg = cargar_config()
    cfg["sim"]["dias"] = 10
    cfg["enfermedad"]["focos_forzados"] = [{"cama_id": "B1-N1-C02", "posicion": 5, "hora": 0},
                                          {"cama_id": "B2-N3-C30", "posicion": 20, "hora": 12}]
    cfg["enfermedad"]["latencia_dias"] = [1, 2]
    ruta = tmp_path_factory.mktemp("integracion") / "finca.db"
    for corrida, (escenario, semilla) in CORRIDAS.items():
        correr(cfg, escenario, semilla, ruta, corrida, modelo=None)
    return ruta


@pytest.fixture
def finca(base_real, monkeypatch):
    """Apunta el hub y el tablero a la base del simulador."""
    monkeypatch.setenv("FINCA_DB", str(base_real))
    return base_real


def _consultas(c: str) -> dict:
    """Todas las consultas del hub que usa el tablero."""
    return {
        "riesgo_ultimo": db.riesgo_ultimo(c), "serie_riesgo": db.serie_riesgo(c), "clima_bloque": db.clima_bloque(c, 1),
        "variables_bloque": db.variables_bloque(c, 1), "alertas": db.alertas(c), "incidencias": db.incidencias(c),
        "seguimientos": db.seguimientos(c), "robots_actual": db.robots_actual(c),
        "prioridades_robot": db.prioridades_robot(c, "B1"), "ventilacion_actual": db.ventilacion_actual(c),
        "ventilacion_historial": db.ventilacion_historial(c), "cola_pendiente": db.cola_pendiente(c),
        "metricas": db.metricas(c), "lecturas_cama": db.lecturas_cama(c, "B1-N1-C02", 0, 240),
    }


def test_las_dos_corridas_quedan_en_la_misma_base(finca):
    assert set(db.corridas()["corrida_id"]) == set(CORRIDAS)
    assert db.red("temporada-9") == "local" and db.red("celular-12") == "sin_red"


@pytest.mark.parametrize("corrida", list(CORRIDAS))
def test_el_hub_lee_todo_lo_que_escribe_el_simulador(finca, corrida):
    r = _consultas(corrida)
    assert len(r["riesgo_ultimo"]) == 288 and len(r["robots_actual"]) == 4
    assert len(r["incidencias"]) > 0 and len(r["alertas"]) > 0
    assert "verdad_infectada" not in r["incidencias"].columns


@pytest.mark.parametrize("corrida", list(CORRIDAS))
@pytest.mark.parametrize("tab", ["finca", "alertas", "incidencias", "ventilacion", "analisis"])
def test_el_tablero_muestra_la_corrida_del_simulador(finca, corrida, tab):
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["corrida"] = corrida
    at.session_state["tab"] = tab
    at.run()
    assert not at.exception, at.exception


def test_detalle_de_cama_con_datos_del_simulador(finca):
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["corrida"] = "temporada-9"
    at.session_state["cama"] = "B1-N1-C02"
    at.run()
    assert not at.exception, at.exception


def test_con_red_local_no_hay_cola(finca):
    con = sqlite3.connect(finca)
    assert con.execute("SELECT COUNT(*) FROM cola_sync WHERE corrida_id='temporada-9'").fetchone()[0] == 0
    con.close()


def test_sin_red_se_ve_hasta_la_ultima_sincronizacion(finca):
    c = "celular-12"
    assert db.corte(c) <= db.ahora(c)                          # lo posterior a la última pasada está oculto
    assert len(db.cola_pendiente(c)) > 0
    con = sqlite3.connect(finca)
    fotos = [json.loads(p) for (p,) in con.execute(
        "SELECT payload FROM cola_sync WHERE corrida_id=? AND tipo='inspeccion' ORDER BY id", (c,))]
    con.close()
    assert fotos and all("estado" in f and "verdad_infectada" not in f for f in fotos)


def test_pasa_el_celular_pone_al_dia_el_tablero(finca):
    c = "celular-12"
    antes = len(db.incidencias(c))
    assert celular.sincronizar(c) > 0
    assert db.cola_pendiente(c).empty and db.corte(c) > db.ahora(c)
    assert len(db.incidencias(c)) >= antes
