"""verdad_infectada nunca sale de hub/: ninguna consulta la devuelve y el dashboard no la nombra."""
from pathlib import Path

import pandas as pd

from hub import alertas, db

RAIZ = Path(__file__).resolve().parent.parent


def _resultados(c):
    """Todo lo que el dashboard puede pedirle al hub para una corrida."""
    h = db.ahora(c)
    yield db.riesgo_ultimo(c)
    yield db.riesgo_dia(c, 3)
    yield db.riesgo_cama(c, "B1-N2-C14")
    yield db.serie_riesgo(c)
    yield db.variables_cama(c, "B1-N2-C14")
    yield db.variables_bloque(c, 1)
    yield db.lecturas_cama(c, "B1-N2-C14", h - 72, h)
    yield db.clima_actual(c, "B1-N2-C14")
    yield db.clima_bloque(c, 1)
    yield db.alertas(c)
    yield db.incidencias(c)
    yield db.incidencias(c, grupo="abiertas")
    yield db.seguimientos(c)
    yield db.robots_actual(c)
    yield db.prioridades_robot(c, "B1")
    yield db.ultima_visita(c, "B1-N2-C14")
    yield db.ventilacion_actual(c)
    yield db.ventilacion_historial(c)
    yield db.cola_pendiente(c)
    yield db.ultima_sync(c)
    yield db.cobertura(c)
    yield db.metricas(c)
    yield db.corridas()
    yield db.camas()
    yield alertas.de_pantalla(c)
    yield alertas.de_trazabilidad(c)


def test_ninguna_consulta_la_devuelve(finca_db):
    for c in ("demo", "temporada-7", "celular-12"):
        for df in _resultados(c):
            assert isinstance(df, pd.DataFrame)
            assert "verdad_infectada" not in df.columns
            assert not any("verdad" in str(col) for col in df.columns)


def test_el_dashboard_no_la_nombra():
    for p in (RAIZ / "dashboard").rglob("*"):
        if p.suffix in (".py", ".html", ".js", ".css"):
            assert "verdad" not in p.read_text(encoding="utf-8"), p
