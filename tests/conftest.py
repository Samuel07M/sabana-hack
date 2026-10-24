"""Fixtures compartidas: una base mock completa por sesión (hub/mock.py)."""
import shutil

import pytest

from hub.config import cargar
from hub.mock import abrir_base, preparar


@pytest.fixture(scope="session")
def base_mock(tmp_path_factory):
    """Base mock de prueba con las tres corridas y los estados de incidencia vistos durante la simulación."""
    cfg = cargar()
    ruta = tmp_path_factory.mktemp("mock") / "mock.db"
    con = abrir_base(ruta, cfg)
    vistos: dict[str, set] = {}
    for c in cfg["dashboard"]["mock"]["corridas"]:
        src = preparar(con, c, cfg)
        estados = vistos.setdefault(c["corrida_id"], set())
        while src.step():
            estados.update(i["estado"] for i in src.inc.values())
            if src.hora % 24 == 0:
                src.escribir(con)
        src.escribir(con)
    con.close()
    return {"ruta": ruta, "estados_vistos": vistos}


@pytest.fixture
def finca_db(base_mock, tmp_path, monkeypatch):
    """Copia de la base mock apuntada por FINCA_DB (cada prueba puede escribir en la suya)."""
    ruta = tmp_path / "finca.db"
    shutil.copy(base_mock["ruta"], ruta)
    monkeypatch.setenv("FINCA_DB", str(ruta))
    return ruta
