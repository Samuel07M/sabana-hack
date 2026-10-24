"""CLI de temporada: simula y escribe data/finca.db (+ la verdad en data/verdad_<corrida>.parquet)."""
import argparse
import sqlite3
import time
from pathlib import Path

import pandas as pd

from sim import escritor, geometria
from sim.config import RAIZ, cargar_config
from sim.motor import Simulacion
from sim.valores import ESCENARIOS

DB_DEFAULT = RAIZ / "data" / "finca.db"


def parsear_args(argv=None) -> argparse.Namespace:
    """Argumentos de línea de comandos."""
    p = argparse.ArgumentParser(description="Corre una temporada simulada → finca.db")
    p.add_argument("--escenario", default="drones", choices=ESCENARIOS)
    p.add_argument("--semilla", type=int, default=None, help="por defecto la de config")
    p.add_argument("--dias", type=int, default=None, help="por defecto los de config")
    p.add_argument("--db", type=Path, default=DB_DEFAULT)
    p.add_argument("--config", type=Path, default=None, help="YAML que se aplica sobre default.yaml")
    return p.parse_args(argv)


def guardar_verdad(sim: Simulacion, ruta: Path) -> None:
    """Eventos de cambio de estado de las plantas (solo los usa analisis/)."""
    c = sim.cambios()
    df = pd.DataFrame({"hora": c[:, 0], "planta": c[:, 1], "estado_nuevo": c[:, 2]})
    df["cama_id"] = [sim.geo.camas[i]["cama_id"] for i in sim.geo.cama_de_planta[df["planta"].to_numpy()]]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(ruta, index=False)


def correr(cfg: dict, escenario: str, semilla: int, db: Path, corrida_id: str | None = None,
           modo: str = "temporada", verdad: Path | None = None, modelo="auto") -> Simulacion:
    """Simula una temporada completa y la escribe en `db`; devuelve la simulación."""
    corrida_id = corrida_id or f"temporada-{semilla}"
    con = escritor.crear_base(db, cfg)
    try:
        escritor.insertar_corrida(con, corrida_id, modo, escenario, semilla, cfg)
        escritor.insertar_camas(con, geometria.listar_camas(cfg))
        sim = Simulacion(cfg, escenario, semilla, corrida_id, modo=modo, modelo=modelo)
        for h in range(sim.n_horas):
            sim.paso(h)
            if h % 24 == 23:
                escritor.volcar(con, sim)
        sim.finalizar()
        escritor.volcar(con, sim)
    finally:
        con.close()
    if verdad is not None:
        guardar_verdad(sim, verdad)
    return sim


def main(argv=None) -> None:
    """Simula la temporada y resume las filas por tabla."""
    args = parsear_args(argv)
    cfg = cargar_config(args.config)
    semilla = cfg["semilla"] if args.semilla is None else args.semilla
    if args.dias is not None:
        cfg["sim"]["dias"] = args.dias
    cfg["semilla"] = semilla
    corrida_id = f"temporada-{semilla}"
    verdad = args.db.parent / f"verdad_{corrida_id}.parquet"
    t0 = time.time()
    correr(cfg, args.escenario, semilla, args.db, corrida_id, verdad=verdad)
    con = sqlite3.connect(args.db)
    filas = escritor.contar_filas(con)
    con.close()
    print(f"{args.db} · escenario={args.escenario} semilla={semilla} dias={cfg['sim']['dias']} · {time.time() - t0:.1f} s")
    for tabla, n in filas.items():
        print(f"  {tabla}: {n}")


if __name__ == "__main__":
    main()
