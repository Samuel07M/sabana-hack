"""Pruebas de variables, etiquetas, reglas y entrenamiento."""
import inspect

import numpy as np
import pandas as pd
import pytest

from prediccion import entrenar, etiquetas, reglas, variables
from sim import geometria
from sim.config import cargar_config
from tests.test_sim import cfg_chica


def _entradas(cfg, horas=80):
    geo = geometria.construir(cfg)
    rng = np.random.default_rng(0)
    T = (15 + rng.normal(0, 1, (horas, geo.n_camas))).astype(np.float32)
    HR = (88 + rng.normal(0, 4, (horas, geo.n_camas))).astype(np.float32)
    return geo, T, HR, np.full(geo.n_camas, -10 ** 6)


def test_variables_no_recibe_ni_lee_la_verdad():
    cfg = cfg_chica()
    geo, T, HR, ult = _entradas(cfg)
    params = inspect.signature(variables.construir).parameters
    assert not any("verdad" in p or "estado" in p or "enf" in p for p in params)
    df = variables.construir(cfg, geo, 79, T, HR, ult, np.zeros(geo.n_camas, bool), np.ones(geo.n_naves, bool))
    assert list(df.columns) == list(variables.VARIABLES) and len(df) == geo.n_camas
    assert df.notna().all().all()


def test_distancia_a_confirmada_es_99_si_no_hay_y_cuenta_camas():
    cfg = cfg_chica()
    geo, T, HR, ult = _entradas(cfg)
    conf = np.zeros(geo.n_camas, bool)
    df = variables.construir(cfg, geo, 79, T, HR, ult, conf, np.ones(geo.n_naves, bool))
    assert (df["distancia_a_confirmada_en_nave"] == 99).all()
    conf[1] = True
    df = variables.construir(cfg, geo, 79, T, HR, ult, conf, np.ones(geo.n_naves, bool))
    assert df["distancia_a_confirmada_en_nave"].tolist()[:4] == [1, 0, 1, 2]
    assert (df["distancia_a_confirmada_en_nave"].iloc[4:] == 99).all()        # otra nave
    assert df["confirmadas_misma_cama"].iloc[1] == 1 and df["confirmadas_camas_vecinas"].iloc[0] == 1


def test_etiqueta_167h_si_169h_no():
    cambios = np.array([[167, 0, 1], [169, 5, 1], [10, 9, 2]])
    cama_de_planta = np.arange(10) // 5
    y = etiquetas.etiquetas(cambios, cama_de_planta, 2, 500, 0, 168)
    assert y.tolist() == [1, 0]


def test_indice_de_broome_del_pdf():
    cfg = cargar_config()
    assert reglas.indice_broome(24, 12.0, cfg) == pytest.approx(0.87, abs=0.01)
    assert reglas.indice_broome(12, 18.0, cfg) == pytest.approx(0.28, abs=0.01)
    assert reglas.nivel_broome(0.87, cfg) == "moderado" and reglas.nivel_broome(-1, cfg) == "nulo"


def test_riesgo_reglas_en_0_1_y_niveles():
    cfg = cfg_chica()
    geo, T, HR, ult = _entradas(cfg)
    df = variables.construir(cfg, geo, 79, T, HR, ult, np.ones(geo.n_camas, bool), np.ones(geo.n_naves, bool))
    r = reglas.riesgo_reglas(df, cfg)
    assert ((r >= 0) & (r <= 1)).all()
    assert reglas.nivel_de([0.1, 0.3, 0.6], cfg).tolist() == ["bajo", "medio", "alto"]


def test_semillas_de_entrenamiento_y_prueba_no_se_cruzan():
    t = cargar_config()["entrenamiento"]
    assert not set(entrenar.rango(t["semillas_train"])) & set(entrenar.rango(t["semillas_test"]))


def test_dataset_de_una_corrida_tiene_etiquetas_y_sin_semana_incompleta():
    from sim.motor import Simulacion
    cfg = cfg_chica(sim={"dias": 14})
    sim = Simulacion(cfg, "robots", 1, "t", modelo=None, recolectar=True)
    for h in range(sim.n_horas):
        sim.paso(h)
    d = entrenar.dataset_de_corrida(sim)
    assert set(d["y"]) <= {0, 1} and d["dia"].max() * 24 + 6 + 168 < sim.n_horas
    assert set(variables.VARIABLES) <= set(d.columns)
    m = entrenar.metricas(pd.DataFrame({"y": [0, 1, 0, 1], "semilla": 0, "dia": [0, 0, 1, 1]}),
                          np.array([.1, .9, .2, .8]), 1)
    assert m["auc"] == 1.0 and m["top_k"] == 1.0
