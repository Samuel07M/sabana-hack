"""Crea la base SQLite desde contrato/schema.sql y escribe filas por lote."""
import json
import sqlite3
from pathlib import Path

from sim.config import RAIZ
from sim.valores import ESCENARIOS, MODOS

SCHEMA = RAIZ / "contrato" / "schema.sql"
COLUMNAS_CAMAS = ("cama_id", "bloque", "nave", "cama", "es_borde", "tiene_ventilacion")


def crear_base(ruta: Path, cfg: dict) -> sqlite3.Connection:
    """Recrea la base en `ruta` con el esquema del contrato, WAL y busy_timeout."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    for sufijo in ("", "-wal", "-shm"):
        Path(str(ruta) + sufijo).unlink(missing_ok=True)
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(f"PRAGMA busy_timeout={int(cfg['base_datos']['busy_timeout_ms'])}")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    return con


def insertar_corrida(con: sqlite3.Connection, corrida_id: str, modo: str,
                     escenario: str, semilla: int, cfg: dict) -> None:
    """Inserta la fila de `corridas` con la config completa usada."""
    if modo not in MODOS:
        raise ValueError(f"modo '{modo}' fuera del contrato: {MODOS}")
    if escenario not in ESCENARIOS:
        raise ValueError(f"escenario '{escenario}' fuera del contrato: {ESCENARIOS}")
    with con:
        con.execute(
            "INSERT INTO corridas (corrida_id, modo, escenario, semilla, config_json, inicio_sim)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (corrida_id, modo, escenario, semilla,
             json.dumps(cfg, ensure_ascii=False), cfg["sim"]["inicio"]),
        )


def insertar_camas(con: sqlite3.Connection, camas: list[dict]) -> None:
    """Inserta la geometría en `camas` con executemany."""
    filas = [tuple(c[k] for k in COLUMNAS_CAMAS) for c in camas]
    with con:
        con.executemany("INSERT INTO camas VALUES (?, ?, ?, ?, ?, ?)", filas)


def contar_filas(con: sqlite3.Connection) -> dict[str, int]:
    """Filas por tabla del contrato."""
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tablas}
