"""Carga y validación de la configuración (default.yaml + YAML opcional encima)."""
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_DEFAULT = RAIZ / "config" / "default.yaml"

# Claves obligatorias (ruta con puntos).
OBLIGATORIAS = (
    "semilla", "sim.dias", "sim.inicio", "base_datos.busy_timeout_ms",
    "geometria.bloques", "geometria.naves_por_bloque", "geometria.camas_por_nave",
    "geometria.plantas_por_cama", "geometria.tiene_ventilacion",
    "geometria.posiciones_esquina", "geometria.separacion_camas_m",
    "geometria.separacion_plantas_m",
    "riesgo.umbral_alto", "riesgo.umbral_medio", "riesgo.hora_calculo",
    "robots.sens_latente", "robots.sens_sintomas", "robots.especificidad",
    "enfermedad.eficacia_tratamiento", "enfermedad.latencia_dias",
    "alertas.severidad",
)
ENTEROS_POSITIVOS = (
    "sim.dias", "base_datos.busy_timeout_ms", "geometria.bloques",
    "geometria.naves_por_bloque", "geometria.camas_por_nave", "geometria.plantas_por_cama",
)
PROBABILIDADES = (
    "riesgo.umbral_alto", "riesgo.umbral_medio", "robots.sens_latente",
    "robots.sens_sintomas", "robots.especificidad", "enfermedad.eficacia_tratamiento",
)
RANGOS = (  # listas [min, max] con min <= max
    "enfermedad.latencia_dias", "enfermedad.sintomas_a_perdida_dias",
    "enfermedad.focos_por_temporada", "clima.duracion_evento_h", "clima.hr_rango",
    "celular.ventana_hora",
)


def _fusionar(base: dict, encima: dict) -> dict:
    """Mezcla recursiva: los valores de `encima` ganan sobre `base`."""
    for clave, valor in encima.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            _fusionar(base[clave], valor)
        else:
            base[clave] = valor
    return base


def _leer_yaml(ruta: Path) -> dict:
    """Lee un YAML en utf-8; un archivo vacío da {}."""
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _obtener(cfg: dict, ruta: str):
    """Valor en `ruta` (con puntos); lanza ValueError con el nombre si falta."""
    valor = cfg
    for parte in ruta.split("."):
        if not isinstance(valor, dict) or parte not in valor:
            raise ValueError(f"config: falta la clave obligatoria '{ruta}'")
        valor = valor[parte]
    return valor


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validar(cfg: dict) -> dict:
    """Comprueba claves obligatorias y rangos; ValueError con el nombre de la clave."""
    for ruta in OBLIGATORIAS:
        _obtener(cfg, ruta)
    for ruta in ENTEROS_POSITIVOS:
        v = _obtener(cfg, ruta)
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError(f"config: '{ruta}' debe ser un entero > 0 (es {v!r})")
    for ruta in PROBABILIDADES:
        v = _obtener(cfg, ruta)
        if not _es_numero(v) or not 0 <= v <= 1:
            raise ValueError(f"config: '{ruta}' debe estar entre 0 y 1 (es {v!r})")
    for ruta in RANGOS:
        try:
            v = _obtener(cfg, ruta)
        except ValueError:
            continue  # los rangos opcionales solo se validan si existen
        if not (isinstance(v, list) and len(v) == 2 and all(_es_numero(x) for x in v) and v[0] <= v[1]):
            raise ValueError(f"config: '{ruta}' debe ser [min, max] con min <= max (es {v!r})")
    if cfg["riesgo"]["umbral_medio"] > cfg["riesgo"]["umbral_alto"]:
        raise ValueError("config: 'riesgo.umbral_medio' no puede superar 'riesgo.umbral_alto'")
    if not isinstance(cfg["geometria"]["tiene_ventilacion"], bool):
        raise ValueError("config: 'geometria.tiene_ventilacion' debe ser true o false")
    return cfg


def cargar_config(extra: Path | str | None = None) -> dict:
    """Carga default.yaml, aplica `extra` encima si se da, y valida."""
    cfg = _leer_yaml(CONFIG_DEFAULT)
    if extra is not None:
        _fusionar(cfg, _leer_yaml(Path(extra)))
    return validar(cfg)
