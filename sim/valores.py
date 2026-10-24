"""Valores permitidos del contrato (contrato/schema.sql). Una sola definición."""

MODOS = ("vivo", "temporada", "experimento")
ESCENARIOS = ("actual", "sensor_central", "drones", "drones_celular", "drones_sin_vent", "demo")
ENFERMEDADES = ("botrytis",)
NIVELES_RIESGO = ("bajo", "medio", "alto")
ORIGENES_INCIDENCIA = ("prediccion", "patrulla")
ESTADOS_INCIDENCIA = ("sospecha", "confirmada", "en_tratamiento", "en_seguimiento", "cerrada", "descartada")
TRANSICIONES = {  # máquina de estados de una incidencia (guía, sección 5.2)
    "sospecha": ("confirmada", "descartada"),
    "confirmada": ("en_tratamiento",),
    "en_tratamiento": ("en_seguimiento",),
    "en_seguimiento": ("confirmada", "cerrada"),
    "cerrada": (),
    "descartada": (),
}


def validar_transicion(desde: str, hacia: str) -> None:
    """ValueError si `desde → hacia` no es una transición válida."""
    if hacia not in TRANSICIONES.get(desde, ()):
        raise ValueError(f"transición de incidencia inválida: {desde} → {hacia}")


RESULTADOS_SEGUIMIENTO = ("empeora", "igual", "mejora", "limpia")
SEVERIDADES = ("info", "advertencia", "critica")
TIPOS_ALERTA = ("riesgo_7d", "confirmacion", "seguimiento", "ventilacion", "descartada")
ESTADOS_ALERTA = ("nueva", "vista", "resuelta")
ESTADOS_DRON = ("patrulla", "prioridad", "inspeccionando", "carga")
ESTADOS_VENTILACION = ("encendida", "apagada")
FUENTES_LECTURA = ("sensor_fijo", "dron:B{n}")  # 'dron:B{n}' con n = bloque
ORIGENES_COLA = ("dron:B{n}", "celular")
TIPOS_COLA = ("lectura", "inspeccion", "seguimiento")
