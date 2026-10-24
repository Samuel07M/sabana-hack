"""Pruebas del simulador: geometría, clima, enfermedad, sensores, drones y estados."""
import copy
import sqlite3

import numpy as np
import pytest

from sim import calibracion, clima, enfermedad, escritor, geometria, valores
from sim.config import cargar_config
from sim.enfermedad import Enfermedad
from sim.motor import Simulacion


def cfg_chica(**cambios) -> dict:
    """Finca de juguete: 1 bloque, 2 naves de 4 camas, 10 plantas por cama, 14 días, un foco latente."""
    cfg = cargar_config()
    cfg["geometria"].update(bloques=1, naves_por_bloque=2, camas_por_nave=4, plantas_por_cama=10)
    cfg["sim"]["dias"] = 14
    cfg["enfermedad"]["focos_forzados"] = [{"cama_id": "B1-N1-C02", "posicion": 5, "hora": 0}]
    cfg["drones"].update(sens_latente=1.0, sens_sintomas=1.0, tasa_falsa_deteccion_planta=0.0, especificidad=1.0)
    cfg["enfermedad"]["eficacia_tratamiento"] = 1.0
    for seccion, valores_ in cambios.items():
        cfg[seccion].update(valores_)
    return cfg


def correr(cfg, escenario="drones", semilla=1, modelo=None) -> Simulacion:
    sim = Simulacion(cfg, escenario, semilla, "t", modelo=modelo)
    for h in range(sim.n_horas):
        sim.paso(h)
    return sim


# ── geometría ───────────────────────────────────────────────────────────────
def test_vecindad_simetrica_y_pesos_del_pdf():
    geo = geometria.construir(cargar_config())
    assert geo.n_plantas == 11520
    V = geo.V
    assert abs(V - V.T).max() == 0
    i = 20
    assert V[i, i + 1] == pytest.approx(0.78, abs=0.01)       # misma cama ±1
    assert V[i, i + 40] == pytest.approx(0.41, abs=0.01)      # cama contigua
    assert V[i, i + 80] == pytest.approx(0.17, abs=0.01)      # dos camas
    assert V[i, 12 * 40 + i] == 0                              # otra nave: sin vecindad


def test_es_borde_planta_incluye_esquinas():
    geo = geometria.construir(cargar_config())
    assert geo.es_borde_planta[0] and geo.es_borde_planta[39] and not geo.es_borde_planta[20 + 40]


def test_calibracion_beta_vec():
    cfg = cargar_config()
    assert calibracion.fraccion_cama_contigua(cfg, cfg["enfermedad"]["beta_vec"]) == pytest.approx(
        cfg["enfermedad"]["meta_cama_adyacente_7d"], abs=0.002)


# ── clima ───────────────────────────────────────────────────────────────────
def test_clima_reproducible_y_en_rango():
    cfg = cfg_chica()
    geo = geometria.construir(cfg)
    T1, HR1 = clima.generar(cfg, geo, 100, np.random.default_rng(3))
    T2, HR2 = clima.generar(cfg, geo, 100, np.random.default_rng(3))
    assert (T1 == T2).all() and (HR1 == HR2).all()
    lo, hi = cfg["clima"]["hr_rango"]
    for on in (0.0, 1.0):
        hr = clima.hr_con_ventilacion(cfg, HR1[10].astype(float), on)
        assert hr.min() >= lo and hr.max() <= hi


def test_ventilacion_encendida_baja_la_hr():
    cfg = cfg_chica()
    hr = np.full(5, 80.0)
    assert (clima.hr_con_ventilacion(cfg, hr, 1.0) < clima.hr_con_ventilacion(cfg, hr, 0.0)).all()


def test_mojado_se_reinicia_tras_mas_de_4_horas_secas():
    W, s = np.zeros(1, int), np.zeros(1, int)
    for mojada in [1] * 5 + [0] * 4 + [1]:
        W, s = clima.actualizar_mojado(W, s, np.array([bool(mojada)]), 4)
    assert W[0] == 6                                            # 4 h secas no reinician
    for mojada in [0] * 5:
        W, s = clima.actualizar_mojado(W, s, np.array([bool(mojada)]), 4)
    assert W[0] == 0                                            # la quinta hora seca sí


def test_punto_de_rocio_del_pdf():
    td = clima.punto_rocio(cargar_config(), np.array([15.0]), np.array([95.0]))
    assert td[0] == pytest.approx(14.2, abs=0.1)


# ── enfermedad ──────────────────────────────────────────────────────────────
def test_f_ambiental_con_los_numeros_del_pdf():
    cfg = cargar_config()
    p, tmax = cfg["enfermedad"]["nair_allen"]["baya"], cfg["enfermedad"]["T_sin_infeccion"]
    f = lambda W, T: float(enfermedad.f_ambiental(np.array(T), np.array(W), p, tmax))
    assert f(24, 21) == pytest.approx(0.949, abs=0.002)
    assert f(24, 8) == pytest.approx(0.047, abs=0.002)
    for W, T in ((24, 12), (13, 16), (10, 20)):                 # tabla de arándano de UMaine
        assert 0.34 <= f(W, T) <= 0.40
    assert f(24, 41) == 0.0


def _enf(cfg, semilla=1):
    geo = geometria.construir(cfg)
    return geo, Enfermedad(cfg, geo, np.random.default_rng(semilla), 100)


def test_sin_focos_ni_beta0_nadie_se_infecta():
    cfg = cfg_chica()
    cfg["enfermedad"].update(focos_forzados=[{"cama_id": "B1-N1-C02", "posicion": 5, "hora": 10 ** 6}], beta_0=0.0)
    geo, enf = _enf(cfg)
    for h in range(100):
        enf.paso(h, np.ones(geo.n_camas), np.ones(geo.n_camas))
    assert enf.cambios == [] and enf.estado.sum() == 0


def test_reproducible_y_transiciones_validas():
    cfg = cfg_chica()
    cfg["enfermedad"].update(beta_vec=0.05, beta_0=1e-3, latencia_dias=[1, 1], sintomas_a_perdida_dias=[1, 1])
    resultados = []
    for _ in range(2):
        geo, enf = _enf(cfg)
        for h in range(100):
            enf.paso(h, np.ones(geo.n_camas), np.ones(geo.n_camas))
        resultados.append(list(enf.cambios))
    assert resultados[0] == resultados[1] and len(resultados[0]) > 1
    validas = {None: {1}, 1: {2, 3}, 2: {3, 4}, 3: {0}, 0: {1}, 4: set()}
    ultimo = {}
    for _, planta, nuevo in resultados[0]:
        assert nuevo in validas[ultimo.get(planta)]
        ultimo[planta] = nuevo


def test_tratada_no_contagia_y_vuelve_a_sana():
    cfg = cfg_chica()
    geo, enf = _enf(cfg)
    enf.paso(0, np.zeros(geo.n_camas), np.zeros(geo.n_camas))          # siembra el foco
    cama = int(geo.cama_de_planta[np.nonzero(enf.estado == enfermedad.LATENTE)[0][0]])
    assert enf.pv.max() > 0
    assert enf.tratar(cama, 0, np.random.default_rng(0)) == 1
    assert enf.pv.max() == pytest.approx(0, abs=1e-12) and enf.peso.sum() == 0
    enf.paso(cfg["enfermedad"]["dias_proteccion"] * 24 + 1, np.zeros(geo.n_camas), np.zeros(geo.n_camas))
    assert (enf.estado == enfermedad.SANA).all()


# ── sensores y escritura ────────────────────────────────────────────────────
def test_sensor_central_una_lectura_por_bloque_por_hora():
    sim = correr(cfg_chica(sim={"dias": 2}), "sensor_central")
    filas = sim.buf["lecturas"]
    assert len(filas) == 48 * sim.cfg["geometria"]["bloques"]
    assert {f[5] for f in filas} == {"sensor_fijo"}
    assert {f[2] for f in filas} == {sim.geo.camas[c]["cama_id"] for c in sim.geo.cama_central}


def test_volcar_escribe_todas_las_tablas(tmp_path):
    cfg = cfg_chica(sim={"dias": 6})
    con = escritor.crear_base(tmp_path / "t.db", cfg)
    sim = Simulacion(cfg, "drones", 1, "t", modelo=None)
    escritor.insertar_corrida(con, "t", "temporada", "drones", 1, cfg)
    for h in range(sim.n_horas):
        sim.paso(h)
    escritor.volcar(con, sim)
    filas = escritor.contar_filas(con)
    assert filas["lecturas"] > 0 and filas["drones"] > 0 and filas["riesgo"] > 0 and filas["incidencias"] > 0
    assert not any(sim.buf.values()) or all(len(v) == 0 for v in sim.buf.values())
    con.close()


# ── drones e incidencias ────────────────────────────────────────────────────
def test_prioridad_interrumpe_la_patrulla():
    sim = Simulacion(cfg_chica(), "drones", 1, "t", modelo=None)
    dron = sim.drones[0]
    assert dron._elegir(sim) == (int(dron.ruta[0]), "patrulla")
    sim.nivel_actual[6] = "alto"
    sim.prob_actual[6] = 0.9
    assert dron._elegir(sim) == (6, "prioridad")
    sim.ult_visita[6] = 0.0                                              # visitada hace menos de 24 h
    assert dron._elegir(sim)[1] == "patrulla"


def test_confirmacion_genera_alerta_critica_y_apaga_la_ventilacion():
    sim = correr(cfg_chica())
    conf = [a for a in sim.buf["alertas"] if a[6] == "confirmacion"]
    assert conf and all(a[5] == "critica" for a in conf)
    vent = [v for v in sim.buf["ventilacion"] if v[4] == "apagada"]
    assert vent and vent[0][5].startswith("auto: incidencia #")
    assert any(a[6] == "ventilacion" for a in sim.buf["alertas"])
    assert any(v[4] == "encendida" and v[5] == "auto: fin de apagado" for v in sim.buf["ventilacion"])


def test_sin_ventilacion_en_la_nave_no_se_apaga_nada():
    sim = correr(cfg_chica(geometria={"tiene_ventilacion": False}))
    assert any(a[6] == "confirmacion" for a in sim.buf["alertas"])
    assert not sim.buf["ventilacion"] and not any(a[6] == "ventilacion" for a in sim.buf["alertas"])


def test_drones_sin_vent_no_apaga_pero_confirma():
    sim = correr(cfg_chica(), "drones_sin_vent")
    assert any(a[6] == "confirmacion" for a in sim.buf["alertas"])
    assert not sim.buf["ventilacion"]


def test_dos_limpias_seguidas_cierran_la_incidencia():
    sim = correr(cfg_chica(sim={"dias": 30}))
    cerradas = [i for i in sim.inc.values() if i["estado"] == "cerrada"]
    assert cerradas
    i = cerradas[0]
    seg = [s for s in sim.buf["seguimientos"] if s[1] == i["id"]]
    assert [s[5] for s in seg[-2:]] == ["limpia", "limpia"]
    assert i["hora_cerrada"] is not None and i["verdad_infectada"] == 1


def test_sensor_central_no_patrulla_pero_sigue_incidencias():
    sim = correr(cfg_chica(), "sensor_central")
    assert all(f[5] == "sensor_fijo" or f[5].startswith("dron") for f in sim.buf["lecturas"])
    assert sim.flags["patrulla"] is False


def test_escenario_actual_confirma_solo_sintomas_y_sin_modelo():
    cfg = cfg_chica(actual={"p_humano": 1.0, "dias_ronda": 1}, sim={"dias": 30})
    cfg["enfermedad"]["latencia_dias"] = [2, 2]
    sim = correr(cfg, "actual")
    assert not sim.buf["riesgo"] and not sim.buf["drones"]
    assert sim.inc and all(i["origen"] == "patrulla" for i in sim.inc.values())


def test_celular_deja_hora_recibida_y_retrasa_la_confirmacion():
    cfg = cfg_chica()
    lan, cel = correr(cfg, "drones"), correr(cfg, "drones_celular")
    assert cel.buf["cola_sync"] and all(f[4] is None or f[4] >= f[3] for f in cel.buf["cola_sync"])
    hora_lan = min(a[2] for a in lan.buf["alertas"] if a[6] == "confirmacion")
    hora_cel = min(a[2] for a in cel.buf["alertas"] if a[6] == "confirmacion")
    assert hora_cel >= hora_lan
    assert int(hora_cel) in set(cel.pases.tolist())


def test_misma_semilla_misma_corrida():
    a, b = correr(cfg_chica()), correr(cfg_chica())
    assert a.buf["alertas"] == b.buf["alertas"] and a.cambios().tolist() == b.cambios().tolist()


def test_escenarios_comparten_los_sorteos_de_infeccion():
    cfg = cfg_chica()
    a, b = Simulacion(cfg, "drones", 4, "a", modelo=None), Simulacion(cfg, "actual", 4, "b", modelo=None)
    assert (a.enf.U == b.enf.U).all() and (a.T_base == b.T_base).all()


def test_incidencias_pasan_por_todos_los_estados():
    cfg = cfg_chica(sim={"dias": 40})
    cfg["drones"]["tasa_falsa_deteccion_planta"] = 0.01          # algunas sospechas serán falsas → descartada
    sim = Simulacion(cfg, "drones", 1, "t", modelo=None)
    vistos = set()
    for h in range(sim.n_horas):
        sim.paso(h)
        vistos |= {f[5] for f in sim.filas_incidencias()}      # cada hora, el estado de las filas modificadas
    assert vistos == set(valores.ESTADOS_INCIDENCIA)


# ── máquina de estados ──────────────────────────────────────────────────────
def test_transiciones_invalidas_lanzan_error():
    valores.validar_transicion("sospecha", "confirmada")
    valores.validar_transicion("en_seguimiento", "confirmada")
    for desde, hacia in (("confirmada", "cerrada"), ("descartada", "confirmada"), ("sospecha", "en_tratamiento")):
        with pytest.raises(ValueError, match="transición"):
            valores.validar_transicion(desde, hacia)


def test_escenario_invalido_en_el_motor():
    with pytest.raises(ValueError, match="escenario"):
        Simulacion(cfg_chica(), "inventado", 1, "t")


def test_incidencias_en_la_base_solo_usan_valores_del_contrato(tmp_path):
    cfg = cfg_chica(sim={"dias": 30})
    con = escritor.crear_base(tmp_path / "t.db", cfg)
    escritor.insertar_corrida(con, "t", "temporada", "drones", 1, cfg)
    sim = correr(cfg)
    escritor.volcar(con, sim)
    estados = {r[0] for r in con.execute("SELECT DISTINCT estado FROM incidencias")}
    assert estados <= set(valores.ESTADOS_INCIDENCIA)
    assert {r[0] for r in con.execute("SELECT DISTINCT tipo FROM alertas")} <= set(valores.TIPOS_ALERTA)
    assert {r[0] for r in con.execute("SELECT DISTINCT severidad FROM alertas")} <= set(valores.SEVERIDADES)
    assert {r[0] for r in con.execute("SELECT DISTINCT estado FROM drones")} <= set(valores.ESTADOS_DRON)
    assert {r[0] for r in con.execute("SELECT DISTINCT resultado FROM seguimientos")} <= set(valores.RESULTADOS_SEGUIMIENTO)
    con.close()
