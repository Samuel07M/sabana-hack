"""Deja data/finca.db lista para el tablero: una temporada con red local y otra sin red (la demo se agrega con run_vivo)."""
import argparse
import sqlite3
import time
from pathlib import Path

from sim import escritor
from sim.config import cargar_config
from sim.run_temporada import DB_DEFAULT, corrida_por_defecto, correr

CORRIDAS = (("robots", 9), ("robots_celular", 12))   # temporada-9 y celular-12, los mismos nombres que hub/mock.py


def main(argv=None) -> None:
    """Recrea la base con las dos temporadas y resume las filas por corrida."""
    p = argparse.ArgumentParser(description="Prepara data/finca.db para el tablero")
    p.add_argument("--db", type=Path, default=DB_DEFAULT)
    args = p.parse_args(argv)
    t0 = time.time()
    for i, (escenario, semilla) in enumerate(CORRIDAS):
        cfg = cargar_config()
        cfg["semilla"] = semilla
        corrida = corrida_por_defecto(escenario, semilla)
        correr(cfg, escenario, semilla, args.db, corrida, verdad=args.db.parent / f"verdad_{corrida}.parquet",
               recrear=i == 0)
        print(f"  {corrida:12s} escenario={escenario}")
    con = sqlite3.connect(args.db)
    print(f"{args.db} lista en {time.time() - t0:.0f} s · filas: {escritor.contar_filas(con)}")
    con.close()
    print("Tablero: streamlit run dashboard/app.py  (?corrida=temporada-9 | celular-12)\n"
          "Demo en vivo: python -m sim.run_vivo --velocidad 1  (?corrida=demo)")


if __name__ == "__main__":
    main()
