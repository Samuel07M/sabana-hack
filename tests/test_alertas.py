"""Ciclo de vida de alertas: transiciones solo hacia adelante y acciones permitidas por tipo."""
import sqlite3

from hub import alertas as A


def test_transiciones():
    assert A.puede_pasar("nueva", "vista")
    assert A.puede_pasar("nueva", "resuelta")
    assert A.puede_pasar("vista", "resuelta")
    assert not A.puede_pasar("vista", "nueva")
    assert not A.puede_pasar("resuelta", "vista")
    assert not A.puede_pasar("resuelta", "nueva")
    assert not A.puede_pasar("nueva", "nueva")
    assert not A.puede_pasar("nueva", "borrada")


def test_acciones_por_tipo():
    assert A.acciones("riesgo_7d") == ["inspeccion_priorizada", "monitorear", "ignorar"]
    assert A.acciones("confirmacion") == ["tratamiento_programado", "tratamiento_aplicado"]
    assert A.acciones("seguimiento") == ["continuar_seguimiento", "retratar"]
    assert A.acciones("ventilacion") == ["entendido"]
    assert A.acciones("descartada") == ["entendido"]
    assert not A.accion_valida("ventilacion", "apagar_48h")
    assert not A.accion_valida("ventilacion", "mantener_encendida")
    assert not A.accion_valida("riesgo_7d", "entendido")


def _una(ruta, tipo):
    """alerta_id de una alerta nueva del tipo."""
    return sqlite3.connect(ruta).execute("SELECT alerta_id FROM alertas WHERE tipo=? AND estado='nueva' LIMIT 1",
                                         (tipo,)).fetchone()[0]


def _estado(ruta, aid):
    """(estado, accion) de una alerta."""
    return sqlite3.connect(ruta).execute("SELECT estado, accion FROM alertas WHERE alerta_id=?", (aid,)).fetchone()


def test_vista_y_resolver(finca_db):
    aid = _una(finca_db, "riesgo_7d")
    assert A.marcar_vista(aid)
    assert _estado(finca_db, aid) == ("vista", None)
    assert not A.marcar_vista(aid)
    assert not A.resolver(aid, "entendido")
    assert _estado(finca_db, aid) == ("vista", None)
    assert A.resolver(aid, "monitorear")
    assert _estado(finca_db, aid) == ("resuelta", "monitorear")
    assert not A.resolver(aid, "ignorar")
    assert not A.marcar_vista(aid)
    assert _estado(finca_db, aid) == ("resuelta", "monitorear")


def test_resolver_desde_nueva(finca_db):
    aid = _una(finca_db, "confirmacion")
    assert A.resolver(aid, "tratamiento_programado")
    assert _estado(finca_db, aid) == ("resuelta", "tratamiento_programado")


def test_ventilacion_solo_entendido(finca_db):
    aid = _una(finca_db, "ventilacion")
    assert not A.resolver(aid, "apagar_48h")
    assert A.resolver(aid, "entendido")
    assert _estado(finca_db, aid) == ("resuelta", "entendido")


def test_alerta_inexistente(finca_db):
    assert not A.marcar_vista(10 ** 9)
    assert not A.resolver(10 ** 9, "entendido")
