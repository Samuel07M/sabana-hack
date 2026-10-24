"""Nombre de enfermedad por bloque: solo cambia el texto en pantalla, no los datos."""
from hub import db
from hub import enfermedades as E


def test_nombre_por_bloque():
    assert E.de_cama("B1-N2-C14") == "Botrytis"
    assert E.de_cama("B2-N1-C01") == "Mildiú polvoso"
    assert E.de_cama("B3-N1-C01") == "Neofusicoccum spp."
    assert E.de_cama("B4-N6-C72") == "Phytophthora cinnamomi"
    assert E.de_cama(None) == "Botrytis"


def test_alertas_reetiquetadas_sin_cambiar_la_base(finca_db):
    al = db.alertas("temporada-7")
    assert len(al)
    for r in al.itertuples():
        nombre = E.de_cama(r.cama_id)
        if nombre != "Botrytis":
            assert "Botrytis" not in (r.titulo or "") and "Botrytis" not in (r.mensaje or "")
    import sqlite3
    with sqlite3.connect(finca_db) as con:                       # la base sigue diciendo Botrytis
        crudo = con.execute("SELECT COUNT(*) FROM alertas WHERE titulo LIKE '%Botrytis%'").fetchone()[0]
    assert crudo > 0
