"""Pruebas de la Fase 1: config, geometría, escritor y CLI."""
import re
import sqlite3

import pytest

from sim import escritor, geometria, run_temporada
from sim.config import cargar_config


@pytest.fixture(scope="module")
def cfg():
    return cargar_config()


@pytest.fixture(scope="module")
def camas(cfg):
    return geometria.listar_camas(cfg)


def test_288_camas_y_11520_plantas(cfg, camas):
    assert len(camas) == 288
    assert len(camas) * cfg["geometria"]["plantas_por_cama"] == 11520


def test_numeracion_continua_dentro_del_bloque(camas):
    por_id = {c["cama_id"]: c for c in camas}
    assert por_id["B1-N2-C14"]["nave"] == 2
    nave6 = sorted(c["cama"] for c in camas if c["bloque"] == 1 and c["nave"] == 6)
    assert nave6 == list(range(61, 73))
    assert len({c["cama_id"] for c in camas}) == 288


def test_es_borde_solo_primera_y_ultima_de_la_nave(camas):
    bordes = {(c["bloque"], c["nave"], c["cama"]) for c in camas if c["es_borde"]}
    esperados = {(b, n, c) for b in range(1, 5) for n in range(1, 7)
                 for c in ((n - 1) * 12 + 1, n * 12)}
    assert bordes == esperados


def test_tablas_e_indices_coinciden_con_el_contrato(cfg, tmp_path):
    sql = escritor.SCHEMA.read_text(encoding="utf-8")
    tablas = set(re.findall(r"CREATE TABLE (\w+)", sql))
    indices = set(re.findall(r"CREATE INDEX (\w+)", sql))
    con = escritor.crear_base(tmp_path / "t.db", cfg)
    try:
        en_db = lambda tipo: {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type=? AND name NOT LIKE 'sqlite_%'", (tipo,))}
        assert en_db("table") == tablas and len(tablas) == 10
        assert en_db("index") == indices and len(indices) == 3
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        con.close()


def test_recrear_la_base_borra_la_anterior(cfg, tmp_path):
    ruta = tmp_path / "t.db"
    con = escritor.crear_base(ruta, cfg)
    escritor.insertar_camas(con, geometria.listar_camas(cfg))
    con.close()
    con = escritor.crear_base(ruta, cfg, recrear=True)
    assert escritor.contar_filas(con)["camas"] == 0
    con.close()


def test_por_defecto_la_base_se_conserva(cfg, tmp_path):
    ruta = tmp_path / "t.db"
    con = escritor.crear_base(ruta, cfg)
    escritor.insertar_camas(con, geometria.listar_camas(cfg))
    con.close()
    con = escritor.crear_base(ruta, cfg)
    assert escritor.contar_filas(con)["camas"] == 288
    con.close()


def test_run_temporada_dias_1(tmp_path):
    db = tmp_path / "finca.db"
    run_temporada.main(["--dias", "1", "--db", str(db)])
    con = sqlite3.connect(db)
    filas = escritor.contar_filas(con)
    con.close()
    assert filas["corridas"] == 1 and filas["camas"] == 288
    assert filas["lecturas"] >= 24 * 4                      # un sensor central por bloque por hora
    assert (tmp_path / "verdad_temporada-7.parquet").exists()


def test_escenario_invalido_en_el_escritor(cfg, tmp_path):
    con = escritor.crear_base(tmp_path / "t.db", cfg)
    with pytest.raises(ValueError, match="escenario"):
        escritor.insertar_corrida(con, "x", "temporada", "inventado", 1, cfg)
    con.close()


def test_config_invalida_nombra_la_clave(tmp_path):
    malo = tmp_path / "malo.yaml"
    malo.write_text("riesgo: {umbral_alto: 1.5}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="riesgo.umbral_alto"):
        cargar_config(malo)


def test_config_rango_invertido(tmp_path):
    malo = tmp_path / "malo.yaml"
    malo.write_text("enfermedad: {latencia_dias: [14, 7]}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="enfermedad.latencia_dias"):
        cargar_config(malo)


def test_config_encima_sobrescribe_solo_lo_indicado(tmp_path):
    demo = tmp_path / "demo.yaml"
    demo.write_text("geometria: {bloques: 1}\n", encoding="utf-8")
    cfg = cargar_config(demo)
    assert cfg["geometria"]["bloques"] == 1
    assert cfg["geometria"]["naves_por_bloque"] == 6
