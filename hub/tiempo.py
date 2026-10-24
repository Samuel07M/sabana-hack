"""Hora simulada (horas desde el inicio) ↔ fecha y textos legibles en español."""
import math
from datetime import datetime, timedelta

from hub.config import cargar

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")
MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic")


def inicio(inicio_sim: str | None = None) -> datetime:
    """Fecha de la hora 0: la de la corrida, o sim.inicio del YAML."""
    return datetime.fromisoformat(inicio_sim or cargar()["sim"]["inicio"])


def fecha(hora: float, inicio_sim: str | None = None) -> datetime:
    """datetime de una hora simulada."""
    return inicio(inicio_sim) + timedelta(hours=float(hora))


def dia(hora: float) -> int:
    """Día simulado: hora // 24."""
    return int(math.floor(hora / 24))


def hhmm(hora: float) -> str:
    """'14:00' (o '14:36' si la hora tiene fracción)."""
    hh = int(math.floor(hora)) % 24
    mm = round((hora - math.floor(hora)) * 60)
    if mm == 60:
        hh, mm = (hh + 1) % 24, 0
    return f"{hh:02d}:{mm:02d}"


def corta(hora: float, inicio_sim: str | None = None) -> str:
    """'1 nov'."""
    f = fecha(hora, inicio_sim)
    return f"{f.day} {MESES_CORTOS[f.month - 1]}"


def etiqueta(hora: float | None, inicio_sim: str | None = None) -> str:
    """'1 nov · 14:00', o '—' si no hay hora."""
    if hora is None or (isinstance(hora, float) and math.isnan(hora)):
        return "—"
    return f"{corta(hora, inicio_sim)} · {hhmm(hora)}"


def fecha_larga(hora: float, inicio_sim: str | None = None) -> str:
    """'Domingo, 1 de noviembre de 2026'."""
    f = fecha(hora, inicio_sim)
    s = f"{DIAS[f.weekday()]}, {f.day} de {MESES[f.month - 1]} de {f.year}"
    return s[0].upper() + s[1:]


def hace(hora: float | None, ahora: float) -> str:
    """'hace 3 h', 'hace 2 días' o 'hace menos de 1 h'."""
    if hora is None or (isinstance(hora, float) and math.isnan(hora)):
        return "—"
    d = ahora - hora
    if d < 1:
        return "hace menos de 1 h"
    if d < 48:
        return f"hace {math.floor(d)} h"
    return f"hace {math.floor(d / 24)} días"
