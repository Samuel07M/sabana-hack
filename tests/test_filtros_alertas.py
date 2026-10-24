"""Alertas solo muestra riesgo_7d y confirmacion; Trazabilidad solo seguimiento, ventilacion y descartada."""
from hub import alertas as A
from hub import db

CORRIDAS = ("demo", "temporada-7", "celular-12")


def test_pantalla_alertas(finca_db):
    for c in CORRIDAS:
        df = A.de_pantalla(c)
        assert len(df) and set(df["tipo"]) == {"riesgo_7d", "confirmacion"}
        assert set(A.de_pantalla(c, estado="nueva")["estado"]) == {"nueva"}
        assert set(A.de_pantalla(c, tipo="seguimiento")["tipo"]) <= {"riesgo_7d", "confirmacion"}
        assert A.de_pantalla(c, bloque="2")["cama_id"].str.startswith("B2-").all()
        assert list(df["hora"]) == sorted(df["hora"], reverse=True)


def test_trazabilidad(finca_db):
    for c in CORRIDAS:
        df = A.de_trazabilidad(c)
        assert len(df) and set(df["tipo"]) == {"seguimiento", "ventilacion", "descartada"}
        for t in A.TIPOS_TRAZA:
            assert set(A.de_trazabilidad(c, t)["tipo"]) == {t}


def test_entre_las_dos_estan_todas(finca_db):
    for c in CORRIDAS:
        assert len(A.de_pantalla(c)) + len(A.de_trazabilidad(c)) == len(db.alertas(c))
