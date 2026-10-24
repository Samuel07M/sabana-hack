"""Corre los 5 escenarios con las mismas semillas y resume métricas con IC 95 % (bootstrap) y diferencias pareadas."""
import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from analisis import metricas
from prediccion import entrenar
from sim import escritor, geometria
from sim.config import RAIZ, cargar_config
from sim.motor import FLAGS, Simulacion

RESULTADOS = RAIZ / "data" / "resultados"
EXPERIMENTOS = RAIZ / "data" / "experimentos"
ESCENARIOS = ("actual", "sensor_central", "drones", "drones_celular", "drones_sin_vent")
CLAVES = ("anticipacion_dias", "retraso_deteccion_dias", "afectadas_final", "afectadas_pico", "plantas_perdidas",
          "alertas_alto_falsas", "descartadas", "confirmaciones_falsas", "focos_no_detectados")
COMPARACIONES = (("drones", "actual"), ("drones", "sensor_central"), ("drones_celular", "drones"),
                 ("drones_sin_vent", "drones"))


def correr_una(args: tuple):
    """Una corrida (escenario, semilla): métricas, serie de afectadas y filas de riesgo para evaluar el modelo."""
    escenario, semilla, dias, guardar_db = args
    cfg = cargar_config()
    if dias:
        cfg["sim"]["dias"] = dias
    corrida_id = f"exp-{escenario}-{semilla}"
    sim = Simulacion(cfg, escenario, semilla, corrida_id, modo="experimento", recolectar=FLAGS[escenario]["modelo"])
    for h in range(sim.n_horas):
        sim.paso(h)
    sim.finalizar()
    m, serie = metricas.extraer(sim), metricas.serie_afectadas(sim)
    riesgo = None
    if sim.dataset:
        riesgo = entrenar.dataset_de_corrida(sim)[["semilla", "dia", "cama", "y", "reglas", "prob"]].assign(escenario=escenario)
    if guardar_db:
        con = escritor.crear_base(EXPERIMENTOS / f"{corrida_id}.db", cfg, recrear=True)
        escritor.insertar_corrida(con, corrida_id, "experimento", escenario, semilla, cfg)
        escritor.insertar_camas(con, geometria.listar_camas(cfg))
        escritor.volcar(con, sim)
        con.close()
    return m, serie, riesgo


def ic_bootstrap(valores, cfg: dict, rng: np.random.Generator) -> tuple[float, float, float]:
    """(media, límite inferior, límite superior) del IC por bootstrap sobre las semillas."""
    v = np.asarray(valores, dtype=float)
    v = v[~np.isnan(v)]
    if v.size == 0:
        return np.nan, np.nan, np.nan
    medias = rng.choice(v, size=(cfg["analisis"]["bootstrap_n"], v.size)).mean(axis=1)
    a = (1 - cfg["analisis"]["ic_nivel"]) / 2
    return float(v.mean()), float(np.quantile(medias, a)), float(np.quantile(medias, 1 - a))


def resumir(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Media e IC95 por escenario y métrica, más diferencias pareadas por semilla."""
    rng = np.random.default_rng(cfg["semilla"])
    filas = []
    for esc in ESCENARIOS:
        for k in CLAVES:
            m, lo, hi = ic_bootstrap(df.loc[df.escenario == esc, k], cfg, rng)
            filas.append({"tipo": "media", "escenario": esc, "comparado_con": "", "metrica": k, "media": m, "ic_lo": lo, "ic_hi": hi})
    ancho = df.pivot(index="semilla", columns="escenario")
    for a, b in COMPARACIONES:
        for k in CLAVES:
            m, lo, hi = ic_bootstrap(ancho[k][a] - ancho[k][b], cfg, rng)
            filas.append({"tipo": "diferencia_pareada", "escenario": a, "comparado_con": b, "metrica": k,
                          "media": m, "ic_lo": lo, "ic_hi": hi})
    return pd.DataFrame(filas)


def metricas_modelo(riesgo: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """AUC, PR-AUC y aciertos en el top-k diario: reglas vs IA (todos los datos) vs IA solo sensor central."""
    filas = []
    k = cfg["analisis"]["top_k_camas"]
    casos = (("reglas", "drones", "reglas"), ("IA", "drones", "prob"),
             ("reglas (solo sensor central)", "sensor_central", "reglas"), ("IA solo sensor central", "sensor_central", "prob"))
    for nombre, esc, col in casos:
        d = riesgo[riesgo.escenario == esc]
        filas.append({"modelo": nombre, "escenario": esc, **entrenar.metricas(d, d[col].to_numpy(), k)})
    return pd.DataFrame(filas)


def main(argv=None) -> None:
    """Corre escenarios × semillas y guarda metricas.parquet, series, riesgo y el resumen."""
    p = argparse.ArgumentParser(description="Escenarios × semillas → data/resultados/")
    p.add_argument("--semillas", type=int, default=30)
    p.add_argument("--dias", type=int, default=None, help="por defecto los de config")
    p.add_argument("--procesos", type=int, default=max(1, min(6, (os.cpu_count() or 2) - 1)))
    p.add_argument("--guardar-db", action="store_true", help="guarda cada corrida en data/experimentos/<corrida>.db")
    args = p.parse_args(argv)
    cfg = cargar_config()
    inicio = cfg["analisis"]["semilla_inicial_validacion"]
    semillas = range(inicio, inicio + args.semillas)
    trabajos = [(e, s, args.dias, args.guardar_db) for s in semillas for e in ESCENARIOS]
    if args.guardar_db:
        EXPERIMENTOS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with ProcessPoolExecutor(args.procesos) as pool:
        resultados = list(pool.map(correr_una, trabajos, chunksize=1))
    print(f"{len(trabajos)} corridas en {time.time() - t0:.0f} s ({args.procesos} procesos)")
    df = pd.DataFrame([r[0] for r in resultados])
    series = pd.DataFrame([{"escenario": r[0]["escenario"], "semilla": r[0]["semilla"], "dia": d + 1, "afectadas": v}
                           for r in resultados for d, v in enumerate(r[1])])
    riesgo = pd.concat([r[2] for r in resultados if r[2] is not None], ignore_index=True)
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RESULTADOS / "metricas.parquet", index=False)
    series.to_parquet(RESULTADOS / "series_afectadas.parquet", index=False)
    riesgo.to_parquet(RESULTADOS / "riesgo_validacion.parquet", index=False)
    resumen, modelo = resumir(df, cfg), metricas_modelo(riesgo, cfg)
    resumen.to_csv(RESULTADOS / "resumen.csv", index=False, encoding="utf-8")
    modelo.to_csv(RESULTADOS / "modelo_validacion.csv", index=False, encoding="utf-8")
    pd.set_option("display.width", 200)
    print(resumen[resumen.tipo == "media"].pivot(index="metrica", columns="escenario", values="media")[list(ESCENARIOS)].round(3))
    print("\nDiferencias pareadas (media [IC95]):")
    for _, f in resumen[resumen.tipo == "diferencia_pareada"].iterrows():
        print(f"  {f.escenario} − {f.comparado_con:<14} {f.metrica:<24} {f.media:8.3f} [{f.ic_lo:.3f}, {f.ic_hi:.3f}]")
    print("\nModelo (semillas de validación):")
    print(modelo.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
