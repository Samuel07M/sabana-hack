"""El mock cumple contrato/schema.sql y cubre todos los estados, tipos y severidades."""
import sqlite3

from hub.config import cargar
from hub.mock import SCHEMA

TIPOS = {"riesgo_7d", "confirmacion", "seguimiento", "ventilacion", "descartada"}
SEVERIDADES = {"info", "advertencia", "critica"}
ESTADOS_INC = {"sospecha", "confirmada", "en_tratamiento", "en_seguimiento", "cerrada", "descartada"}


def _columnas(con):
    """{tabla: [(columna, tipo)]} de una base."""
    tablas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {t: [(c[1], c[2]) for c in con.execute(f"PRAGMA table_info({t})")] for t in tablas}


def _valores(con, sql):
    """Conjunto de valores de la primera columna."""
    return {r[0] for r in con.execute(sql)}


def _contrato():
    """Base vacía creada con contrato/schema.sql."""
    ref = sqlite3.connect(":memory:")
    ref.executescript(SCHEMA.read_text(encoding="utf-8"))
    return ref


def test_contrato_tal_cual(base_mock):
    con = sqlite3.connect(base_mock["ruta"])
    assert _columnas(con) == _columnas(_contrato())
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_valores_permitidos(base_mock):
    con = sqlite3.connect(base_mock["ruta"])
    assert _valores(con, "SELECT tipo FROM alertas") == TIPOS
    assert _valores(con, "SELECT severidad FROM alertas") == SEVERIDADES
    assert _valores(con, "SELECT estado FROM alertas") == {"nueva"}
    assert _valores(con, "SELECT nivel FROM riesgo") == {"bajo", "medio", "alto"}
    assert _valores(con, "SELECT origen FROM incidencias") == {"prediccion", "patrulla"}
    assert _valores(con, "SELECT estado FROM incidencias") <= ESTADOS_INC
    assert _valores(con, "SELECT resultado FROM seguimientos") == {"empeora", "igual", "mejora", "limpia"}
    assert _valores(con, "SELECT estado FROM drones") == {"patrulla", "prioridad", "inspeccionando", "carga"}
    assert _valores(con, "SELECT estado FROM ventilacion") == {"encendida", "apagada"}
    assert _valores(con, "SELECT tipo FROM cola_sync") == {"lectura", "inspeccion", "seguimiento"}
    assert _valores(con, "SELECT hora_recibida IS NULL FROM cola_sync") == {0, 1}
    assert _valores(con, "SELECT fuente FROM lecturas") == {"sensor_fijo", "dron:B1", "dron:B2", "dron:B3", "dron:B4"}
    motivos = _valores(con, "SELECT motivo FROM ventilacion")
    assert all(m.startswith("auto: incidencia #") or m == "auto: fin de apagado" for m in motivos)


def test_severidades_del_yaml(base_mock):
    sev = cargar()["alertas"]["severidad"]
    con = sqlite3.connect(base_mock["ruta"])
    for tipo, s in con.execute("SELECT DISTINCT tipo, severidad FROM alertas"):
        assert s in (sev[tipo], sev.get(f"{tipo}_empeora"))
    filas = con.execute("SELECT a.severidad FROM alertas a JOIN seguimientos g ON a.incidencia_id=g.incidencia_id "
                        "AND a.hora=g.hora WHERE a.tipo='seguimiento' AND g.resultado='empeora'").fetchall()
    assert filas and {s for (s,) in filas} == {sev["seguimiento_empeora"]} == {"critica"}


def test_todos_los_estados_de_incidencia(base_mock):
    vistos = set().union(*base_mock["estados_vistos"].values())
    assert vistos == ESTADOS_INC


def test_tres_corridas(base_mock):
    con = sqlite3.connect(base_mock["ruta"])
    assert con.execute("SELECT corrida_id, escenario FROM corridas ORDER BY corrida_id").fetchall() == [
        ("celular-12", "drones_celular"), ("demo", "demo"), ("temporada-7", "drones")]
    assert con.execute("SELECT COUNT(*) FROM camas").fetchone()[0] == 4 * 6 * 12
    assert con.execute("SELECT COUNT(*) FROM cola_sync WHERE corrida_id!='celular-12'").fetchone()[0] == 0


def test_guion_de_la_demo(base_mock):
    con = sqlite3.connect(base_mock["ruta"])
    q = lambda sql: con.execute(sql).fetchone()[0]
    riesgo = q("SELECT MIN(hora) FROM alertas WHERE corrida_id='demo' AND tipo='riesgo_7d' AND cama_id='B1-N2-C14'")
    prio = q("SELECT MIN(hora) FROM drones WHERE corrida_id='demo' AND dron_id='B1' AND estado='prioridad' "
             "AND cama_id='B1-N2-C14'")
    conf = q("SELECT MIN(hora) FROM alertas WHERE corrida_id='demo' AND tipo='confirmacion' AND cama_id='B1-N2-C14'")
    vent = q("SELECT MIN(hora) FROM ventilacion WHERE corrida_id='demo' AND bloque=1 AND nave=2 AND estado='apagada'")
    mejora = q("SELECT MIN(g.hora) FROM seguimientos g JOIN incidencias i USING (incidencia_id) "
               "WHERE g.corrida_id='demo' AND i.cama_id='B1-N2-C14' AND g.resultado='mejora'")
    assert None not in (riesgo, prio, conf, vent, mejora)
    assert riesgo <= prio <= conf == vent < mejora
    assert q("SELECT estado FROM incidencias WHERE corrida_id='demo' AND cama_id='B1-N2-C14' "
             "ORDER BY incidencia_id LIMIT 1") == "cerrada"


def _texto(con, tipo):
    """(titulo, mensaje) de la primera alerta del tipo en la cama del guion."""
    return con.execute("SELECT titulo, mensaje FROM alertas WHERE corrida_id='demo' AND tipo=? "
                       "AND cama_id='B1-N2-C14' ORDER BY hora, alerta_id LIMIT 1", (tipo,)).fetchone()


def test_textos_de_alertas(base_mock):
    con = sqlite3.connect(base_mock["ruta"])
    t, m = _texto(con, "riesgo_7d")
    assert t == "Riesgo alto de Botrytis · B1 · Nave 2 · Cama 14"
    assert m.startswith("B1 · Nave 2 · Cama 14: alto riesgo de Botrytis en los próximos 7 días (prob. ")
    assert "). HR > 95 % durante " in m and m.endswith(" h.")
    t, m = _texto(con, "confirmacion")
    assert t == "Botrytis confirmada · B1 · Nave 2 · Cama 14"
    assert m == "Botrytis confirmada · B1 · Nave 2 · Cama 14 · posición 22. 3 plantas afectadas (confianza 0.88)."
    t, m = _texto(con, "ventilacion")
    assert t == "Ventilación apagada · B1 · Nave 2"
    assert m.startswith("Se apagó la ventilación de B1 · Nave 2 por 48 h tras confirmar Botrytis en la Cama 14 "
                        "(incidencia #")
    assert m.endswith("para frenar el transporte de esporas por el aire. Vigile la humedad de la nave.")
    t, m = _texto(con, "seguimiento")
    assert t == "Seguimiento · Mejora · B1 · Nave 2 · Cama 14"
    assert m == "Revisita automática n.º 1 · B1 · Nave 2 · Cama 14: mejora (1 planta afectada; antes 3)."


def test_sin_verdad_por_planta(base_mock):
    con = sqlite3.connect(base_mock["ruta"])
    assert set(_columnas(con)) == set(_columnas(_contrato()))
    assert con.execute("SELECT COUNT(*) FROM cola_sync WHERE payload LIKE '%verdad%'").fetchone()[0] == 0
