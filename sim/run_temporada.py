"""CLI de temporada: crea data/finca.db (Fase 1: corridas + camas)."""
import argparse
from pathlib import Path

from sim import escritor, geometria
from sim.config import RAIZ, cargar_config
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


def main(argv=None) -> None:
    """Crea la base, escribe `corridas` y `camas` e imprime filas por tabla."""
    args = parsear_args(argv)
    cfg = cargar_config(args.config)
    semilla = cfg["semilla"] if args.semilla is None else args.semilla
    if args.dias is not None:
        cfg["sim"]["dias"] = args.dias
    cfg["semilla"] = semilla
    con = escritor.crear_base(args.db, cfg)
    try:
        escritor.insertar_corrida(con, f"temporada-{semilla}", "temporada",
                                  args.escenario, semilla, cfg)
        escritor.insertar_camas(con, geometria.listar_camas(cfg))
        filas = escritor.contar_filas(con)
    finally:
        con.close()
    print(f"{args.db} · escenario={args.escenario} semilla={semilla} dias={cfg['sim']['dias']}")
    for tabla, n in filas.items():
        print(f"  {tabla}: {n}")


if __name__ == "__main__":
    main()
