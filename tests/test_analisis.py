"""Pruebas de métricas, bootstrap y gráficas."""
import numpy as np
import pandas as pd
import pytest

from analisis import graficas, metricas, validar
from sim.config import cargar_config
from tests.test_sim import cfg_chica, correr


def test_metricas_de_una_corrida_chica():
    sim = correr(cfg_chica(sim={"dias": 30}))
    m = metricas.extraer(sim)
    assert 0 <= m["afectadas_final"] <= m["afectadas_pico"] <= 1
    assert m["confirmaciones"] >= 1 and m["camas_infectadas"] >= 1
    assert m["camas_avisadas_antes"] <= m["camas_avisadas"] <= m["camas_infectadas"]
    assert m["camas_frenadas"] == m["camas_infectadas"] - m["camas_con_sintomas"]
    serie = metricas.serie_afectadas(sim)
    assert serie.shape == (30,) and serie.max() == pytest.approx(m["afectadas_pico"], abs=0.2)


def test_actual_avisa_despues_de_los_sintomas():
    cfg = cfg_chica(actual={"p_humano": 1.0, "dias_ronda": 1}, sim={"dias": 40})
    cfg["enfermedad"]["latencia_dias"] = [2, 2]
    m = metricas.extraer(correr(cfg, "actual"))
    assert m["anticipacion_dias"] <= 1 and m["alertas_alto"] == 0


def test_drones_avisan_antes_que_la_ronda_manual():
    cfg = cfg_chica(sim={"dias": 40}, actual={"p_humano": 0.35, "dias_ronda": 4})
    cfg["enfermedad"]["latencia_dias"] = [3, 3]
    drones, actual = (metricas.extraer(correr(cfg, e)) for e in ("drones", "actual"))
    assert drones["afectadas_final"] <= actual["afectadas_final"]


def test_ic_bootstrap_contiene_la_media():
    cfg = cargar_config()
    m, lo, hi = validar.ic_bootstrap([1, 2, 3, 4, 5, np.nan], cfg, np.random.default_rng(0))
    assert lo <= m <= hi and m == 3
    assert all(np.isnan(validar.ic_bootstrap([], cfg, np.random.default_rng(0))))


def test_graficas_1920x1080(tmp_path, monkeypatch):
    import matplotlib.image as mpimg
    rng = np.random.default_rng(0)
    esc = graficas.ESCENARIOS
    df = pd.DataFrame([{"escenario": e, "semilla": s, "anticipacion_dias": rng.normal(5, 3), "confirmaciones": 5.0,
                        "camas_avisadas_antes": 4, "camas_infectadas": 5, "retraso_deteccion_dias": 4.0, "afectadas_final": 0.01,
                        "confirmaciones_falsas": 0.0, "descartadas": 2.0, "alertas_alto_falsas": 30.0,
                        "focos_no_detectados": 1.0, "plantas_perdidas": 10.0} for e in esc for s in range(5)])
    series = pd.DataFrame([{"escenario": e, "semilla": s, "dia": d, "afectadas": rng.random() / 10}
                           for e in ("actual", "drones") for s in range(5) for d in range(1, 11)])
    riesgo = pd.DataFrame({"escenario": np.repeat(["drones", "sensor_central"], 200), "y": rng.integers(0, 2, 400),
                           "reglas": rng.random(400), "prob": rng.random(400)})
    pd.DataFrame({"variante": "completo", "variable": [f"v{i}" for i in range(12)], "importancia": rng.random(12),
                  "desvio": 0.01}).to_csv(tmp_path / "importancia.csv", index=False)
    monkeypatch.setattr(graficas, "RESULTADOS", tmp_path)
    graficas.g1_anticipacion(df); graficas.g2_afectadas(series); graficas.g3_curvas(riesgo)
    graficas.g4_importancia(); graficas.g5_errores(df); graficas.g6_red_vs_celular(df)
    pngs = sorted(tmp_path.glob("*.png"))
    assert len(pngs) == 6
    for p in pngs:
        assert mpimg.imread(p).shape[:2] == (1080, 1920)
