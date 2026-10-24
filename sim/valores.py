"""Valores permitidos del contrato (contrato/schema.sql). Una sola definición."""

MODOS = ("vivo", "temporada", "experimento")
ESCENARIOS = ("actual", "sensor_central", "drones", "drones_celular", "drones_sin_vent", "demo")
ENFERMEDADES = ("botrytis",)
NIVELES_RIESGO = ("bajo", "medio", "alto")
ORIGENES_INCIDENCIA = ("prediccion", "patrulla")
ESTADOS_INCIDENCIA = ("sospecha", "confirmada", "en_tratamiento", "en_seguimiento", "cerrada", "descartada")
RESULTADOS_SEGUIMIENTO = ("empeora", "igual", "mejora", "limpia")
SEVERIDADES = ("info", "advertencia", "critica")
TIPOS_ALERTA = ("riesgo_7d", "confirmacion", "seguimiento", "ventilacion", "descartada")
ESTADOS_ALERTA = ("nueva", "vista", "resuelta")
ESTADOS_DRON = ("patrulla", "prioridad", "inspeccionando", "carga")
ESTADOS_VENTILACION = ("encendida", "apagada")
FUENTES_LECTURA = ("sensor_fijo", "dron:B{n}")  # 'dron:B{n}' con n = bloque
ORIGENES_COLA = ("dron:B{n}", "celular")
TIPOS_COLA = ("lectura", "inspeccion", "seguimiento")
