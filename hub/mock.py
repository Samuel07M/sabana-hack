"""Datos de prueba que cumplen contrato/schema.sql: port de FuenteLocal del prototipo HTML (retirado).

    python -m hub.mock                          # las tres corridas completas → data/mock.db
    python -m hub.mock --vivo --corrida demo    # una hora simulada por segundo desde la hora 8

La verdad del simulador (estado de cada planta) se queda en memoria: no va a la base.
"""
import argparse
import bisect
import json
import math
import sqlite3
import time
from pathlib import Path

import numpy as np

from hub import ubicacion as U
from hub.config import RAIZ, cargar
from hub.variables import ESTADOS_CONFIRMADOS, SIN_CONFIRMADA, calcular

SCHEMA = RAIZ / "contrato" / "schema.sql"
RUTA_MOCK = RAIZ / "data" / "mock.db"
TABLAS_CORRIDA = ("lecturas", "riesgo", "incidencias", "seguimientos", "alertas", "robots", "ventilacion",
                  "cola_sync", "corridas")
COLS = {
    "lecturas": ("corrida_id", "hora", "cama_id", "temp_c", "hr", "fuente"),
    "riesgo": ("corrida_id", "dia", "cama_id", "enfermedad", "riesgo_reglas", "prob_ia_7d", "nivel"),
    "incidencias": ("incidencia_id", "corrida_id", "cama_id", "posicion", "origen", "estado", "hora_creada",
                    "hora_confirmada", "hora_cerrada", "confianza", "plantas_afectadas", "verdad_infectada"),
    "seguimientos": ("seguimiento_id", "incidencia_id", "corrida_id", "hora", "robot_id", "resultado",
                     "plantas_afectadas", "nota"),
    "alertas": ("alerta_id", "corrida_id", "hora", "cama_id", "incidencia_id", "severidad", "tipo", "titulo",
                "mensaje", "estado", "accion"),
    "robots": ("corrida_id", "hora", "robot_id", "cama_id", "estado", "bateria"),
    "ventilacion": ("corrida_id", "hora", "bloque", "nave", "estado", "motivo"),
    "cola_sync": ("id", "corrida_id", "origen", "hora_generada", "hora_recibida", "tipo", "payload"),
}
IDS = {"incidencias": "incidencia_id", "seguimientos": "seguimiento_id", "alertas": "alerta_id", "cola_sync": "id"}
RES = {"empeora": "Empeora", "igual": "Igual", "mejora": "Mejora", "limpia": "Limpia"}
SANA, LATENTE, SINTOMAS, TRATADA, PERDIDA = range(5)


def plural(n: int, s: str, p: str) -> str:
    """'1 planta afectada' / '3 plantas afectadas'."""
    return f"{n} {s if n == 1 else p}"


def num(x: float) -> str:
    """95.0 → '95'; 92.5 → '92.5'."""
    return f"{x:g}"


# ── base de datos ────────────────────────────────────────────────────────────
def abrir_base(ruta: Path, cfg: dict) -> sqlite3.Connection:
    """Abre (o crea desde contrato/schema.sql) la base en modo WAL."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(f"PRAGMA busy_timeout={int(cfg['base_datos']['busy_timeout_ms'])}")
    if not con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='corridas'").fetchone()[0]:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
    return con


def borrar_corrida(con: sqlite3.Connection, corrida_id: str) -> None:
    """Quita las filas de una corrida (las demás se conservan)."""
    for t in TABLAS_CORRIDA:
        con.execute(f"DELETE FROM {t} WHERE corrida_id=?", (corrida_id,))
    con.commit()


def ids_libres(con: sqlite3.Connection) -> dict:
    """Siguiente id libre por tabla (los ids son únicos entre corridas)."""
    return {t: (con.execute(f"SELECT COALESCE(MAX({c}), 0) FROM {t}").fetchone()[0]) for t, c in IDS.items()}


# ── simulación ───────────────────────────────────────────────────────────────
class FuenteLocal:
    """Simulación de una corrida con el mismo comportamiento que FuenteLocal del prototipo."""

    def __init__(self, corrida: dict, cfg: dict, ids: dict | None = None):
        self.cfg, self.c, self.id = cfg, corrida, corrida["corrida_id"]
        self.M = cfg["dashboard"]["mock"]
        self.rng = np.random.default_rng(corrida["semilla"])
        self.guion = bool(corrida.get("guion"))
        self.red = "sin_red" if corrida["escenario"] == "robots_celular" else "local"
        self.hora = 0
        self.ultima_sync = None
        self.hora_sync_dia: dict[int, int] = {}
        self.programados: list[tuple] = []
        self.n_prog = 0
        self.ids = dict(ids or {t: 0 for t in IDS})
        self.buf = {t: [] for t in COLS}
        self.inc: dict[int, dict] = {}
        self.inc_sucias: set[int] = set()
        self.ref_inc: dict[int, dict] = {}
        self.verdad_ref: dict[int, int] = {}
        self.ref_seq = 0
        self.segs_inc: dict[int, list] = {}
        self.ultimo_nivel: dict[str, str] = {}
        self.cola_pend: list[dict] = []
        self.cola_upd: list[int] = []
        self._geometria()
        self._clima()
        self._plantas()
        self._ventilacion_inicial()
        self._robots()
        self._focos()

    # ---- inicio ----
    def _geometria(self):
        """Camas en orden bloque → nave → cama, con índices para numpy."""
        g = self.cfg["geometria"]
        self.B, self.NN, self.CN, self.P = g["bloques"], g["naves_por_bloque"], g["camas_por_nave"], g["plantas_por_cama"]
        self.camas, self.idx = [], {}
        for b in range(1, self.B + 1):
            for n in range(1, self.NN + 1):
                for k in range(1, self.CN + 1):
                    num_c = (n - 1) * self.CN + k
                    cid = U.cama_id(b, n, num_c)
                    self.idx[cid] = len(self.camas)
                    self.camas.append({"cama_id": cid, "bloque": b, "nave": n, "cama": num_c,
                                       "es_borde": int(k in (1, self.CN)),
                                       "tiene_ventilacion": int(bool(g["tiene_ventilacion"]))})
        self.nC = len(self.camas)
        self.nNav = self.B * self.NN
        self.c_bloque = np.array([c["bloque"] for c in self.camas])
        self.c_nav = np.array([(c["bloque"] - 1) * self.NN + c["nave"] - 1 for c in self.camas])
        self.c_borde = np.array([c["es_borde"] for c in self.camas], dtype=float)
        self.lect: dict[str, list] = {c["cama_id"]: [] for c in self.camas}
        self.lect_horas: dict[str, list] = {c["cama_id"]: [] for c in self.camas}
        self.sensor: dict[int, dict] = {b: {} for b in range(1, self.B + 1)}
        sf = self.M["sensor_fijo"]
        self.sensor_cama = {b: U.cama_id(b, sf["nave"], (sf["nave"] - 1) * self.CN + sf["cama_en_nave"])
                            for b in range(1, self.B + 1)}

    def _clima(self):
        """Desfases por nave y eventos húmedos por bloque."""
        c, r, gd = self.cfg["clima"], self.rng, self.M["guion_demo"]
        self.offT = r.normal(0, c["offset_nave_T_sd"], self.nNav)
        self.offHR = r.normal(0, c["offset_nave_HR_sd"], self.nNav)
        self.eventos = {}
        ev = gd["evento"]
        for b in range(1, self.B + 1):
            lista = []
            for d in range(self.cfg["sim"]["dias"]):
                if r.random() < c["eventos_humedos_por_dia"]:
                    ini = d * 24 + int(r.integers(0, 24))
                    dur = int(r.integers(c["duracion_evento_h"][0], c["duracion_evento_h"][1] + 1))
                    if self.guion and b == ev["bloque"] and d < gd["dias_sin_eventos"]:
                        continue
                    lista.append((ini, ini + dur, float(c["subida_evento_hr"])))
            if self.guion and b == ev["bloque"]:
                lista.append((ev["ini"], ev["fin"], float(ev["subida_hr"])))
            self.eventos[b] = lista
        self.wet_ring = np.zeros((self.nC, 24), dtype=np.int8)
        self.wet24 = np.zeros(self.nC)
        self.Tv = np.zeros(self.nC)
        self.HRv = np.zeros(self.nC)

    def _plantas(self):
        """Estado y próximo cambio de cada planta (la verdad, solo en memoria)."""
        self.est = np.zeros((self.nNav, self.CN, self.P), dtype=np.int8)
        self.t_sig = np.zeros((self.nNav, self.CN, self.P))
        L = self.cfg["enfermedad"]["L_aire_camas"]
        k = np.arange(self.CN)
        dk = k[None, :] - k[:, None]
        self.m_aire = np.where(dk > 0, np.exp(-dk / L), 0.0)

    def _ventilacion_inicial(self):
        """Todas las naves con ventilación empiezan encendidas (sin fila: el hub lo asume)."""
        self.vent = {}
        if self.cfg["geometria"]["tiene_ventilacion"]:
            for kn in range(self.nNav):
                self.vent[kn] = {"estado": "encendida", "token": 0}

    def _robots(self):
        """Un robot por bloque, en la cama 1, en patrulla."""
        self.robots = []
        for b in range(1, self.B + 1):
            d = {"robot_id": f"B{b}", "bloque": b, "pos": 1, "dir": 1, "cama_id": U.cama_id(b, 1, 1),
                 "estado": "patrulla", "bateria": 100.0, "carga_hasta": 0.0, "tarea": None, "prioridades": [],
                 "ult_insp_prio": {}, "incs": {}, "revisitas": []}
            self.robots.append(d)
            self._fila("robots", corrida_id=self.id, hora=0.0, robot_id=d["robot_id"], cama_id=d["cama_id"],
                       estado="patrulla", bateria=100)

    def _focos(self):
        """Foco del guion y focos aleatorios de la temporada."""
        r, e, Me, gd = self.rng, self.cfg["enfermedad"], self.M["enfermedad"], self.M["guion_demo"]
        if self.guion:
            ci = self.idx[gd["cama"]]
            self._programar(gd["hora_foco"], lambda h, ci=ci: [self._infectar(ci, p - 1, h) for p in gd["posiciones_foco"]])
        lo, hi = e["focos_por_temporada"]
        esquina = self.cfg["geometria"]["posiciones_esquina"][0]
        for _ in range(int(r.integers(lo, hi + 1))):
            b = int(r.integers(2, self.B + 1)) if self.guion else int(r.integers(1, self.B + 1))
            nave = int(r.integers(1, self.NN + 1))
            k = int(r.choice([1, self.CN])) if r.random() < Me["peso_foco_borde"] else int(r.integers(1, self.CN + 1))
            ci = self.idx[U.cama_id(b, nave, (nave - 1) * self.CN + k)]
            pos = int(r.integers(1, esquina + 1)) if r.random() < 0.5 else int(r.integers(1, self.P + 1))
            hora = int(r.integers(0, Me["dias_ventana_foco"] * 24 + 1))
            self._programar(hora, lambda h, ci=ci, pos=pos: self._infectar(ci, pos - 1, h))

    # ---- utilidades ----
    def _fila(self, tabla: str, **row) -> dict:
        """Agrega una fila al búfer de escritura."""
        if tabla in IDS and IDS[tabla] not in row:
            self.ids[tabla] += 1
            row[IDS[tabla]] = self.ids[tabla]
        self.buf[tabla].append(row)
        return row

    def _programar(self, hora: float, fn) -> None:
        """Agenda fn(h) para cuando la simulación llegue a `hora`."""
        self.n_prog += 1
        self.programados.append((hora, self.n_prog, fn))

    def _ci(self, ci: int) -> tuple[int, int]:
        """(índice de nave, cama dentro de la nave) de un índice de cama."""
        return ci // self.CN, ci % self.CN

    def _infectar(self, ci: int, p: int, h: float) -> None:
        """Una planta sana pasa a latente."""
        kn, k = self._ci(ci)
        if self.est[kn, k, p] != SANA:
            return
        lat = self.cfg["enfermedad"]["latencia_dias"]
        self.est[kn, k, p] = LATENTE
        self.t_sig[kn, k, p] = h + self.rng.uniform(lat[0], lat[1]) * 24

    def _vent_on(self, kn: int) -> bool:
        """True si la nave tiene ventilación y está encendida."""
        v = self.vent.get(kn)
        return bool(v) and v["estado"] == "encendida"

    def _es_guion(self, cid: str) -> bool:
        """True si es la cama del guion de la demo."""
        return self.guion and cid == self.M["guion_demo"]["cama"]

    # ---- paso de una hora ----
    def step(self, entre_ticks=None) -> bool:
        """Avanza una hora simulada; `entre_ticks()` se llama tras cada tick de los robots (modo vivo)."""
        if self.hora >= self.cfg["sim"]["dias"] * 24:
            return False
        h = self.hora
        self._correr_programados(h)
        self._clima_hora(h)
        self._sensores(h)
        self._enfermedad(h)
        tph = int(60 / self.cfg["robots"]["min_por_cama"])
        for k in range(tph):
            t = h + k / tph
            for d in self.robots:
                self._tick(d, t, tph)
            if entre_ticks:
                entre_ticks()
        if self.red == "local" and h % 24 == self.cfg["riesgo"]["hora_calculo"]:
            self.calcular_riesgo(h)
        if self.red == "sin_red" and h % 24 == self._hora_sync(h // 24):
            self.sincronizar(h)
        self.hora += 1
        return True

    def _correr_programados(self, h: int) -> None:
        """Ejecuta lo agendado hasta la hora h, en orden."""
        ya = sorted((p for p in self.programados if p[0] <= h), key=lambda p: (p[0], p[1]))
        if not ya:
            return
        self.programados = [p for p in self.programados if p[0] > h]
        for _, _, fn in ya:
            fn(h)

    def _hora_sync(self, dia: int) -> int:
        """Hora del día en que pasa el celular (una vez al día, en la ventana del YAML)."""
        if dia not in self.hora_sync_dia:
            lo, hi = self.cfg["celular"]["ventana_hora"]
            self.hora_sync_dia[dia] = int(self.rng.integers(lo, hi + 1))
        return self.hora_sync_dia[dia]

    def _clima_hora(self, h: int) -> None:
        """T y HR de cada cama; la ventilación encendida baja la HR."""
        c, r = self.cfg["clima"], self.rng
        s = math.sin(2 * math.pi * (h - 9) / 24)
        ev = np.array([sum(m for a, z, m in self.eventos[b] if a <= h < z) for b in range(1, self.B + 1)])
        vent = np.array([self._vent_on(kn) for kn in range(self.nNav)], dtype=float)
        T = c["T_media"] + c["A_T"] * s + self.offT[self.c_nav] + r.normal(0, c["ruido_T_sd"], self.nC)
        HR = (c["HR_media"] - c["A_HR"] * s + self.offHR[self.c_nav] + c["extra_borde_hr"] * self.c_borde
              + ev[self.c_bloque - 1] + vent[self.c_nav] * c["delta_ventilacion_hr"]
              + r.normal(0, c["ruido_HR_sd"], self.nC))
        HR = np.clip(HR, *c["hr_rango"])
        w = (HR >= self.cfg["mojado"]["umbral_hr"]).astype(np.int8)
        slot = h % 24
        self.wet24 += w - self.wet_ring[:, slot]
        self.wet_ring[:, slot] = w
        self.Tv, self.HRv = T, HR

    def _sensores(self, h: int) -> None:
        """Un sensor fijo por bloque: una lectura por hora."""
        s, lo_hi = self.cfg["sensores"], self.cfg["clima"]["hr_rango"]
        for b, cid in self.sensor_cama.items():
            i = self.idx[cid]
            t = round(float(self.Tv[i] + self.rng.normal(0, s["ruido_T_sd"])), 1)
            hr = round(float(np.clip(self.HRv[i] + self.rng.normal(0, s["ruido_HR_sd"]), *lo_hi)), 1)
            self.sensor[b][h] = (t, hr)
            self._fila("lecturas", corrida_id=self.id, hora=h, cama_id=cid, temp_c=t, hr=hr, fuente="sensor_fijo")

    def _enfermedad(self, h: int) -> None:
        """Contagio por plantas vecinas y por corriente de aire; avance latente → síntomas → perdida."""
        e, Me, r = self.cfg["enfermedad"], self.M["enfermedad"], self.rng
        E = self.est
        W = np.where(E == LATENTE, e["peso_latente"], np.where(E == SINTOMAS, e["peso_sintomas"], 0.0))
        pv = np.zeros_like(W)
        if W.any():
            for d in (-2, -1, 1, 2):
                pv += _desplazar(W, 0, d)
            for dk in (-1, 1):
                for d in (-1, 0, 1):
                    pv += Me["peso_cama_vecina"] * _desplazar(W, dk, d)
            vent = np.array([self._vent_on(kn) for kn in range(self.nNav)], dtype=float)
            pa = (W.sum(axis=2) * vent[:, None]) @ self.m_aire
        else:
            pa = np.zeros((self.nNav, self.CN))
        fT = np.exp(-(((self.Tv - Me["T_opt"]) / Me["T_ancho"]) ** 2)).reshape(self.nNav, self.CN)
        fM = np.minimum(1.0, self.wet24 / Me["horas_mojado_full"]).reshape(self.nNav, self.CN)
        rate = (Me["beta_vec"] * pv + Me["beta_aire"] * pa[:, :, None] + Me["beta_0"]) * (fT * fM)[:, :, None]
        nuevas = (E == SANA) & (fM[:, :, None] > 0) & (r.random(E.shape) < 1 - np.exp(-rate))
        m1 = (E == LATENTE) & (h >= self.t_sig)
        m2 = (E == SINTOMAS) & (h >= self.t_sig)
        m3 = (E == TRATADA) & (h >= self.t_sig)
        lat, sp = e["latencia_dias"], e["sintomas_a_perdida_dias"]
        E[m1] = SINTOMAS
        self.t_sig[m1] = h + r.uniform(sp[0], sp[1], int(m1.sum())) * 24
        E[m2] = PERDIDA
        E[m3] = SANA
        E[nuevas] = LATENTE
        self.t_sig[nuevas] = h + r.uniform(lat[0], lat[1], int(nuevas.sum())) * 24

    def _contar(self, cid: str, sL: float, sS: float) -> dict:
        """Plantas infectadas reales, detectadas por la cámara y primera posición infectada."""
        kn, k = self._ci(self.idx[cid])
        st = self.est[kn, k]
        inf = (st == LATENTE) | (st == SINTOMAS)
        real = int(inf.sum())
        pos = int(np.argmax(inf)) + 1 if real else None
        u = self.rng.random(self.P)
        det = int(((st == LATENTE) & (u < sL)).sum() + ((st == SINTOMAS) & (u < sS)).sum())
        return {"real": real, "det": det, "pos": pos}

    def _tratar_plantas(self, cid: str, h: float) -> None:
        """El tratamiento cura con la eficacia del YAML y protege unos días."""
        e = self.cfg["enfermedad"]
        kn, k = self._ci(self.idx[cid])
        st = self.est[kn, k]
        m = ((st == LATENTE) | (st == SINTOMAS)) & (self.rng.random(self.P) < e["eficacia_tratamiento"])
        st[m] = TRATADA
        self.t_sig[kn, k][m] = h + e["dias_proteccion"] * 24

    # ---- robots ----
    def _tick(self, d: dict, t: float, tph: int) -> None:
        """Un tick de min_por_cama: carga, revisita, prioridad, inspección o patrulla 1→72→1."""
        D = self.cfg["robots"]
        if d["estado"] == "carga":
            if t >= d["carga_hasta"] - 1e-9:
                d["bateria"] = 100.0
                self._mover(d, d["cama_id"], "patrulla", t)
            return
        if d["bateria"] <= D["bateria_min"] * 100:
            d["carga_hasta"] = t + D["horas_carga"]
            self._mover(d, d["cama_id"], "carga", t)
            return
        d["bateria"] = max(0.0, d["bateria"] - 100 / (D["bateria_horas"] * tph))
        if not d["tarea"]:
            iR = next((i for i, x in enumerate(d["revisitas"]) if x["hora"] <= t), -1)
            if iR >= 0:
                x = d["revisitas"].pop(iR)
                d["tarea"] = {"tipo": "revisita", "cama_id": x["cama_id"], "ref": x["ref"], "fase": "ir"}
            else:
                while d["prioridades"]:
                    c = d["prioridades"].pop(0)
                    u = d["ult_insp_prio"].get(c)
                    if u is not None and t - u < D["horas_sin_visita_prioridad"]:
                        continue
                    if d["incs"].get(c, {}).get("abierta"):
                        continue
                    d["tarea"] = {"tipo": "prioridad", "cama_id": c, "fase": "ir"}
                    break
        if d["tarea"]:
            ta = d["tarea"]
            if ta["fase"] == "ir":
                self._mover(d, ta["cama_id"], "prioridad", t)
                self._lectura_robot(d, ta["cama_id"], t)
                ta["fase"], ta["fin"] = "insp", t + D["horas_verificacion"]
                return
            self._mover(d, ta["cama_id"], "inspeccionando", t)
            if t + 1e-9 >= ta["fin"]:
                self._ejecutar_tarea(d, ta, t)
                d["tarea"] = None
            return
        total = self.NN * self.CN
        nxt = d["pos"] + d["dir"]
        if nxt > total or nxt < 1:
            d["dir"] *= -1
            nxt = d["pos"] + d["dir"]
        d["pos"] = nxt
        cid = U.cama_id(d["bloque"], (nxt - 1) // self.CN + 1, nxt)
        self._mover(d, cid, "patrulla", t)
        self._lectura_robot(d, cid, t)
        self._inspeccion_ligera(d, cid, t)

    def _mover(self, d: dict, cid: str, estado: str, t: float) -> None:
        """Registra en `robots` solo los cambios de cama o de estado."""
        if d["cama_id"] == cid and d["estado"] == estado:
            return
        d["cama_id"], d["estado"] = cid, estado
        self._fila("robots", corrida_id=self.id, hora=round(t, 2), robot_id=d["robot_id"], cama_id=cid,
                   estado=estado, bateria=int(round(d["bateria"])))

    def _lectura_robot(self, d: dict, cid: str, t: float) -> None:
        """El robot mide T y HR al pasar por la cama."""
        i, s = self.idx[cid], self.cfg["sensores"]
        row = {"hora": int(math.floor(t)), "cama_id": cid,
               "temp_c": round(float(self.Tv[i] + self.rng.normal(0, s["ruido_T_sd"])), 1),
               "hr": round(float(np.clip(self.HRv[i] + self.rng.normal(0, s["ruido_HR_sd"]),
                                         *self.cfg["clima"]["hr_rango"])), 1),
               "fuente": f"robot:{d['robot_id']}"}
        self._fila("lecturas", corrida_id=self.id, **row)
        self.lect[cid].append((row["hora"], row["temp_c"], row["hr"], row["fuente"]))
        self.lect_horas[cid].append(row["hora"])
        self._cola(d, "lectura", row, t)

    def _inspeccion_ligera(self, d: dict, cid: str, t: float) -> None:
        """En patrulla la cámara mira de pasada; si ve algo, se queda a verificar."""
        D, Mo = self.cfg["robots"], self.M["robots"]
        if d["incs"].get(cid, {}).get("abierta") or self._es_guion(cid):
            return
        c = self._contar(cid, D["sens_latente"], D["sens_sintomas"])
        fp = self.rng.random() < (1 - D["especificidad"]) * Mo["factor_fp_patrulla"]
        if c["det"] > 0 or fp:
            self.ref_seq += 1
            ref = self.ref_seq
            posicion = c["pos"] if c["pos"] is not None else int(self.rng.integers(1, self.P + 1))
            self._sospecha(d, ref, cid, posicion, "patrulla", t)
            d["tarea"] = {"tipo": "confirmar", "cama_id": cid, "ref": ref, "det": c["det"], "posicion": posicion,
                          "fase": "insp", "fin": t + D["horas_verificacion"]}
            self._mover(d, cid, "inspeccionando", t)

    def _ejecutar_tarea(self, d: dict, ta: dict, t: float) -> None:
        """Termina una verificación, una visita prioritaria o una revisita."""
        D, Mo, gd = self.cfg["robots"], self.M["robots"], self.M["guion_demo"]
        if ta["tipo"] == "confirmar":
            self._resolver(d, ta["cama_id"], t, ta["ref"], ta["det"], ta["posicion"], None)
            return
        if ta["tipo"] == "prioridad":
            d["ult_insp_prio"][ta["cama_id"]] = t
            f = Mo["factor_inspeccion_prioridad"]
            c = self._contar(ta["cama_id"], min(1.0, D["sens_latente"] * f), D["sens_sintomas"])
            forzar = gd if self._es_guion(ta["cama_id"]) else None
            if c["det"] > 0 or forzar:
                self.ref_seq += 1
                ref = self.ref_seq
                posicion = forzar["posicion"] if forzar else (c["pos"] or int(self.rng.integers(1, self.P + 1)))
                self._sospecha(d, ref, ta["cama_id"], posicion, "prediccion", t - D["horas_verificacion"])
                self._resolver(d, ta["cama_id"], t, ref, c["det"], posicion, forzar)
            return
        if ta["tipo"] == "revisita":
            inc = d["incs"].get(ta["cama_id"])
            if not inc:
                return
            n = self._contar(ta["cama_id"], 1, 1)["real"]
            if n == 0:
                res = "limpia"
            elif n > inc["prev"]:
                res = "empeora"
            elif n == inc["prev"]:
                res = "igual"
            else:
                res = "mejora"
            if self._es_guion(ta["cama_id"]) and inc["n"] < len(gd["seguimientos"]):
                res, n = gd["seguimientos"][inc["n"]]
            inc["n"] += 1
            self._seguimiento(d, inc["ref"], t, res, int(n), inc["prev"], f"Revisita automática n.º {inc['n']}")
            inc["prev"] = int(n)
            inc["limpias"] = inc["limpias"] + 1 if res == "limpia" else 0
            if inc["limpias"] >= D["limpias_para_cerrar"]:
                inc["abierta"] = False
            else:
                d["revisitas"].append({"cama_id": ta["cama_id"], "ref": inc["ref"], "hora": t + D["dias_revisita"] * 24})

    def _resolver(self, d, cid, t, ref, det, posicion, forzar) -> None:
        """Verificación de una sospecha: confirmada o descartada."""
        D, Mo = self.cfg["robots"], self.M["robots"]
        real = self._contar(cid, 0, 0)["real"]
        confirma = True if forzar else (real > 0 and self.rng.random() < Mo["prob_confirmar"])
        plantas = forzar["plantas"] if forzar else max(det, 1)
        rango = Mo["confianza_confirmada"] if confirma else Mo["confianza_descartada"]
        confianza = forzar["confianza"] if forzar else round(float(self.rng.uniform(*rango)), 2)
        self.verdad_ref[ref] = int(real > 0)
        self._inspeccion(d, ref, t, "confirmada" if confirma else "descartada", confianza, plantas if confirma else 0)
        if confirma:
            d["incs"][cid] = {"ref": ref, "abierta": True, "limpias": 0, "prev": plantas, "n": 0}
            d["revisitas"].append({"cama_id": cid, "ref": ref, "hora": t + D["dias_revisita"] * 24})

    # ---- incidencias, seguimientos y alertas (se escriben en tiempo real) ----
    def _cola(self, d: dict | None, tipo: str, payload: dict, t: float) -> None:
        """Sin red: el dato también queda en cola_sync hasta que pase el celular."""
        if self.red != "sin_red":
            return
        row = self._fila("cola_sync", corrida_id=self.id, origen=f"robot:{d['robot_id']}" if d else "robot",
                         hora_generada=int(math.floor(t)), hora_recibida=None, tipo=tipo,
                         payload=json.dumps(payload, ensure_ascii=False))
        self.cola_pend.append(row)

    def _foto_inc(self, inc: dict) -> dict:
        """Columnas de la incidencia para cola_sync (sin verdad_infectada)."""
        return {k: inc[k] for k in COLS["incidencias"] if k != "verdad_infectada"}

    def _tocar_inc(self, inc: dict, d: dict | None, t: float) -> None:
        """Marca la incidencia para reescribirla y la manda a la cola si no hay red."""
        self.inc_sucias.add(inc["incidencia_id"])
        self._cola(d, "inspeccion", self._foto_inc(inc), t)

    def _sospecha(self, d, ref, cid, posicion, origen, hora) -> None:
        """Nace una incidencia en estado sospecha."""
        inc = {"incidencia_id": None, "corrida_id": self.id, "cama_id": cid, "posicion": int(posicion),
               "origen": origen, "estado": "sospecha", "hora_creada": int(math.floor(hora)), "hora_confirmada": None,
               "hora_cerrada": None, "confianza": None, "plantas_afectadas": None, "verdad_infectada": None}
        self.ids["incidencias"] += 1
        inc["incidencia_id"] = self.ids["incidencias"]
        self.inc[inc["incidencia_id"]] = inc
        self.ref_inc[ref] = inc
        self._tocar_inc(inc, d, hora)

    def _inspeccion(self, d, ref, t, resultado, confianza, plantas) -> None:
        """Resultado de la verificación: alerta confirmacion (y ventilación) o descartada."""
        inc = self.ref_inc.get(ref)
        if not inc:
            return
        ahora = int(math.floor(t))
        corto = U.corto(inc["cama_id"])
        inc["estado"], inc["confianza"] = resultado, confianza
        inc["verdad_infectada"] = self.verdad_ref.get(ref, 0)
        if resultado == "confirmada":
            inc["hora_confirmada"], inc["plantas_afectadas"] = ahora, int(plantas)
            self._tocar_inc(inc, d, t)
            self._alerta(ahora, inc["cama_id"], inc["incidencia_id"], "confirmacion",
                         f"Botrytis confirmada · {corto}",
                         f"Botrytis confirmada · {corto} · posición {inc['posicion']}. "
                         f"{plural(int(plantas), 'planta afectada', 'plantas afectadas')} (confianza {confianza:.2f}).")
            self._ventilacion_auto(inc, ahora)
            self._programar(ahora + self.cfg["robots"]["horas_hasta_tratamiento"],
                            lambda h, inc=inc, d=d: self._tratar(inc, d, h))
        else:
            inc["hora_cerrada"], inc["plantas_afectadas"] = ahora, 0
            self._tocar_inc(inc, d, t)
            self._alerta(ahora, inc["cama_id"], inc["incidencia_id"], "descartada",
                         f"Sospecha descartada · {corto}",
                         f"Sospecha descartada · {corto} · posición {inc['posicion']}. "
                         f"La inspección de cerca no confirmó Botrytis (confianza {confianza:.2f}).")

    def _seguimiento(self, d, ref, t, res, n, prev, nota) -> None:
        """Revisita registrada por el robot; actualiza la incidencia y crea la alerta seguimiento."""
        inc = self.ref_inc.get(ref)
        if not inc:
            return
        ahora = int(math.floor(t))
        segs = self.segs_inc.setdefault(inc["incidencia_id"], [])
        prev_seg = segs[-1] if segs else None
        seg = self._fila("seguimientos", incidencia_id=inc["incidencia_id"], corrida_id=self.id, hora=ahora,
                         robot_id=d["robot_id"], resultado=res, plantas_afectadas=n, nota=nota)
        segs.append(seg)
        self._cola(d, "seguimiento", {k: seg[k] for k in COLS["seguimientos"]}, t)
        corto, extra = U.corto(inc["cama_id"]), ""
        if res == "empeora":
            inc["estado"] = "confirmada"
            extra = " Se programa un nuevo tratamiento."
            self._programar(ahora + self.cfg["robots"]["horas_hasta_tratamiento"],
                            lambda h, inc=inc, d=d: self._tratar(inc, d, h))
        elif res == "limpia" and prev_seg and prev_seg["resultado"] == "limpia":
            inc["estado"], inc["hora_cerrada"] = "cerrada", ahora
            extra = " Dos revisitas limpias seguidas: incidencia cerrada."
        else:
            inc["estado"] = "en_seguimiento"
        inc["plantas_afectadas"] = n
        self._tocar_inc(inc, d, t)
        self._alerta(ahora, inc["cama_id"], inc["incidencia_id"], "seguimiento",
                     f"Seguimiento · {RES[res]} · {corto}",
                     f"{nota} · {corto}: {RES[res].lower()} "
                     f"({plural(n, 'planta afectada', 'plantas afectadas')}; antes {prev}).{extra}",
                     empeora=res == "empeora")

    def _tratar(self, inc: dict, d: dict, h: int) -> None:
        """Tratamiento a las horas_hasta_tratamiento de confirmar."""
        if inc["estado"] != "confirmada":
            return
        inc["estado"] = "en_tratamiento"
        self._tratar_plantas(inc["cama_id"], h)
        self._tocar_inc(inc, d, h)

    def _alerta(self, hora, cid, inc_id, tipo, titulo, mensaje, empeora=False) -> None:
        """Alerta nueva con la severidad de alertas.severidad del YAML."""
        sev = self.cfg["alertas"]["severidad"]
        severidad = sev["seguimiento_empeora"] if empeora else sev[tipo]
        self._fila("alertas", corrida_id=self.id, hora=int(hora), cama_id=cid, incidencia_id=inc_id,
                   severidad=severidad, tipo=tipo, titulo=titulo, mensaje=mensaje, estado="nueva", accion=None)

    def _ventilacion_auto(self, inc: dict, ahora: int) -> None:
        """Al confirmar, la nave apaga la ventilación horas_ventilacion_apagada h y avisa."""
        b, n, c = U.partes(inc["cama_id"])
        kn = (b - 1) * self.NN + n - 1
        v = self.vent.get(kn)
        if not v or v["estado"] != "encendida":
            return
        horas = self.cfg["robots"]["horas_ventilacion_apagada"]
        self._cambiar_ventilacion(kn, "apagada", ahora, f"auto: incidencia #{inc['incidencia_id']}")
        tok = v["token"]
        self._alerta(ahora, inc["cama_id"], inc["incidencia_id"], "ventilacion",
                     f"Ventilación apagada · B{b} · Nave {n}",
                     f"Se apagó la ventilación de B{b} · Nave {n} por {horas} h tras confirmar Botrytis en la "
                     f"Cama {c} (incidencia #{inc['incidencia_id']}), para frenar el transporte de esporas por el "
                     f"aire. Vigile la humedad de la nave.")

        def reencender(h, kn=kn, tok=tok):
            if self.vent[kn]["token"] == tok and self.vent[kn]["estado"] == "apagada":
                self._cambiar_ventilacion(kn, "encendida", h, "auto: fin de apagado")
        self._programar(ahora + horas, reencender)

    def _cambiar_ventilacion(self, kn: int, estado: str, hora: int, motivo: str) -> None:
        """Cambio de estado de la ventilación de una nave."""
        v = self.vent[kn]
        v["estado"] = estado
        v["token"] += 1
        self._fila("ventilacion", corrida_id=self.id, hora=int(hora), bloque=kn // self.NN + 1,
                   nave=kn % self.NN + 1, estado=estado, motivo=motivo)

    # ---- riesgo diario y celular ----
    def variables(self, cid: str, h: int) -> dict:
        """Variables del modelo de prueba con los datos medidos (no la verdad)."""
        cam = self.camas[self.idx[cid]]
        mp, Mo = self.M["modelo_prueba"], self.M["robots"]
        horas = self.lect_horas[cid]
        desde = bisect.bisect_left(horas, h - mp["ventana_h"] - Mo["horas_validez_lectura"])
        hasta = bisect.bisect_right(horas, h)
        lect = self.lect[cid][desde:hasta]
        confirmadas = [i["cama_id"] for i in self.inc.values() if i["estado"] in ESTADOS_CONFIRMADOS]
        dist = SIN_CONFIRMADA
        for x in confirmadas:
            b2, n2, c2 = U.partes(x)
            if b2 == cam["bloque"] and n2 == cam["nave"]:
                dist = min(dist, abs(c2 - cam["cama"]))
        v = calcular(lect, self.sensor[cam["bloque"]], h, ventana_h=mp["ventana_h"],
                     validez_h=Mo["horas_validez_lectura"], umbral_hr=self.cfg["mojado"]["umbral_hr"],
                     hr_rango=self.cfg["clima"]["hr_rango"], dist=dist, borde=cam["es_borde"])
        if self.lect[cid]:
            v["edad"] = h - self.lect[cid][-1][0]
        return v

    def calcular_riesgo(self, h: int) -> None:
        """Riesgo diario con el modelo de prueba; alerta riesgo_7d al pasar a 'alto' y cola de prioridad."""
        dia, mp, Me, R, gd = h // 24, self.M["modelo_prueba"], self.M["enfermedad"], self.cfg["riesgo"], self.M["guion_demo"]
        umbral = self.cfg["mojado"]["umbral_hr"]
        altos: dict[int, list] = {}
        for cam in self.camas:
            cid = cam["cama_id"]
            v = self.variables(cid, h)
            fT = 0.0 if v["t_mean"] is None else math.exp(-(((v["t_mean"] - Me["T_opt"]) / Me["T_ancho"]) ** 2))
            reglas = min(1.0, max(0.0, fT * min(1.0, v["wet72"] / mp["umbral_mojado_reglas_h"])
                                  * (1 + (mp["bonus_vecina"] if v["dist"] <= 1 else 0))))
            cerc = math.exp(-v["dist"] / 2) if v["dist"] < SIN_CONFIRMADA else 0.0
            z = (mp["a0"] + mp["a_mojado"] * v["wet72"] + mp["a_temp"] * fT + mp["a_borde"] * v["borde"]
                 + mp["a_vecina"] * cerc + mp["a_delta"] * max(0.0, v["delta_hr"]) + self.rng.normal(0, mp["ruido"]))
            prob = 1 / (1 + math.exp(-z))
            if self._es_guion(cid) and dia == gd["dia_alerta"]:
                prob = max(prob, gd["prob_min"])
            prob = round(prob, 3)
            nivel = "alto" if prob >= R["umbral_alto"] else "medio" if prob >= R["umbral_medio"] else "bajo"
            self._fila("riesgo", corrida_id=self.id, dia=dia, cama_id=cid, enfermedad="botrytis",
                       riesgo_reglas=round(reglas, 3), prob_ia_7d=prob, nivel=nivel)
            if nivel == "alto":
                if self.ultimo_nivel.get(cid) != "alto":
                    corto = U.corto(cid)
                    self._alerta(h, cid, None, "riesgo_7d", f"Riesgo alto de Botrytis · {corto}",
                                 f"{corto}: alto riesgo de Botrytis en los próximos 7 días (prob. {prob:.2f}). "
                                 f"HR > {num(umbral)} % durante {v['wet72']} h.")
                altos.setdefault(cam["bloque"], []).append((cid, prob, self._es_guion(cid)))
            self.ultimo_nivel[cid] = nivel
        for d in self.robots:
            lista = sorted(altos.get(d["bloque"], []), key=lambda x: (-x[2], -x[1]))
            d["prioridades"] = [x[0] for x in lista]

    def sincronizar(self, h: int) -> int:
        """Pasa el celular: marca hora_recibida en lo pendiente y corre el modelo."""
        n = len(self.cola_pend)
        for row in self.cola_pend:
            row["hora_recibida"] = h
            if row.get("_escrita"):
                self.cola_upd.append(row["id"])
        self.cola_pend = []
        self.ultima_sync = h
        self.calcular_riesgo(h)
        return n

    # ---- escritura ----
    def escribir(self, con: sqlite3.Connection) -> None:
        """Vacía el búfer en la base (las incidencias cambiadas se reescriben)."""
        for t, cols in COLS.items():
            if t == "incidencias":
                continue
            filas = self.buf[t]
            if filas:
                con.executemany(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                                [tuple(r[c] for c in cols) for r in filas])
                if t == "cola_sync":
                    for r in filas:
                        r["_escrita"] = True
                self.buf[t] = []
        if self.inc_sucias:
            cols = COLS["incidencias"]
            con.executemany(f"INSERT OR REPLACE INTO incidencias ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                            [tuple(self.inc[i][c] for c in cols) for i in sorted(self.inc_sucias)])
            self.inc_sucias = set()
        if self.cola_upd:
            con.executemany("UPDATE cola_sync SET hora_recibida=? WHERE id=?",
                            [(self.ultima_sync, i) for i in self.cola_upd])
            self.cola_upd = []
        con.commit()

    def registrar_corrida(self, con: sqlite3.Connection) -> None:
        """Filas de corridas y camas (camas es compartida entre corridas)."""
        con.executemany("INSERT OR IGNORE INTO camas (cama_id, bloque, nave, cama, es_borde, tiene_ventilacion) "
                        "VALUES (?,?,?,?,?,?)",
                        [(c["cama_id"], c["bloque"], c["nave"], c["cama"], c["es_borde"], c["tiene_ventilacion"])
                         for c in self.camas])
        con.execute("INSERT INTO corridas (corrida_id, modo, escenario, semilla, config_json, inicio_sim) "
                    "VALUES (?,?,?,?,?,?)",
                    (self.id, self.c["modo"], self.c["escenario"], int(self.c["semilla"]),
                     json.dumps(self.cfg, ensure_ascii=False, default=str), self.cfg["sim"]["inicio"]))
        con.commit()


def _desplazar(W: np.ndarray, dk: int, d: int) -> np.ndarray:
    """W movida dk camas y d posiciones dentro de cada nave, con ceros en los bordes."""
    out = np.zeros_like(W)
    _, CN, P = W.shape
    ks, kd = (slice(0, CN - dk), slice(dk, CN)) if dk >= 0 else (slice(-dk, CN), slice(0, CN + dk))
    ps, pd = (slice(0, P - d), slice(d, P)) if d >= 0 else (slice(-d, P), slice(0, P + d))
    out[:, kd, pd] = W[:, ks, ps]
    return out


# ── comandos ─────────────────────────────────────────────────────────────────
def preparar(con: sqlite3.Connection, corrida: dict, cfg: dict) -> FuenteLocal:
    """Borra la corrida en la base y crea su fuente."""
    borrar_corrida(con, corrida["corrida_id"])
    src = FuenteLocal(corrida, cfg, ids_libres(con))
    src.registrar_corrida(con)
    return src


def correr_completa(con: sqlite3.Connection, corrida: dict, cfg: dict) -> FuenteLocal:
    """Simula la temporada entera y la escribe."""
    src = preparar(con, corrida, cfg)
    while src.step():
        if src.hora % 24 == 0:
            src.escribir(con)
    src.escribir(con)
    return src


def correr_vivo(con: sqlite3.Connection, corrida: dict, cfg: dict) -> None:
    """Escribe una hora simulada por segundo (horas_por_segundo), tick a tick, desde hora_inicial."""
    M = cfg["dashboard"]["mock"]
    src = preparar(con, corrida, cfg)
    while src.hora < M["hora_inicial"] and src.step():
        pass
    src.escribir(con)
    tph = int(60 / cfg["robots"]["min_por_cama"])
    pausa = 1 / (M["horas_por_segundo"] * tph)
    print(f"{corrida['corrida_id']}: en vivo desde la hora {src.hora} (Ctrl+C para parar)")

    def entre_ticks():
        src.escribir(con)
        time.sleep(pausa)
    try:
        while src.step(entre_ticks):
            src.escribir(con)
    except KeyboardInterrupt:
        src.escribir(con)
        print(f"parado en la hora {src.hora}")


def main(argv=None) -> None:
    """CLI: python -m hub.mock [--vivo --corrida demo] [--ruta data/mock.db]."""
    ap = argparse.ArgumentParser(description="Datos de prueba que cumplen contrato/schema.sql")
    ap.add_argument("--vivo", action="store_true", help="una hora simulada por segundo")
    ap.add_argument("--corrida", default=None, help="demo | temporada-7 | celular-12")
    ap.add_argument("--ruta", type=Path, default=RUTA_MOCK)
    a = ap.parse_args(argv)
    cfg = cargar()
    corridas = cfg["dashboard"]["mock"]["corridas"]
    if a.corrida:
        corridas = [c for c in corridas if c["corrida_id"] == a.corrida]
        if not corridas:
            ap.error(f"corrida desconocida: {a.corrida}")
    con = abrir_base(a.ruta, cfg)
    try:
        if a.vivo:
            correr_vivo(con, corridas[0], cfg)
            return
        for c in corridas:
            t0 = time.time()
            src = correr_completa(con, c, cfg)
            print(f"{c['corrida_id']}: {src.hora} h simuladas en {time.time() - t0:.1f} s -> {a.ruta}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
