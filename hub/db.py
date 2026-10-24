"""Única puerta a la base: consultas de solo lectura (una por método del Hub del prototipo).

Todas reciben `corrida_id` y devuelven DataFrames. Nunca devuelven incidencias.verdad_infectada.
En modo sin red (escenario robots_celular) se oculta lo posterior a la última sincronización
(NOTAS.md, decisión 7); el sensor fijo del bloque sigue visible, como en el prototipo.
"""
import json
import math
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from hub import tiempo
from hub import ubicacion as U
from hub.config import RAIZ, cargar
from hub.variables import ESTADOS_CONFIRMADOS, SIN_CONFIRMADA, calcular

RUTA_DEFECTO = Path("data") / "finca.db"
COLS_INC = ("incidencia_id", "corrida_id", "cama_id", "posicion", "origen", "estado", "hora_creada",
            "hora_confirmada", "hora_cerrada", "confianza", "plantas_afectadas")
COLS_ALERTA = ("alerta_id", "corrida_id", "hora", "cama_id", "incidencia_id", "severidad", "tipo", "titulo",
               "mensaje", "estado", "accion")
TIPOS_ALERTA = ("riesgo_7d", "confirmacion", "seguimiento", "ventilacion", "descartada")
SEV_RANK = {"critica": 0, "advertencia": 1, "info": 2}
CERRADAS = ("cerrada", "descartada")
SIN_CORTE = math.inf


# ── conexión ─────────────────────────────────────────────────────────────────
def ruta_base() -> Path:
    """Ruta de la base: variable de entorno FINCA_DB o data/finca.db."""
    p = Path(os.environ.get("FINCA_DB") or RUTA_DEFECTO)
    if not p.is_absolute() and not p.exists():
        p = RAIZ / p
    return p.resolve()


def conectar_lectura() -> sqlite3.Connection:
    """Conexión de solo lectura (mode=ro, URI desde Path.as_uri())."""
    return sqlite3.connect(ruta_base().as_uri() + "?mode=ro", uri=True, check_same_thread=False)


def conectar_escritura() -> sqlite3.Connection:
    """Conexión de escritura con busy_timeout (convive con el simulador en WAL)."""
    con = sqlite3.connect(ruta_base(), check_same_thread=False)
    con.execute(f"PRAGMA busy_timeout={int(cargar()['base_datos']['busy_timeout_ms'])}")
    return con


def _q(sql: str, params=()) -> pd.DataFrame:
    """Ejecuta una consulta de lectura y devuelve un DataFrame."""
    with closing(conectar_lectura()) as con:
        return pd.read_sql_query(sql, con, params=list(params))


def _uno(sql: str, params=()):
    """Primer valor de una consulta de lectura (o None)."""
    with closing(conectar_lectura()) as con:
        fila = con.execute(sql, list(params)).fetchone()
    return fila[0] if fila else None


def existe() -> bool:
    """True si la base existe y tiene el contrato."""
    try:
        return bool(_uno("SELECT COUNT(*) FROM sqlite_master WHERE name='corridas'"))
    except sqlite3.Error:
        return False


# ── corrida, hora y red ──────────────────────────────────────────────────────
def corridas() -> pd.DataFrame:
    """Corridas guardadas en la base."""
    return _q("SELECT corrida_id, modo, escenario, semilla, inicio_sim FROM corridas ORDER BY corrida_id")


def corrida(corrida_id: str) -> pd.DataFrame:
    """Fila de una corrida (sin config_json)."""
    return _q("SELECT corrida_id, modo, escenario, semilla, inicio_sim FROM corridas WHERE corrida_id=?",
              (corrida_id,))


def camas(bloque: int | None = None) -> pd.DataFrame:
    """Geometría de la finca, en orden de bloque, nave y cama."""
    if bloque is None:
        return _q("SELECT * FROM camas ORDER BY bloque, nave, cama")
    return _q("SELECT * FROM camas WHERE bloque=? ORDER BY nave, cama", (bloque,))


def inicio_sim(corrida_id: str) -> str | None:
    """inicio_sim de la corrida (ISO 8601)."""
    return _uno("SELECT inicio_sim FROM corridas WHERE corrida_id=?", (corrida_id,))


def red(corrida_id: str) -> str:
    """'sin_red' si la corrida es robots_celular; si no, 'local'."""
    esc = _uno("SELECT escenario FROM corridas WHERE corrida_id=?", (corrida_id,))
    return "sin_red" if esc == "robots_celular" else "local"


def ahora(corrida_id: str) -> float:
    """Hora simulada actual: la mayor hora escrita en lecturas o robots."""
    v = _uno("SELECT MAX(h) FROM (SELECT MAX(hora) h FROM lecturas WHERE corrida_id=? "
             "UNION ALL SELECT MAX(hora) FROM robots WHERE corrida_id=?)", (corrida_id, corrida_id))
    return float(v) if v is not None else 0.0


def corte(corrida_id: str) -> float:
    """Primera hora oculta: sin red, la hora siguiente a la última sincronización; con red, infinito."""
    if red(corrida_id) != "sin_red":
        return SIN_CORTE
    v = _uno("SELECT MAX(hora_recibida) FROM cola_sync WHERE corrida_id=?", (corrida_id,))
    return float(v) + 1 if v is not None else -math.inf


def _lim(c: float) -> float:
    """Corte apto para un parámetro SQL (SQLite no acepta inf)."""
    return 1e18 if c == math.inf else (-1e18 if c == -math.inf else c)


def _bloque_like(bloque: int) -> str:
    """Patrón LIKE de las camas de un bloque."""
    return f"B{int(bloque)}-%"


# ── riesgo ───────────────────────────────────────────────────────────────────
def _filtro_riesgo(c: float) -> tuple[str, list]:
    """Condición de visibilidad del riesgo (calculado a las hora_calculo de cada día)."""
    return " AND dia*24 + ? < ?", [cargar()["riesgo"]["hora_calculo"], _lim(c)]


def _con_puntaje(df: pd.DataFrame) -> pd.DataFrame:
    """Sin modelo de IA entrenado el simulador deja prob_ia_7d NULL y decide el nivel con riesgo_reglas: se muestra ese."""
    if len(df):
        df["prob_ia_7d"] = df["prob_ia_7d"].fillna(df["riesgo_reglas"])
    return df


def riesgo_ultimo(corrida_id: str) -> pd.DataFrame:
    """Riesgo del último día calculado (hasta hoy), una fila por cama."""
    c = corte(corrida_id)
    hoy = tiempo.dia(ahora(corrida_id))
    f, p = _filtro_riesgo(c)
    dia = _uno(f"SELECT MAX(dia) FROM riesgo WHERE corrida_id=? AND dia<=?{f}", [corrida_id, hoy, *p])
    if dia is None:
        return _q("SELECT * FROM riesgo WHERE 0")
    return riesgo_dia(corrida_id, int(dia))


def riesgo_dia(corrida_id: str, dia: int) -> pd.DataFrame:
    """Riesgo de todas las camas en un día."""
    f, p = _filtro_riesgo(corte(corrida_id))
    return _con_puntaje(_q(f"SELECT * FROM riesgo WHERE corrida_id=? AND dia=?{f} ORDER BY cama_id", [corrida_id, dia, *p]))


def riesgo_cama(corrida_id: str, cama_id: str) -> pd.DataFrame:
    """Serie diaria de riesgo de una cama."""
    f, p = _filtro_riesgo(corte(corrida_id))
    return _con_puntaje(_q(f"SELECT * FROM riesgo WHERE corrida_id=? AND cama_id=?{f} ORDER BY dia",
                           [corrida_id, cama_id, *p]))


def serie_riesgo(corrida_id: str) -> pd.DataFrame:
    """Camas en riesgo alto, medio y bajo por día."""
    f, p = _filtro_riesgo(corte(corrida_id))
    return _q("SELECT dia, SUM(nivel='alto') alto, SUM(nivel='medio') medio, SUM(nivel='bajo') bajo "
              f"FROM riesgo WHERE corrida_id=?{f} GROUP BY dia ORDER BY dia", [corrida_id, *p])


# ── lecturas y clima ─────────────────────────────────────────────────────────
def _sensor_cama(corrida_id: str, bloque: int) -> str | None:
    """Cama donde está el sensor fijo del bloque."""
    return _uno("SELECT cama_id FROM lecturas WHERE corrida_id=? AND fuente='sensor_fijo' AND cama_id LIKE ? "
                "LIMIT 1", (corrida_id, _bloque_like(bloque)))


def lecturas_cama(corrida_id: str, cama_id: str, desde: float, hasta: float) -> pd.DataFrame:
    """Lecturas del robot en la cama y del sensor del bloque entre dos horas; columna `serie` = cama | sensor."""
    c = corte(corrida_id)
    cama = _q("SELECT hora, cama_id, temp_c, hr, fuente FROM lecturas WHERE corrida_id=? AND cama_id=? "
              "AND fuente!='sensor_fijo' AND hora BETWEEN ? AND ? AND hora < ? ORDER BY hora",
              (corrida_id, cama_id, desde, hasta, _lim(c)))
    cama["serie"] = "cama"
    sid = _sensor_cama(corrida_id, U.partes(cama_id)[0])
    sens = _q("SELECT hora, cama_id, temp_c, hr, fuente FROM lecturas WHERE corrida_id=? AND cama_id=? "
              "AND fuente='sensor_fijo' AND hora BETWEEN ? AND ? ORDER BY hora",
              (corrida_id, sid, max(0, desde), hasta))
    sens["serie"] = "sensor"
    return pd.concat([cama, sens], ignore_index=True) if len(sens) else cama


def _clima_de(fila_robot, sensor: pd.DataFrame, h: float):
    """Regla del prototipo: lectura del robot de las últimas 24 h, o el sensor del bloque de las últimas 6 h."""
    if fila_robot is not None and h - fila_robot["hora"] <= 24:
        return fila_robot
    s = sensor[(sensor["hora"] <= h) & (sensor["hora"] >= max(0, h - 6))]
    return s.iloc[-1] if len(s) else None


def clima_bloque(corrida_id: str, bloque: int) -> pd.DataFrame:
    """Clima actual (temp_c, hr, fuente, hora) de cada cama del bloque."""
    h, c = ahora(corrida_id), corte(corrida_id)
    ult = _q("SELECT l.cama_id, l.hora, l.temp_c, l.hr, l.fuente FROM lecturas l JOIN ("
             " SELECT cama_id, MAX(rowid) r FROM lecturas WHERE corrida_id=? AND cama_id LIKE ? "
             " AND fuente!='sensor_fijo' AND hora < ? GROUP BY cama_id) m ON l.rowid=m.r",
             (corrida_id, _bloque_like(bloque), _lim(c)))
    sid = _sensor_cama(corrida_id, bloque)
    sens = _q("SELECT hora, cama_id, temp_c, hr, fuente FROM lecturas WHERE corrida_id=? AND cama_id=? "
              "AND fuente='sensor_fijo' AND hora >= ? ORDER BY hora", (corrida_id, sid, h - 6))
    por_cama = {r["cama_id"]: r for _, r in ult.iterrows()}
    filas = []
    for cid in camas(bloque)["cama_id"]:
        r = _clima_de(por_cama.get(cid), sens, h)
        if r is not None:
            filas.append({"cama_id": cid, "hora": float(r["hora"]), "temp_c": float(r["temp_c"]),
                          "hr": float(r["hr"]), "fuente": r["fuente"]})
    return pd.DataFrame(filas, columns=["cama_id", "hora", "temp_c", "hr", "fuente"])


def clima_actual(corrida_id: str, cama_id: str) -> pd.DataFrame:
    """Clima actual de una cama (0 o 1 fila)."""
    df = clima_bloque(corrida_id, U.partes(cama_id)[0])
    return df[df["cama_id"] == cama_id].reset_index(drop=True)


# ── variables de "Qué explica este riesgo" ───────────────────────────────────
def variables_bloque(corrida_id: str, bloque: int) -> pd.DataFrame:
    """variables() del prototipo para todas las camas del bloque, leyendo de la base."""
    cfg = cargar()
    mp, Mo = cfg["dashboard"]["mock"]["modelo_prueba"], cfg["dashboard"]["mock"]["robots"]
    h, c = ahora(corrida_id), corte(corrida_id)
    fin = int(math.floor(h)) + 1
    desde = fin - mp["ventana_h"] - Mo["horas_validez_lectura"]
    lect = _q("SELECT hora, cama_id, temp_c, hr, fuente FROM lecturas WHERE corrida_id=? AND cama_id LIKE ? "
              "AND fuente!='sensor_fijo' AND hora < ? AND hora >= ? ORDER BY hora, rowid",
              (corrida_id, _bloque_like(bloque), _lim(c), desde))
    ult = _q("SELECT cama_id, MAX(hora) hora, fuente FROM lecturas WHERE corrida_id=? AND cama_id LIKE ? "
             "AND fuente!='sensor_fijo' AND hora < ? GROUP BY cama_id", (corrida_id, _bloque_like(bloque), _lim(c)))
    sid = _sensor_cama(corrida_id, bloque)
    sens = _q("SELECT hora, temp_c, hr FROM lecturas WHERE corrida_id=? AND cama_id=? AND fuente='sensor_fijo' "
              "AND hora >= ?", (corrida_id, sid, desde))
    sensor = {int(r.hora): (r.temp_c, r.hr) for r in sens.itertuples()}
    inc = incidencias(corrida_id, bloque=bloque)
    conf = inc[inc["estado"].isin(ESTADOS_CONFIRMADOS)]
    conf_nave: dict[int, list] = {}
    for cid in conf["cama_id"]:
        _, n, cc = U.partes(cid)
        conf_nave.setdefault(n, []).append(cc)
    por_cama: dict[str, list] = {}
    for r in lect.itertuples():
        por_cama.setdefault(r.cama_id, []).append((r.hora, r.temp_c, r.hr, r.fuente))
    ult_d = {r.cama_id: (r.hora, r.fuente) for r in ult.itertuples()}
    filas = []
    for cam in camas(bloque).itertuples():
        dist = min((abs(x - cam.cama) for x in conf_nave.get(cam.nave, [])), default=SIN_CONFIRMADA)
        v = calcular(por_cama.get(cam.cama_id, []), sensor, fin, ventana_h=mp["ventana_h"],
                     validez_h=Mo["horas_validez_lectura"], umbral_hr=cfg["mojado"]["umbral_hr"],
                     hr_rango=cfg["clima"]["hr_rango"], dist=dist, borde=cam.es_borde, ahora=h)
        u = ult_d.get(cam.cama_id)
        v["edad"] = (h - u[0]) if u else None
        v["ult_fuente"] = u[1] if u else "sensor_fijo"
        filas.append({"cama_id": cam.cama_id, **v})
    return pd.DataFrame(filas)


def variables_cama(corrida_id: str, cama_id: str) -> pd.DataFrame:
    """Variables de una cama (una fila)."""
    df = variables_bloque(corrida_id, U.partes(cama_id)[0])
    return df[df["cama_id"] == cama_id].reset_index(drop=True)


# ── alertas, incidencias y seguimientos ──────────────────────────────────────
def alertas(corrida_id: str, severidad: str | None = None, estado: str | None = None, tipo: str | None = None,
            tipos=None, bloque=None, orden: str = "severidad") -> pd.DataFrame:
    """Alertas visibles con los filtros del prototipo; orden por severidad u 'recientes'."""
    sql = f"SELECT {','.join(COLS_ALERTA)} FROM alertas WHERE corrida_id=? AND hora < ?"
    p: list = [corrida_id, _lim(corte(corrida_id))]
    if severidad and severidad != "todas":
        sql += " AND severidad=?"
        p.append(severidad)
    if estado and estado != "todas":
        sql += " AND estado=?"
        p.append(estado)
    if tipo and tipo != "todos":
        sql += " AND tipo=?"
        p.append(tipo)
    if tipos is not None:
        tipos = list(tipos)
        sql += f" AND tipo IN ({','.join('?' * len(tipos))})" if tipos else " AND 0"
        p += tipos
    if bloque not in (None, "todos", ""):
        sql += " AND cama_id LIKE ?"
        p.append(_bloque_like(int(bloque)))
    df = _q(sql, p)
    if orden == "recientes":
        return df.sort_values(["hora", "alerta_id"], ascending=False, ignore_index=True)
    df["_r"] = df["severidad"].map(SEV_RANK).fillna(9)
    df = df.sort_values(["_r", "hora", "alerta_id"], ascending=[True, False, False], ignore_index=True)
    return df.drop(columns="_r")


def _fotos_recibidas(corrida_id: str) -> dict[int, dict]:
    """Última foto de cada incidencia que ya llegó por cola_sync (modo sin red)."""
    df = _q("SELECT payload FROM cola_sync WHERE corrida_id=? AND tipo='inspeccion' AND hora_recibida IS NOT NULL "
            "ORDER BY id", (corrida_id,))
    fotos = {}
    for txt in df["payload"]:
        try:
            p = json.loads(txt)
        except (TypeError, ValueError):
            continue
        if isinstance(p, dict) and "incidencia_id" in p and "estado" in p:
            fotos[int(p["incidencia_id"])] = {k: p.get(k) for k in COLS_INC}
    return fotos


def incidencias(corrida_id: str, cama_id: str | None = None, bloque: int | None = None,
                grupo: str | None = None) -> pd.DataFrame:
    """Incidencias visibles (sin verdad_infectada), de la más reciente a la más antigua."""
    c = corte(corrida_id)
    df = _q(f"SELECT {','.join(COLS_INC)} FROM incidencias WHERE corrida_id=? AND hora_creada < ?",
            (corrida_id, _lim(c)))
    if c != SIN_CORTE and len(df):
        fotos = _fotos_recibidas(corrida_id)
        if fotos:
            filas = [fotos.get(int(r["incidencia_id"]), r.to_dict()) for _, r in df.iterrows()]
            df = pd.DataFrame(filas, columns=list(COLS_INC))
    if cama_id:
        df = df[df["cama_id"] == cama_id]
    if bloque is not None:
        df = df[df["cama_id"].str.startswith(f"B{int(bloque)}-")]
    if grupo == "abiertas":
        df = df[~df["estado"].isin(CERRADAS)]
    elif grupo == "cerradas":
        df = df[df["estado"] == "cerrada"]
    elif grupo == "descartadas":
        df = df[df["estado"] == "descartada"]
    return df.sort_values(["hora_creada", "incidencia_id"], ascending=False, ignore_index=True)


def seguimientos(corrida_id: str, incidencia_id: int | None = None) -> pd.DataFrame:
    """Revisitas del robot, en orden de hora."""
    sql = "SELECT * FROM seguimientos WHERE corrida_id=? AND hora < ?"
    p: list = [corrida_id, _lim(corte(corrida_id))]
    if incidencia_id is not None:
        sql += " AND incidencia_id=?"
        p.append(int(incidencia_id))
    return _q(sql + " ORDER BY hora, seguimiento_id", p)


# ── robots ───────────────────────────────────────────────────────────────────
def robots_actual(corrida_id: str) -> pd.DataFrame:
    """Última fila visible de cada robot."""
    return _q("SELECT d.* FROM robots d JOIN (SELECT robot_id, MAX(rowid) r FROM robots WHERE corrida_id=? "
              "AND hora < ? GROUP BY robot_id) m ON d.rowid=m.r ORDER BY d.robot_id",
              (corrida_id, _lim(corte(corrida_id))))


def prioridades_robot(corrida_id: str, robot_id: str) -> pd.DataFrame:
    """Cola de prioridad: camas en 'alto' del último cálculo que el robot aún no atiende (máx. top_camas)."""
    cfg = cargar()
    r = riesgo_ultimo(corrida_id)
    bloque = int("".join(ch for ch in robot_id if ch.isdigit()) or 0)
    if r.empty:
        return r
    r = r[(r["nivel"] == "alto") & r["cama_id"].str.startswith(f"B{bloque}-")]
    desde = int(r["dia"].max()) * 24 + cfg["riesgo"]["hora_calculo"] if len(r) else 0
    atendidas = set(_q("SELECT DISTINCT cama_id FROM robots WHERE corrida_id=? AND robot_id=? AND hora >= ? "
                       "AND hora < ? AND estado IN ('prioridad','inspeccionando')",
                       (corrida_id, robot_id, desde, _lim(corte(corrida_id))))["cama_id"])
    abiertas = set(incidencias(corrida_id, bloque=bloque, grupo="abiertas")["cama_id"])
    r = r[~r["cama_id"].isin(atendidas | abiertas)]
    r = r.sort_values(["prob_ia_7d", "cama_id"], ascending=[False, True])
    return r.head(cfg["dashboard"]["ui"]["top_camas"]).reset_index(drop=True)


def ultima_visita(corrida_id: str, cama_id: str) -> pd.DataFrame:
    """Última vez que un robot estuvo en la cama (0 o 1 fila)."""
    return _q("SELECT * FROM robots WHERE corrida_id=? AND cama_id=? AND hora < ? ORDER BY hora DESC, rowid DESC "
              "LIMIT 1", (corrida_id, cama_id, _lim(corte(corrida_id))))


# ── ventilación ──────────────────────────────────────────────────────────────
def ventilacion_actual(corrida_id: str) -> pd.DataFrame:
    """Estado actual de cada nave con ventilación (sin cambios = encendida)."""
    ult = _q("SELECT v.* FROM ventilacion v JOIN (SELECT bloque, nave, MAX(rowid) r FROM ventilacion "
             "WHERE corrida_id=? AND hora < ? GROUP BY bloque, nave) m ON v.rowid=m.r",
             (corrida_id, _lim(corte(corrida_id))))
    naves = _q("SELECT DISTINCT bloque, nave FROM camas WHERE tiene_ventilacion=1 ORDER BY bloque, nave")
    df = naves.merge(ult[["bloque", "nave", "hora", "estado", "motivo"]], on=["bloque", "nave"], how="left")
    df["estado"] = df["estado"].fillna("encendida")
    return df


def ventilacion_historial(corrida_id: str, n: int | None = None) -> pd.DataFrame:
    """Últimos n cambios de ventilación, del más reciente al más antiguo."""
    n = n or cargar()["dashboard"]["ui"]["max_historial_ventilacion"]
    return _q("SELECT * FROM ventilacion WHERE corrida_id=? AND hora < ? AND hora > 0 ORDER BY hora DESC, rowid DESC "
              "LIMIT ?", (corrida_id, _lim(corte(corrida_id)), int(n)))


# ── sincronización ───────────────────────────────────────────────────────────
def cola_pendiente(corrida_id: str) -> pd.DataFrame:
    """Datos guardados en los robots que aún no llegan (hora_recibida NULL)."""
    return _q("SELECT id, corrida_id, origen, hora_generada, hora_recibida, tipo FROM cola_sync "
              "WHERE corrida_id=? AND hora_recibida IS NULL ORDER BY id", (corrida_id,))


def ultima_sync(corrida_id: str) -> pd.DataFrame:
    """Hora de la última sincronización (columna `hora`, NaN si nunca)."""
    return _q("SELECT MAX(hora_recibida) hora FROM cola_sync WHERE corrida_id=?", (corrida_id,))


# ── métricas ─────────────────────────────────────────────────────────────────
def cobertura(corrida_id: str, horas: float = 24, bloque: int | None = None) -> pd.DataFrame:
    """Fracción de camas medidas directamente por el robot en las últimas `horas` (columna `cobertura`)."""
    h, c = ahora(corrida_id), corte(corrida_id)
    tot = len(camas(bloque))
    sql = ("SELECT COUNT(DISTINCT cama_id) FROM lecturas WHERE corrida_id=? AND fuente!='sensor_fijo' "
           "AND hora >= ? AND hora < ?")
    p: list = [corrida_id, h - horas, _lim(c)]
    if bloque is not None:
        sql += " AND cama_id LIKE ?"
        p.append(_bloque_like(bloque))
    ok = _uno(sql, p) or 0
    return pd.DataFrame([{"cobertura": ok / tot if tot else 0.0}])


def metricas(corrida_id: str) -> pd.DataFrame:
    """Métricas de la pantalla Análisis (una fila)."""
    inc, al = incidencias(corrida_id), alertas(corrida_id)
    conf = inc[inc["hora_confirmada"].notna()]
    desc = inc[inc["estado"] == "descartada"]
    r7 = al[al["tipo"] == "riesgo_7d"]
    resp = []
    for i in conf.itertuples():
        a = r7[(r7["cama_id"] == i.cama_id) & (r7["hora"] <= i.hora_confirmada)
               & (i.hora_confirmada - r7["hora"] <= 7 * 24)]
        if len(a):
            resp.append(i.hora_confirmada - a["hora"].min())
    n_c, n_d = len(conf), len(desc)
    fila = {
        "respuesta": sum(resp) / len(resp) if resp else None, "n_resp": len(resp),
        "conf": n_c, "desc": n_d, "tasa": n_c / (n_c + n_d) if n_c + n_d else None,
        "cobertura": float(cobertura(corrida_id, 24)["cobertura"].iloc[0]),
        "revisitas": len(seguimientos(corrida_id)),
        "origen_prediccion": int((inc["origen"] == "prediccion").sum()),
        "origen_patrulla": int((inc["origen"] == "patrulla").sum()),
        "plantas": int(inc[~inc["estado"].isin(CERRADAS)]["plantas_afectadas"].fillna(0).sum()),
    }
    for t in TIPOS_ALERTA:
        fila[f"tipo_{t}"] = int((al["tipo"] == t).sum())
    return pd.DataFrame([fila])
