"""Entrena la IA con temporadas simuladas (semillas de entrenamiento) y la compara con las reglas en las de prueba."""
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score

from prediccion import etiquetas, ia
from prediccion.variables import VARIABLES
from sim.config import RAIZ, cargar_config
from sim.motor import Simulacion

RESULTADOS = RAIZ / "data" / "resultados"


def dataset_de_corrida(sim: Simulacion) -> pd.DataFrame:
    """Filas (cama, día) de una corrida ya simulada con `recolectar=True`: variables, reglas y etiqueta."""
    cfg, g = sim.cfg, sim.geo
    cambios, horizonte = sim.cambios(), cfg["riesgo"]["horizonte_h"]
    partes = []
    for h, df, reg, prob in sim.dataset:
        if h + horizonte >= sim.n_horas:      # sin 7 días completos por delante la etiqueta es incierta
            continue
        d = df.copy()
        d["reglas"] = reg
        d["prob"] = np.nan if prob is None else prob
        d["y"] = etiquetas.etiquetas(cambios, g.cama_de_planta, g.n_camas, sim.n_horas, h, horizonte)
        d["dia"], d["cama"], d["semilla"] = h // 24, np.arange(g.n_camas), sim.semilla
        partes.append(d)
    return pd.concat(partes, ignore_index=True)


def generar(cfg: dict, escenario: str, semillas) -> pd.DataFrame:
    """Simula cada semilla (sin modelo: el nivel sale de las reglas) y junta sus filas."""
    partes = []
    for s in semillas:
        sim = Simulacion(cfg, escenario, s, f"ent-{escenario}-{s}", modo="experimento", modelo=None, recolectar=True)
        for h in range(sim.n_horas):
            sim.paso(h)
        partes.append(dataset_de_corrida(sim))
    return pd.concat(partes, ignore_index=True)


def entrenar_modelo(cfg: dict, datos: pd.DataFrame) -> HistGradientBoostingClassifier:
    """HistGradientBoosting con clases balanceadas."""
    t = cfg["entrenamiento"]
    clf = HistGradientBoostingClassifier(
        class_weight="balanced", max_iter=t["max_iter"], learning_rate=t["learning_rate"],
        max_depth=t["max_depth"], min_samples_leaf=t["min_samples_leaf"],
        l2_regularization=t["l2_regularization"], random_state=0)
    return clf.fit(datos[list(VARIABLES)], datos["y"])


def aciertos_top_k(datos: pd.DataFrame, puntaje: np.ndarray, k: int) -> float:
    """Fracción de camas con infección entre las k de mayor puntaje de cada día (por temporada)."""
    d = datos[["semilla", "dia", "y"]].assign(p=puntaje)
    top = d.sort_values("p", ascending=False).groupby(["semilla", "dia"]).head(k)
    return float(top["y"].mean())


def metricas(datos: pd.DataFrame, puntaje: np.ndarray, k: int) -> dict:
    """AUC, PR-AUC y aciertos en el top-k diario."""
    return {"auc": roc_auc_score(datos["y"], puntaje), "pr_auc": average_precision_score(datos["y"], puntaje),
            "top_k": aciertos_top_k(datos, puntaje, k)}


def rango(par) -> range:
    """[a, b] inclusivo → range."""
    return range(par[0], par[1] + 1)


def main() -> None:
    """Entrena los dos modelos (completo y solo sensor central) y compara con las reglas en las semillas de prueba."""
    cfg = cargar_config()
    t0 = time.time()
    k = cfg["analisis"]["top_k_camas"]
    train, test = rango(cfg["entrenamiento"]["semillas_train"]), rango(cfg["entrenamiento"]["semillas_test"])
    assert not set(train) & set(test), "las semillas de entrenamiento y prueba no pueden cruzarse"
    filas, importancia = [], []
    for variante, escenario in (("completo", "drones"), ("central", "sensor_central")):
        d_train, d_test = generar(cfg, escenario, train), generar(cfg, escenario, test)
        modelo = entrenar_modelo(cfg, d_train)
        ia.guardar(modelo, variante, {"escenario_entrenamiento": escenario, "semillas_train": list(train)})
        prob = modelo.predict_proba(d_test[list(VARIABLES)])[:, 1]
        filas.append({"variante": variante, "modelo": "reglas", **metricas(d_test, d_test["reglas"].to_numpy(), k)})
        filas.append({"variante": variante, "modelo": "IA", **metricas(d_test, prob, k)})
        muestra = d_test.sample(min(len(d_test), cfg["entrenamiento"]["muestra_permutacion"]), random_state=cfg["semilla"])
        imp = permutation_importance(modelo, muestra[list(VARIABLES)], muestra["y"], scoring="roc_auc",
                                     n_repeats=cfg["entrenamiento"]["repeticiones_permutacion"], random_state=0)
        importancia.append(pd.DataFrame({"variante": variante, "variable": VARIABLES, "importancia": imp.importances_mean,
                                         "desvio": imp.importances_std}))
        print(f"[{variante}] entrenado con {len(d_train)} filas ({escenario}), probado con {len(d_test)}")
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    pd.concat(importancia).to_csv(RESULTADOS / "importancia.csv", index=False, encoding="utf-8")
    res = pd.DataFrame(filas)
    res.to_csv(RESULTADOS / "modelo_test.csv", index=False, encoding="utf-8")
    print(res.round(3).to_string(index=False))
    print(f"({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
