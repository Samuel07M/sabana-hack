"""Sincronizar llena hora_recibida, deja ver lo pendiente y no duplica."""
import sqlite3

from hub import celular, db

C = "celular-12"


def _recibidas(ruta):
    """{id: hora_recibida} de lo que ya había llegado."""
    return dict(sqlite3.connect(ruta).execute(
        "SELECT id, hora_recibida FROM cola_sync WHERE corrida_id=? AND hora_recibida IS NOT NULL", (C,)).fetchall())


def _total(ruta):
    """Filas de cola_sync de la corrida."""
    return sqlite3.connect(ruta).execute("SELECT COUNT(*) FROM cola_sync WHERE corrida_id=?", (C,)).fetchone()[0]


def test_sincronizar(finca_db):
    total, antes = _total(finca_db), _recibidas(finca_db)
    pend = len(db.cola_pendiente(C))
    alertas_antes = len(db.alertas(C))
    assert pend > 0
    assert db.corte(C) <= db.ahora(C)
    assert celular.sincronizar(C) == pend
    assert db.cola_pendiente(C).empty
    assert db.ultima_sync(C)["hora"].iloc[0] == int(db.ahora(C))
    assert db.corte(C) > db.ahora(C)
    assert len(db.alertas(C)) >= alertas_antes
    despues = _recibidas(finca_db)
    assert len(despues) == len(antes) + pend
    assert all(despues[i] == h for i, h in antes.items())
    assert celular.sincronizar(C) == 0
    assert _total(finca_db) == total
    assert _recibidas(finca_db) == despues


def test_otras_corridas_intactas(finca_db):
    assert celular.sincronizar("demo") == 0
    assert db.red("demo") == "local"
    assert db.red(C) == "sin_red"
