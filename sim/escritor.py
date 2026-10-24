"""Crea la base SQLite desde contrato/schema.sql y escribe filas por lote."""
import json
import sqlite3
from pathlib import Path

from sim.config import RAIZ
from sim.valores import ESCENARIOS, MODOS

SCHEMA = RAIZ / "contrato" / "schema.sql"
COLUMNAS_CAMAS = ("cama_id", "bloque", "nave", "cama", "es_borde", "tiene_ventilacion")


TABLAS_POR_CORRIDA = ("lecturas", "riesgo", "incidencias", "seguimientos", "alertas", "drones", "ventilacion",
                      "cola_sync", "corridas")
IDS = {"inc": ("incidencias", "incidencia_id"), "alerta": ("alertas", "alerta_id"),
       "seg": ("seguimientos", "seguimiento_id"), "cola": ("cola_sync", "id")}


def crear_base(ruta: Path, cfg: dict, recrear: bool = False) -> sqlite3.Connection:
    """Abre la base en `ruta` (WAL, busy_timeout) conservando lo que tenga; la crea desde el contrato si no existe o si `recrear`."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not recrear and ruta.exists():
        con = sqlite3.connect(ruta)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute(f"PRAGMA busy_timeout={int(cfg['base_datos']['busy_timeout_ms'])}")
        if con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='corridas'").fetchone()[0]:
            return con
        con.close()
    if ruta.exists():
        print(f"aviso: {ruta} ya existía y se recrea desde contrato/schema.sql")
    try:
        for sufijo in ("", "-wal", "-shm"):
            Path(str(ruta) + sufijo).unlink(missing_ok=True)
    except PermissionError as e:
        raise PermissionError(f"no se puede recrear {ruta}: otro programa la tiene abierta (¿el dashboard?). "
                              "Ciérralo y vuelve a correr.") from e
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
    """Inserta la geometría en `camas` con executemany (las camas que ya existen se conservan)."""
    filas = [tuple(c[k] for k in COLUMNAS_CAMAS) for c in camas]
    with con:
        con.executemany("INSERT OR IGNORE INTO camas VALUES (?, ?, ?, ?, ?, ?)", filas)


def borrar_corrida(con: sqlite3.Connection, corrida_id: str) -> None:
    """Quita de todas las tablas las filas de una corrida (para reemplazarla sin tocar las demás)."""
    with con:
        for tabla in TABLAS_POR_CORRIDA:
            con.execute(f"DELETE FROM {tabla} WHERE corrida_id = ?", (corrida_id,))


def ids_iniciales(con: sqlite3.Connection) -> dict[str, int]:
    """Último id usado en cada tabla con id propio: las corridas anexadas siguen la numeración."""
    return {k: con.execute(f"SELECT COALESCE(MAX({col}), 0) FROM {tabla}").fetchone()[0] for k, (tabla, col) in IDS.items()}


SQL_INSERT = {  # tabla -> sentencia (las filas llegan en el orden de las columnas indicadas)
    "lecturas": "INSERT INTO lecturas (corrida_id, hora, cama_id, temp_c, hr, fuente) VALUES (?,?,?,?,?,?)",
    "riesgo": "INSERT INTO riesgo (corrida_id, dia, cama_id, enfermedad, riesgo_reglas, prob_ia_7d, nivel)"
              " VALUES (?,?,?,?,?,?,?)",
    "seguimientos": "INSERT INTO seguimientos (seguimiento_id, incidencia_id, corrida_id, hora, dron_id, resultado,"
                    " plantas_afectadas, nota) VALUES (?,?,?,?,?,?,?,?)",
    "alertas": "INSERT INTO alertas (alerta_id, corrida_id, hora, cama_id, incidencia_id, severidad, tipo, titulo,"
               " mensaje) VALUES (?,?,?,?,?,?,?,?,?)",
    "drones": "INSERT INTO drones (corrida_id, hora, dron_id, cama_id, estado, bateria) VALUES (?,?,?,?,?,?)",
    "ventilacion": "INSERT INTO ventilacion (corrida_id, hora, bloque, nave, estado, motivo) VALUES (?,?,?,?,?,?)",
    "cola_sync": "INSERT INTO cola_sync (id, corrida_id, origen, hora_generada, hora_recibida, tipo, payload)"
                 " VALUES (?,?,?,?,?,?,?)",
}
SQL_INCIDENCIAS = ("INSERT OR REPLACE INTO incidencias (incidencia_id, corrida_id, cama_id, posicion, origen, estado,"
                   " hora_creada, hora_confirmada, hora_cerrada, confianza, plantas_afectadas, verdad_infectada)"
                   " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")


def volcar(con: sqlite3.Connection, sim) -> None:
    """Escribe en una transacción las filas nuevas de la simulación y vacía sus buffers."""
    with con:
        for tabla, sql in SQL_INSERT.items():
            if sim.buf[tabla]:
                con.executemany(sql, sim.buf[tabla])
                sim.buf[tabla].clear()
        filas = sim.filas_incidencias()
        if filas:
            con.executemany(SQL_INCIDENCIAS, filas)


def contar_filas(con: sqlite3.Connection) -> dict[str, int]:
    """Filas por tabla del contrato."""
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tablas}
