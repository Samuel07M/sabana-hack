"""Hitos del tour: cada uno devuelve una función (corrida, desde) → primera hora ≥ desde en que ocurre, o None.

Leen la base completa (sin tope de reproducción): el tour avanza el tope hasta la hora que devuelven.
"""
from collections.abc import Callable
from contextlib import closing

from hub import db
from hub.config import cargar

Hito = Callable[[str, float], float | None]


def _primera(sql: str, params: tuple) -> float | None:
    """MIN(...) de una consulta de una columna; None si no hay filas."""
    with closing(db.conectar_lectura()) as con:
        v = con.execute(sql, params).fetchone()[0]
    return None if v is None else float(v)


def lectura(fuente: str = "robot:%", cama: str = "%", hr_min: float | None = None) -> Hito:
    """Primera lectura de la fuente (LIKE) en las camas (LIKE), con humedad ≥ hr_min si se da."""
    hr = -1.0 if hr_min is None else float(hr_min)
    return lambda c, d: _primera("SELECT MIN(hora) FROM lecturas WHERE corrida_id=? AND fuente LIKE ? AND cama_id LIKE ? "
                                 "AND hr >= ? AND hora >= ?", (c, fuente, cama, hr, d))


def riesgo(cama: str = "%", nivel: str = "alto") -> Hito:
    """Primer cálculo de riesgo (a las hora_calculo) con ese nivel en la cama."""
    hc = cargar()["riesgo"]["hora_calculo"]
    return lambda c, d: _primera("SELECT MIN(dia*24 + ?) FROM riesgo WHERE corrida_id=? AND cama_id LIKE ? AND nivel LIKE ? "
                                 "AND dia*24 + ? >= ?", (hc, c, cama, nivel, hc, d))


def alerta(tipo: str, cama: str = "%") -> Hito:
    """Primera alerta del tipo en la cama."""
    return lambda c, d: _primera("SELECT MIN(hora) FROM alertas WHERE corrida_id=? AND tipo=? AND cama_id LIKE ? AND hora >= ?",
                                 (c, tipo, cama, d))


def robot(estado: str, cama: str = "%") -> Hito:
    """Primera vez que un robot está en ese estado en la cama."""
    return lambda c, d: _primera("SELECT MIN(hora) FROM robots WHERE corrida_id=? AND estado=? AND cama_id LIKE ? AND hora >= ?",
                                 (c, estado, cama, d))


def incidencia(estado: str = "confirmada", cama: str = "%") -> Hito:
    """Primera incidencia creada (sospecha) o confirmada en la cama."""
    col = "hora_creada" if estado == "sospecha" else "hora_confirmada"
    return lambda c, d: _primera(f"SELECT MIN({col}) FROM incidencias WHERE corrida_id=? AND cama_id LIKE ? AND {col} >= ?",
                                 (c, cama, d))


def ventilacion(estado: str = "apagada", bloque: int | None = None, nave: int | None = None) -> Hito:
    """Primer cambio de ventilación a ese estado (en la nave, si se da)."""
    b, n = (-1, -1) if bloque is None else (int(bloque), int(nave))
    return lambda c, d: _primera("SELECT MIN(hora) FROM ventilacion WHERE corrida_id=? AND estado=? AND hora >= ? "
                                 "AND (? < 0 OR (bloque=? AND nave=?))", (c, estado, d, b, b, n))


def seguimiento() -> Hito:
    """Primera revisita registrada por el robot."""
    return lambda c, d: _primera("SELECT MIN(hora) FROM seguimientos WHERE corrida_id=? AND hora >= ?", (c, d))


def cola_sync() -> Hito:
    """Primer dato guardado en los robots esperando sincronizar (nivel 2)."""
    return lambda c, d: _primera("SELECT MIN(hora_generada) FROM cola_sync WHERE corrida_id=? AND hora_generada >= ?", (c, d))
