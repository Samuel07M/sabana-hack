"""Motor de la simulación: avanza hora a hora clima, enfermedad, sensores, riesgo, robots y alertas."""
import heapq
import json
from collections import defaultdict

import numpy as np

from prediccion import ia, reglas, variables
from sim import alertas, clima, enfermedad, geometria, sensores, valores
from sim.robots import Robot, inspeccionar
from sim.enfermedad import Enfermedad
from sim.valores import ESCENARIOS

ABIERTAS = ("confirmada", "en_tratamiento", "en_seguimiento")  # incidencias activas (la finca ya las conoce)
COLS_FOTO = ("incidencia_id", "corrida_id", "cama_id", "posicion", "origen", "estado", "hora_creada",  # = hub/db.py COLS_INC
             "hora_confirmada", "hora_cerrada", "confianza", "plantas_afectadas")
COLS_SEG = ("seguimiento_id", "incidencia_id", "corrida_id", "hora", "robot_id", "resultado", "plantas_afectadas", "nota")
FLAGS = {  # qué tiene cada escenario
    "actual": dict(modelo=False, patrulla=False, robots=False, humano=True, vent_auto=False, celular=False),
    "sensor_central": dict(modelo=True, patrulla=False, robots=True, humano=False, vent_auto=True, celular=False),
    "robots": dict(modelo=True, patrulla=True, robots=True, humano=False, vent_auto=True, celular=False),
    "robots_celular": dict(modelo=True, patrulla=True, robots=True, humano=False, vent_auto=True, celular=True),
    "robots_sin_vent": dict(modelo=True, patrulla=True, robots=True, humano=False, vent_auto=False, celular=False),
    "demo": dict(modelo=True, patrulla=True, robots=True, humano=False, vent_auto=True, celular=False),
}
assert set(FLAGS) == set(ESCENARIOS)


class Simulacion:
    """Una corrida: se avanza con `paso(hora)`; las filas nuevas quedan en `self.buf`."""

    def __init__(self, cfg: dict, escenario: str, semilla: int, corrida_id: str, modo: str = "temporada",
                 modelo="auto", recolectar: bool = False, ids_iniciales: dict | None = None):
        if escenario not in FLAGS:
            raise ValueError(f"escenario '{escenario}' fuera del contrato: {ESCENARIOS}")
        self.cfg, self.escenario, self.semilla, self.corrida_id, self.modo = cfg, escenario, semilla, corrida_id, modo
        self.flags = FLAGS[escenario]
        self.recolectar = recolectar
        self.n_horas = cfg["sim"]["dias"] * 24
        raiz = np.random.default_rng(semilla)
        r_clima, r_enf, self.r_sens, self.r_robot, r_cel, self.r_hum = raiz.spawn(6)
        self.geo = g = geometria.construir(cfg)
        self.T_base, self.HR_base = clima.generar(cfg, g, self.n_horas, r_clima)
        self.enf = Enfermedad(cfg, g, r_enf, self.n_horas)
        self.p_na = self.enf.p_na
        # verdad de la hora actual
        self.W = np.zeros(g.n_camas, dtype=int)
        self.secas = np.zeros(g.n_camas, dtype=int)
        self.T_h = self.HR_h = None
        # ventilación por nave global
        self.tiene_vent_nave = np.zeros(g.n_naves, dtype=bool)
        self.tiene_vent_nave[g.nave_global_c[g.tiene_vent_c]] = True
        self.vent_off = np.zeros(g.n_naves, dtype=bool)
        self.vent_hasta = np.zeros(g.n_naves)
        # lo que la finca mide / estima
        n_bloques = cfg["geometria"]["bloques"]
        self.cen_T, self.cen_HR = np.zeros((self.n_horas, n_bloques)), np.zeros((self.n_horas, n_bloques))
        self.est_T = np.zeros((self.n_horas, g.n_camas), dtype=np.float32)
        self.est_HR = np.zeros((self.n_horas, g.n_camas), dtype=np.float32)
        self.bias_T, self.bias_HR = np.zeros(g.n_camas), np.zeros(g.n_camas)
        self.ultima = np.full(g.n_camas, -10 ** 6)
        self.es_central = np.zeros(g.n_camas, dtype=bool)
        self.es_central[g.cama_central] = True
        # riesgo
        self.prob_actual = np.zeros(g.n_camas)
        self.nivel_actual = np.full(g.n_camas, "bajo", dtype=object)
        if modelo == "auto":
            modelo = ia.cargar("central" if escenario == "sensor_central" else "completo") if self.flags["modelo"] else None
        self.modelo = modelo
        self.dataset: list[tuple] = []
        # incidencias
        self.inc: dict[int, dict] = {}
        self.abierta: dict[int, int] = {}           # cama -> incidencia en curso (sospecha o activa)
        self.rev_pend: dict[int, float] = {}        # incidencia -> hora de la próxima revisita
        self.sucias: set[int] = set()
        self.ult_visita = np.full(g.n_camas, -np.inf)
        self.ids = defaultdict(int, ids_iniciales or {})
        self.cola: list[tuple] = []                 # eventos diferidos (hora, seq, nombre, args)
        self.buf: dict[str, list] = defaultdict(list)
        self.cola_sync_pend: list[list] = []
        self.pend_lect: list[tuple] = []
        d0, d1 = cfg["celular"]["ventana_hora"]
        n_dias = cfg["sim"]["dias"]
        self.pases = np.arange(n_dias) * 24 + r_cel.integers(d0, d1 + 1, n_dias)
        self.robots = [Robot(self, b) for b in range(1, n_bloques + 1)] if self.flags["robots"] else []
        self.h = 0

    # ── utilidades ──────────────────────────────────────────────────────────
    def _id(self, tabla: str) -> int:
        self.ids[tabla] += 1
        return self.ids[tabla]

    def vent_encendida_nave(self) -> np.ndarray:
        """True en las naves con ventilación controlable y encendida."""
        return self.tiene_vent_nave & ~self.vent_off

    def _sig_pase(self, hora: int) -> float:
        """Hora de la primera pasada del celular ≥ hora (inf si ya no habrá)."""
        k = np.searchsorted(self.pases, hora)
        return float(self.pases[k]) if k < len(self.pases) else np.inf

    def _programar(self, hora: float, nombre: str, *args) -> None:
        """Agenda un evento; si es inmediato (y ya estamos en la hora) lo ejecuta ahora."""
        if hora == np.inf:
            return
        if hora <= self.h:
            getattr(self, f"_ev_{nombre}")(self.h, *args)
        else:
            heapq.heappush(self.cola, (hora, self._id("seq"), nombre, args))

    def _hora_efecto(self, hora: int) -> float:
        """Cuándo el sistema se entera de algo ocurrido en `hora`: ya, o en la próxima pasada del celular."""
        return self._sig_pase(max(hora, self.h + 1)) if self.flags["celular"] else hora

    def fila_robot(self, robot, t: float, cama: int, estado: str) -> None:
        """Registra posición y estado del robot."""
        self.buf["robots"].append((self.corrida_id, round(float(t), 3), f"B{robot.bloque}",
                                   self.geo.camas[cama]["cama_id"], estado, round(float(robot.bateria), 3)))

    def _alerta(self, hora: int, cama: int, inc_id, tipo: str, texto: tuple[str, str], empeora: bool = False) -> None:
        self.buf["alertas"].append((self._id("alerta"), self.corrida_id, hora, self.geo.camas[cama]["cama_id"], inc_id,
                                    alertas.severidad(self.cfg, tipo, empeora), tipo, texto[0], texto[1]))

    def _cola_sync(self, origen: str, hora: int, tipo: str, payload: dict) -> None:
        """cola_sync solo sin red (NOTAS.md, decisión 7): el dato espera la pasada del celular, que llena hora_recibida."""
        if self.modo == "experimento" or not self.flags["celular"]:
            return                                   # con red local no hay cola; la validación no la necesita
        self.cola_sync_pend.append([self._id("cola"), self.corrida_id, origen, hora, None, tipo,
                                    json.dumps(payload, ensure_ascii=False)])

    def _tocar(self, inc: dict) -> None:
        """Marca la incidencia para reescribirla y, sin red, manda su foto a la cola (como hub/mock.py)."""
        self.sucias.add(inc["id"])
        if self.flags["celular"]:
            foto = dict(zip(COLS_FOTO, self._fila_inc(inc)))   # _fila_inc termina en verdad_infectada: queda fuera
            self._cola_sync(f"robot:B{self.geo.bloque_c[inc['cama']]}", self.h, "inspeccion", foto)

    def _estado(self, inc: dict, nuevo: str, **campos) -> None:
        """Cambia el estado de la incidencia validando la transición y marca la fila como modificada."""
        valores.validar_transicion(inc["estado"], nuevo)
        inc.update(estado=nuevo, **campos)
        self._tocar(inc)

    def _fila_inc(self, i: dict) -> tuple:
        return (i["id"], self.corrida_id, self.geo.camas[i["cama"]]["cama_id"], i["posicion"], i["origen"], i["estado"],
                i["hora_creada"], i["hora_confirmada"], i["hora_cerrada"], i["confianza"], i["plantas_afectadas"],
                i["verdad_infectada"])

    def filas_incidencias(self) -> list[tuple]:
        """Filas de las incidencias modificadas desde la última llamada."""
        filas = [self._fila_inc(self.inc[k]) for k in sorted(self.sucias)]
        self.sucias.clear()
        return filas

    # ── paso horario ────────────────────────────────────────────────────────
    def paso(self, h: int) -> None:
        """Avanza la simulación una hora."""
        cfg, g = self.cfg, self.geo
        self.h = h
        self._vent_restaurar(h)
        while self.cola and self.cola[0][0] <= h:
            _, _, nombre, args = heapq.heappop(self.cola)
            getattr(self, f"_ev_{nombre}")(h, *args)
        if self.flags["celular"] and h in self.pases:  # después de los eventos: lo que se supo en esta pasada viaja en ella
            self._pasada(h)
        vent_c = self.vent_encendida_nave()[g.nave_global_c].astype(float)
        self.T_h = self.T_base[h].astype(float)
        self.HR_h = clima.hr_con_ventilacion(cfg, self.HR_base[h].astype(float), vent_c)
        mojada = (self.HR_h >= cfg["mojado"]["umbral_hr"]) | clima.es_hora_de_riego(cfg, h)
        self.W, self.secas = clima.actualizar_mojado(self.W, self.secas, mojada, cfg["mojado"]["pausa_seca_reinicio_h"])
        f = enfermedad.f_ambiental(self.T_h, self.W, self.p_na, cfg["enfermedad"]["T_sin_infeccion"]) * mojada
        self.enf.paso(h, f, vent_c)
        self._sensor_fijo(h)
        if self.flags["modelo"] and h % 24 == cfg["riesgo"]["hora_calculo"]:
            self._riesgo(h)
        if self.flags["humano"] and h % 24 == cfg["actual"]["hora_ronda"]:
            self._ronda_humana(h)
        for robot in self.robots:
            robot.trabajar(self, h)

    def _sensor_fijo(self, h: int) -> None:
        """Lee el sensor central de cada bloque y actualiza lo que la finca estima de cada cama."""
        g = self.geo
        cen = g.cama_central
        Tm, HRm = sensores.medir(self.cfg, self.T_h[cen], self.HR_h[cen], self.r_sens)
        self.cen_T[h], self.cen_HR[h] = Tm, HRm
        lo, hi = self.cfg["clima"]["hr_rango"]
        self.est_T[h] = Tm[g.bloque_c - 1] + self.bias_T
        self.est_HR[h] = np.clip(HRm[g.bloque_c - 1] + self.bias_HR, lo, hi)
        self.ultima[cen] = h
        self.buf["lecturas"].extend(sensores.filas_sensor_central(self.corrida_id, h, g, Tm, HRm))

    def _vent_restaurar(self, h: int) -> None:
        """Reenciende las naves cuyo apagado de 48 h terminó."""
        for n in np.nonzero(self.vent_off & (self.vent_hasta <= h))[0]:
            self.vent_off[n] = False
            b, nv = divmod(int(n), self.cfg["geometria"]["naves_por_bloque"])
            self.buf["ventilacion"].append((self.corrida_id, h, b + 1, nv + 1, "encendida", "auto: fin de apagado"))

    # ── riesgo ──────────────────────────────────────────────────────────────
    def _riesgo(self, h: int) -> None:
        """Calcula variables, riesgo de reglas, prob. de IA y nivel; escribe `riesgo` y alertas riesgo_7d."""
        g, cfg = self.geo, self.cfg
        confirmadas = np.zeros(g.n_camas, dtype=bool)
        for i in self.inc.values():
            if i["estado"] in ABIERTAS:
                confirmadas[i["cama"]] = True
        df = variables.construir(cfg, g, h, self.est_T, self.est_HR, self.ultima, confirmadas,
                                 self.vent_encendida_nave())
        reg = reglas.riesgo_reglas(df, cfg)
        prob = self.modelo.predecir(df) if self.modelo is not None else None
        base = reg if prob is None else prob
        nivel = reglas.nivel_de(base, cfg)
        dia = h // 24
        for c in range(g.n_camas):
            self.buf["riesgo"].append((self.corrida_id, dia, g.camas[c]["cama_id"], "botrytis", round(float(reg[c]), 4),
                                       None if prob is None else round(float(prob[c]), 4), str(nivel[c])))
        nuevos = np.nonzero((nivel == "alto") & (self.nivel_actual != "alto"))[0]
        for c in nuevos:
            w = float(df["max_mojado_continuo_24h"].iloc[c])
            nb = reglas.nivel_broome(float(df["indice_broome_24h"].iloc[c]), cfg)
            self._alerta(h, int(c), None, "riesgo_7d", alertas.riesgo_7d(g.camas[c], float(base[c]), w, nb, cfg))
        self.prob_actual, self.nivel_actual = np.asarray(base, dtype=float), nivel.astype(object)
        if self.recolectar:
            self.dataset.append((h, df, reg, prob))

    def prioridad(self, camas: np.ndarray, t: float):
        """Cama del robot con nivel alto, sin visita reciente y sin incidencia abierta; la de mayor prob."""
        d = self.cfg["robots"]
        libre = np.array([c not in self.abierta for c in camas])
        sel = (self.nivel_actual[camas] == "alto") & (t - self.ult_visita[camas] >= d["horas_sin_visita_prioridad"]) & libre
        if not sel.any():
            return None
        cand = camas[sel]
        return int(cand[np.argmax(self.prob_actual[cand])])

    def revisita_vencida(self, bloque: int, t: float):
        """Incidencia de este bloque con revisita vencida (la más atrasada) o None."""
        vencidas = [(due, k) for k, due in self.rev_pend.items()
                    if due <= t and self.geo.bloque_c[self.inc[k]["cama"]] == bloque]
        return min(vencidas)[1] if vencidas else None

    # ── visitas del robot ────────────────────────────────────────────────────
    def visita(self, robot, cama: int, motivo: str, t: float, dt: float) -> None:
        """El robot llega a una cama: mide, inspecciona y, según el caso, abre una sospecha o registra la revisita."""
        h = int(t)
        g, cfg = self.geo, self.cfg
        self.fila_robot(robot, t, cama, "patrulla" if motivo == "patrulla" else "prioridad")
        self.ult_visita[cama] = t
        Tm, HRm = sensores.medir(cfg, self.T_h[cama], self.HR_h[cama], self.r_sens)
        Tm, HRm = float(Tm), float(HRm)
        cid = g.camas[cama]["cama_id"]
        self.buf["lecturas"].append((self.corrida_id, h, cid, round(Tm, 2), round(HRm, 2), f"robot:B{robot.bloque}"))
        self._lectura_robot(robot, h, cama, Tm, HRm)
        inc_id = self.abierta.get(cama)
        if motivo == "revisita":
            pos, _, _ = inspeccionar(self.enf.estado_cama(cama), cfg["robots"], self.r_robot)
            self.fila_robot(robot, t + dt / 2, cama, "inspeccionando")
            self.rev_pend.pop(inc_id, None)       # el resultado reprograma la próxima revisita
            self._programar(self._hora_efecto(h + 1) if self.flags["celular"] else h, "revisita",
                            inc_id, len(pos), t, robot.id)
        elif inc_id is None:
            pos, reales, fps = inspeccionar(self.enf.estado_cama(cama), cfg["robots"], self.r_robot)
            if len(pos):
                self.fila_robot(robot, t + dt / 2, cama, "inspeccionando")
                self._sospecha(robot, cama, int(pos[0]), len(pos), reales, fps, motivo, h)

    def _lectura_robot(self, robot, h: int, cama: int, Tm: float, HRm: float) -> None:
        """La lectura del robot corrige el sesgo de la cama: ya (red local) o en la próxima pasada (celular)."""
        origen = f"robot:B{robot.bloque}"
        payload = {"corrida_id": self.corrida_id, "hora": h, "cama_id": self.geo.camas[cama]["cama_id"],
                   "temp_c": round(Tm, 2), "hr": round(HRm, 2), "fuente": origen}
        self._cola_sync(origen, h, "lectura", payload)
        if self.flags["celular"]:
            self.pend_lect.append((h, cama, Tm, HRm))
        else:
            self._aplicar_lectura(h, cama, Tm, HRm)

    def _aplicar_lectura(self, h: int, cama: int, Tm: float, HRm: float) -> None:
        """Sesgo de la cama = lectura propia − sensor central del bloque en esa hora."""
        if self.es_central[cama]:
            return
        b = self.geo.bloque_c[cama] - 1
        self.bias_T[cama] = Tm - self.cen_T[h, b]
        self.bias_HR[cama] = HRm - self.cen_HR[h, b]
        self.ultima[cama] = max(self.ultima[cama], h)

    def _pasada(self, h: int) -> None:
        """Un trabajador pasa con el celular: descarga lo guardado por los robots y lo sincroniza."""
        for lectura in sorted(self.pend_lect):
            self._aplicar_lectura(*lectura)
        self.pend_lect.clear()
        for fila in self.cola_sync_pend:
            fila[4] = h
            self.buf["cola_sync"].append(tuple(fila))
        self.cola_sync_pend.clear()

    # ── incidencias ─────────────────────────────────────────────────────────
    def _nueva_inc(self, cama: int, posicion: int, origen: str, hora: int, estado: str) -> dict:
        inc = dict(id=self._id("inc"), cama=cama, posicion=posicion, origen=origen, estado=estado, hora_creada=hora,
                   hora_confirmada=None, hora_cerrada=None, confianza=None, plantas_afectadas=None,
                   verdad_infectada=None, limpias=0)
        self.inc[inc["id"]] = inc
        self.abierta[cama] = inc["id"]
        self._tocar(inc)
        return inc

    def _sospecha(self, robot, cama: int, posicion: int, n_det: int, reales: int, fps: int, motivo: str, h: int) -> None:
        """Crea la incidencia en `sospecha`; su verificación llega `horas_verificacion` después."""
        inc = self._nueva_inc(cama, posicion, "prediccion" if motivo == "prioridad" else "patrulla", h, "sospecha")
        due = h + self.cfg["robots"]["horas_verificacion"]
        self._programar(self._hora_efecto(due), "verificar", inc["id"], n_det, reales, fps)

    def _ev_verificar(self, h: int, inc_id: int, n_det: int, reales: int, fps: int) -> None:
        """Segunda mirada de la cámara: confirma (positivo) o descarta la sospecha."""
        d = self.cfg["robots"]
        inc, g = self.inc[inc_id], self.geo
        cama = g.camas[inc["cama"]]
        positivo = reales > 0 or (fps > 0 and self.r_robot.random() < 1.0 - d["especificidad"] ** fps)
        inc["verdad_infectada"] = int(reales > 0)
        if not positivo:
            self._estado(inc, "descartada", hora_cerrada=h)
            self.abierta.pop(inc["cama"], None)
            self._alerta(h, inc["cama"], inc_id, "descartada", alertas.descartada(cama, inc["posicion"]))
            return
        self._estado(inc, "confirmada", hora_confirmada=h, plantas_afectadas=n_det,
                     confianza=round(1.0 - (1.0 - d["especificidad"]) ** n_det, 3))
        self._alerta(h, inc["cama"], inc_id, "confirmacion",
                     alertas.confirmacion(cama, inc["posicion"], n_det, inc["confianza"]))
        self._apagar_ventilacion(h, inc)
        self._programar(h + d["horas_hasta_tratamiento"], "tratar", inc_id)

    def _apagar_ventilacion(self, h: int, inc: dict) -> None:
        """Apaga automáticamente la ventilación de la nave 48 h (si la tiene) y avisa con una alerta."""
        g = self.geo
        if not (self.flags["vent_auto"] and g.tiene_vent_c[inc["cama"]]):
            return
        n = int(g.nave_global_c[inc["cama"]])
        horas = self.cfg["robots"]["horas_ventilacion_apagada"]
        if not self.vent_off[n]:
            self.vent_off[n] = True
            cama = g.camas[inc["cama"]]
            self.buf["ventilacion"].append((self.corrida_id, h, cama["bloque"], cama["nave"], "apagada",
                                            f"auto: incidencia #{inc['id']}"))
        self.vent_hasta[n] = max(self.vent_hasta[n], h + horas)
        self._alerta(h, inc["cama"], inc["id"], "ventilacion", alertas.ventilacion(g.camas[inc["cama"]], horas))

    def _ev_tratar(self, h: int, inc_id: int) -> None:
        """El personal trata la cama: la incidencia pasa a `en_tratamiento` y se agenda la revisita."""
        inc = self.inc[inc_id]
        self.enf.tratar(inc["cama"], h, self.r_robot)
        self._estado(inc, "en_tratamiento")
        if self.flags["robots"]:
            self.rev_pend[inc_id] = h + self.cfg["robots"]["dias_revisita"] * 24
        else:                                     # sin robot nadie hace seguimiento: se cierra y la cama vuelve a la ronda manual
            self._estado(inc, "en_seguimiento")
            self._estado(inc, "cerrada", hora_cerrada=h)
            self.abierta.pop(inc["cama"], None)

    def _ev_revisita(self, h: int, inc_id: int, n: int, t_visita: float, robot_id: str) -> None:
        """Resultado de una revisita: seguimiento, alerta y nuevo estado de la incidencia."""
        d = self.cfg["robots"]
        inc = self.inc[inc_id]
        previo = inc["plantas_afectadas"] or 0
        resultado = "limpia" if n == 0 else "empeora" if n > previo else "mejora" if n < previo else "igual"
        seg = (self._id("seg"), inc_id, self.corrida_id, int(t_visita), robot_id, resultado, n,
               f"Revisita: {n} plantas visibles (antes {previo})")
        self.buf["seguimientos"].append(seg)
        self._cola_sync(f"robot:{robot_id}", int(t_visita), "seguimiento", dict(zip(COLS_SEG, seg)))
        cama = self.geo.camas[inc["cama"]]
        self._alerta(h, inc["cama"], inc_id, "seguimiento", alertas.seguimiento(cama, resultado, n),
                     empeora=resultado == "empeora")
        inc["plantas_afectadas"] = n
        if inc["estado"] == "en_tratamiento":
            self._estado(inc, "en_seguimiento")
        inc["limpias"] = inc["limpias"] + 1 if resultado == "limpia" else 0
        if inc["limpias"] >= d["limpias_para_cerrar"]:
            self._estado(inc, "cerrada", hora_cerrada=h)
            self.abierta.pop(inc["cama"], None)
            self.rev_pend.pop(inc_id, None)
        elif resultado == "empeora":
            self._estado(inc, "confirmada")
            self.rev_pend.pop(inc_id, None)
            self._programar(h + d["horas_hasta_tratamiento"], "tratar", inc_id)
        else:
            self.rev_pend[inc_id] = max(h, t_visita) + d["dias_revisita"] * 24
        self._tocar(inc)

    # ── escenario `actual` ──────────────────────────────────────────────────
    def _ronda_humana(self, h: int) -> None:
        """Revisión manual: cada cama se recorre una vez cada `dias_ronda`; solo ve síntomas."""
        a, g = self.cfg["actual"], self.geo
        dia = h // 24
        sint = (self.enf.estado == enfermedad.SINTOMAS).reshape(g.n_camas, g.plantas_por_cama).sum(axis=1)
        toca = (np.arange(g.n_camas) % a["dias_ronda"]) == (dia % a["dias_ronda"])
        ve = self.r_hum.random(g.n_camas) < a["p_humano"]
        for c in np.nonzero(toca & ve & (sint > 0) & np.array([k not in self.abierta for k in range(g.n_camas)]))[0]:
            c = int(c)
            pos = int(np.nonzero(self.enf.estado_cama(c) == enfermedad.SINTOMAS)[0][0]) + 1
            inc = self._nueva_inc(c, pos, "patrulla", h, "confirmada")
            inc.update(hora_confirmada=h, plantas_afectadas=int(sint[c]), verdad_infectada=1,
                       confianza=self.cfg["robots"]["especificidad"])
            self._alerta(h, c, inc["id"], "confirmacion",
                         alertas.confirmacion(g.camas[c], pos, inc["plantas_afectadas"], inc["confianza"]))
            self._programar(h + self.cfg["robots"]["horas_hasta_tratamiento"], "tratar", inc["id"])

    # ── cierre ──────────────────────────────────────────────────────────────
    def finalizar(self) -> None:
        """Al terminar, lo que el celular no alcanzó a descargar queda en cola_sync con hora_recibida NULL."""
        for fila in self.cola_sync_pend:
            self.buf["cola_sync"].append(tuple(fila))
        self.cola_sync_pend.clear()

    def cambios(self) -> np.ndarray:
        """Eventos de verdad (hora, planta, estado_nuevo) como arreglo (n, 3)."""
        return np.array(self.enf.cambios, dtype=np.int64).reshape(-1, 3)
