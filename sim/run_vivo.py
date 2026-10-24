"""CLI de demo en vivo: escribe hora a hora en data/finca.db (la base queda en WAL, el dashboard lee mientras tanto)."""
import argparse
import time
from pathlib import Path

from sim import escritor, geometria
from sim.config import RAIZ, cargar_config
from sim.motor import Simulacion

DB_DEFAULT = RAIZ / "data" / "finca.db"
CORRIDA_DEMO = "demo"


def parsear_args(argv=None) -> argparse.Namespace:
    """Argumentos de línea de comandos."""
    p = argparse.ArgumentParser(description="Demo en vivo: 1 hora simulada cada 1/velocidad segundos")
    p.add_argument("--config", type=Path, default=RAIZ / "config" / "demo.yaml")
    p.add_argument("--velocidad", type=float, default=1.0, help="horas simuladas por segundo (0 = sin esperar)")
    p.add_argument("--db", type=Path, default=DB_DEFAULT)
    p.add_argument("--semilla", type=int, default=None, help="por defecto la de la config")
    p.add_argument("--horas", type=int, default=None, help="por defecto los días de la config × 24")
    p.add_argument("--recrear", action="store_true", help="borra la base y la crea de nuevo (por defecto se conserva "
                                                          "y solo se reemplaza la corrida `demo`)")
    p.add_argument("--anexar", action="store_true", help=argparse.SUPPRESS)   # compatibilidad: ya es el comportamiento por defecto
    return p.parse_args(argv)


def main(argv=None) -> None:
    """Simula la demo escribiendo cada hora sin leer nada de la base (las acciones del dashboard no vuelven)."""
    args = parsear_args(argv)
    cfg = cargar_config(args.config)
    semilla = cfg["semilla"] if args.semilla is None else args.semilla
    cfg["semilla"] = semilla
    con = escritor.crear_base(args.db, cfg, recrear=args.recrear)
    try:
        escritor.borrar_corrida(con, CORRIDA_DEMO)
        escritor.insertar_corrida(con, CORRIDA_DEMO, "vivo", "demo", semilla, cfg)
        escritor.insertar_camas(con, geometria.listar_camas(cfg))
        sim = Simulacion(cfg, "demo", semilla, CORRIDA_DEMO, modo="vivo", ids_iniciales=escritor.ids_iniciales(con))
        horas = args.horas or sim.n_horas
        espera = 1.0 / args.velocidad if args.velocidad > 0 else 0.0
        print(f"demo en vivo → {args.db} · {horas} h simuladas · {args.velocidad} h/s")
        for h in range(horas):
            t0 = time.time()
            sim.paso(h)
            nuevas = {t: len(sim.buf[t]) for t in ("alertas", "ventilacion", "seguimientos") if sim.buf[t]}
            escritor.volcar(con, sim)
            if nuevas:
                print(f"h{h:04d} (día {h // 24}, {h % 24:02d}:00) " + " ".join(f"{t}+{n}" for t, n in nuevas.items()))
            time.sleep(max(0.0, espera - (time.time() - t0)))
        sim.finalizar()
        escritor.volcar(con, sim)
    finally:
        con.close()


if __name__ == "__main__":
    main()
