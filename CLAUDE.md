# CLAUDE.md · Berry Good Idea (Sabana Hack 2026)

Contexto del repo para Claude Code. Léelo completo antes de tocar código. Trabajamos en español; los nombres de variables y funciones pueden ir en inglés o en español, pero sé consistente dentro de cada módulo.

## Qué estamos construyendo

Sistema para detectar a tiempo enfermedades de humedad y temperatura (empezando por **Botrytis**) en **invernaderos de arándano**, y dejar registro de cada caso. Todo es **simulado**: no hay hardware real.

Flujo lineal (es el corazón de la propuesta):

1. **Predicción:** modelo que estima el riesgo de infección de cada cama a 7 días con temperatura, humedad, cambios de humedad y plantas infectadas cercanas.
2. **Detección:** **un robot de riel por bloque** con cámara 360 que baja entre las plantas y sensores de temperatura y humedad. Patrulla todas las camas en rutina y visita primero las de mayor riesgo.
3. **Seguimiento:** el robot registra **automáticamente** cada hallazgo y cada revisita. Si la nave tiene ventilación, el sistema la apaga automáticamente 48 h cuando hay una incidencia confirmada (las esporas viajan con el aire) y siempre avisa con una alerta `ventilacion`.

**Sin internet (supuesto por defecto):**
- Nivel 1: hub local en la finca con red propia (wifi o radio, sin internet). Alertas en tiempo real.
- Nivel 2 (peor caso): no hay red. El robot guarda los datos; un celular los descarga por Bluetooth cuando pasa un trabajador, corre el modelo ahí mismo y sincroniza cuando encuentra señal.
- Nivel 3: internet. Solo respaldo e historial. Nunca es requisito.

**Consecuencia para el código:** nada en tiempo de ejecución puede depender de internet. Librerías, fuentes y mapas van empaquetados localmente. Base de datos: **SQLite**.

## Ubicación: nomenclatura de la finca

Toda ubicación se expresa como **Bloque · Nave · Cama**, igual que en la finca (ej. `Bloque 1 · Nave 2 · Cama 14`). No usamos coordenadas x/y en la interfaz.

- Geometría por defecto (cambiar en `config/default.yaml` si hay datos reales): 4 bloques × 6 naves × 12 camas por nave.
- Las camas se numeran **continuas dentro del bloque**: nave 1 = camas 1–12, nave 2 = camas 13–24, …, nave 6 = camas 61–72.
- Cada cama tiene `plantas_por_cama` plantas (por defecto 40) en posiciones 1…40.
- Identificador de cama: `B{bloque}-N{nave}-C{cama:02d}`, ej. `B1-N2-C14`.

## Quién es dueño de qué

| Carpeta | Dueño | Contenido |
|---|---|---|
| `contrato/` | **Ambos** | Esquema de la base de datos y valores permitidos. Se cambia solo con acuerdo de los dos. |
| `config/` | Ambos | Parámetros en YAML. |
| `sim/` | Santiago | Simulador: geometría, clima, enfermedad, robots, ventilación, escritura a la base. |
| `prediccion/` | Santiago | Variables, reglas biológicas, modelo de IA, entrenamiento. |
| `analisis/` | Santiago | Escenarios, métricas, gráficas para las slides. |
| `hub/` | Samuel | Acceso a la base, API local, cola de sincronización, simulación del celular. |
| `dashboard/` | Samuel | Interfaz (mapa por bloque/nave/cama, alertas, incidencias, ventilación, estado de sincronización). |
| `tests/` | Cada uno los suyos | |

**Regla:** no edites carpetas del otro sin avisar. Si necesitas algo del otro lado, propón el cambio en `contrato/` o deja una nota en `NOTAS.md`.

Plan de Santiago: `planSantiago.md`. Plan de Samuel: `planSamuel.md`. Guía de implementación detallada (lado de Santiago): `MASTER_CODING_GUIDE.md`.

## Contrato de datos (`contrato/schema.sql`)

Es la frontera entre el simulador y el dashboard. El simulador **escribe** (incluidas `alertas`, `ventilacion` y `cola_sync`); el hub y el dashboard **leen** y escriben solo `alertas.estado`, `alertas.accion` y `cola_sync.hora_recibida`. Decisiones de detalle en `NOTAS.md`.

**La fuente de verdad es el archivo `contrato/schema.sql`** (incluye además índices y comentarios con los valores permitidos). Este resumen puede quedarse atrás:

```sql
CREATE TABLE corridas (
  corrida_id TEXT PRIMARY KEY,      -- 'demo', 'temporada-7', 'exp-robots-12'
  modo TEXT NOT NULL,               -- 'vivo' | 'temporada' | 'experimento'
  escenario TEXT NOT NULL,          -- 'actual' | 'sensor_central' | 'robots' | 'robots_celular' | 'robots_sin_vent' | 'demo'
  semilla INTEGER NOT NULL,
  config_json TEXT NOT NULL,
  inicio_sim TEXT NOT NULL          -- ISO 8601
);

CREATE TABLE camas (                -- geometría, una fila por cama
  cama_id TEXT PRIMARY KEY,         -- 'B1-N2-C14'
  bloque INTEGER, nave INTEGER, cama INTEGER,
  es_borde INTEGER,                 -- 1 si es la primera o última cama de la nave
  tiene_ventilacion INTEGER         -- 1 si la nave tiene ventilación controlable
);

CREATE TABLE lecturas (             -- temperatura y humedad medidas (no la verdad del simulador)
  corrida_id TEXT, hora INTEGER,    -- hora simulada desde el inicio
  cama_id TEXT, temp_c REAL, hr REAL,
  fuente TEXT                       -- 'sensor_fijo' | 'robot:B1'
);

CREATE TABLE riesgo (               -- salida del modelo, una fila por cama por día (06:00)
  corrida_id TEXT, dia INTEGER, cama_id TEXT,
  enfermedad TEXT,                  -- 'botrytis'
  riesgo_reglas REAL,               -- 0..1
  prob_ia_7d REAL,                  -- 0..1
  nivel TEXT                        -- 'bajo' | 'medio' | 'alto'
);

CREATE TABLE incidencias (
  incidencia_id INTEGER PRIMARY KEY,
  corrida_id TEXT, cama_id TEXT, posicion INTEGER,
  origen TEXT,                      -- 'prediccion' | 'patrulla'
  estado TEXT,                      -- ver estados abajo
  hora_creada INTEGER, hora_confirmada INTEGER, hora_cerrada INTEGER,
  confianza REAL, plantas_afectadas INTEGER,
  verdad_infectada INTEGER          -- solo para validación; el dashboard NO lo muestra
);

CREATE TABLE seguimientos (         -- registrado automáticamente por el robot
  seguimiento_id INTEGER PRIMARY KEY,
  incidencia_id INTEGER, corrida_id TEXT, hora INTEGER,
  robot_id TEXT, resultado TEXT,     -- 'empeora' | 'igual' | 'mejora' | 'limpia'
  plantas_afectadas INTEGER, nota TEXT
);

CREATE TABLE alertas (
  alerta_id INTEGER PRIMARY KEY,
  corrida_id TEXT, hora INTEGER, cama_id TEXT, incidencia_id INTEGER,
  severidad TEXT,                   -- 'info' | 'advertencia' | 'critica'
  tipo TEXT,                        -- 'riesgo_7d' | 'confirmacion' | 'seguimiento' | 'ventilacion' | 'descartada'
  titulo TEXT, mensaje TEXT,
  estado TEXT DEFAULT 'nueva',      -- 'nueva' | 'vista' | 'resuelta'
  accion TEXT                       -- lo que eligió el agrónomo en el dashboard
);

CREATE TABLE robots (               -- posición y estado, una fila por cambio
  corrida_id TEXT, hora REAL, robot_id TEXT, cama_id TEXT,
  estado TEXT,                      -- 'patrulla' | 'prioridad' | 'inspeccionando' | 'carga'
  bateria REAL
);

CREATE TABLE ventilacion (
  corrida_id TEXT, hora INTEGER, bloque INTEGER, nave INTEGER,
  estado TEXT,                      -- 'encendida' | 'apagada'
  motivo TEXT
);

CREATE TABLE cola_sync (            -- nivel 2: datos esperando llegar al modelo/hub
  id INTEGER PRIMARY KEY,
  corrida_id TEXT, origen TEXT,     -- 'robot:B1' | 'celular'
  hora_generada INTEGER, hora_recibida INTEGER, tipo TEXT, payload TEXT
);
```

**Estados de una incidencia:**
`sospecha → confirmada → en_tratamiento → en_seguimiento → cerrada`, o `sospecha → descartada`. Desde `en_seguimiento` puede volver a `confirmada` si el robot encuentra que empeora.

**Niveles de riesgo:** `alto` si `prob_ia_7d ≥ 0.6`, `medio` si `≥ 0.3`, si no `bajo`. Los umbrales viven en `config/default.yaml`.

## Convenciones

- Python 3.13, entorno virtual `.venv`. Dependencias en `requirements.txt` con versiones fijadas.
- Windows: abre siempre los archivos de texto con `encoding="utf-8"` (por defecto Windows usa cp1252 y rompe las tildes y la ñ).
- Toda corrida recibe una `semilla`. Una sola fuente de aleatoriedad por corrida: `numpy.random.default_rng(semilla)`. Nunca `random` global.
- Todo parámetro va en `config/default.yaml` con comentario de origen: `# fuente: biología (Sara B.)`, `# fuente: supuesto`, `# fuente: ficha técnica`. Nada de números mágicos en el código.
- El tiempo simulado se mide en **horas desde el inicio** (`hora`) y **días** (`dia = hora // 24`).
- La “verdad” del simulador (estado real de cada planta) **no va al dashboard**. Se guarda aparte (`data/verdad_<corrida>.parquet`) y solo la usa `analisis/`.
- Escribe pruebas cortas en `tests/` para lo que toques; corre `pytest -q` antes de hacer push.
- Funciones pequeñas y con docstring de una línea. Sin abstracciones de más: es un hackathon.

## Comandos

Los dos trabajamos en **Windows con PowerShell**. Rutas con `\` en la terminal; en el código usa `pathlib.Path` (nunca rutas armadas a mano).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # si sale "running scripts is disabled": Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt

python -m sim.run_temporada --escenario robots --semilla 7      # temporada completa → data/finca.db (--dias N; conserva las demás corridas, --recrear borra la base)
python -m sim.run_vivo --config config/demo.yaml --velocidad 1  # modo demo en vivo, 1 h simulada por segundo (conserva la temporada; --recrear borra la base)
python -m prediccion.entrenar                                  # entrena el modelo de IA con temporadas simuladas (≈4 min)
python -m sim.calibracion                                      # β_cama (r = 0,2/día) y β_vec (cama contigua 5,5 %) con las metas del PDF
python -m analisis.validar --semillas 30                       # escenarios × semillas → data/resultados/*.parquet y resumen.csv
python -m analisis.graficas                                    # las 6 gráficas PNG → data/resultados/
python -m hub.api                                              # API local (Samuel)
streamlit run dashboard/app.py                                 # dashboard local (Samuel)
pytest -q
```

## Git

- Ramas: `santiago/<tema>` y `samuel/<tema>`; merge a `main` cuando corre y pasa `pytest`.
- Commits pequeños y en español: `sim: contagio por corriente de aire`.
- `data/` está en `.gitignore`.

## Fechas (sábado 24 de octubre)

- **11:30** código congelado, video de respaldo grabado, ficha técnica y demo entregadas.
- **13:00** ensayo del pitch. **14:00** pitch (10 minutos).

Criterios del jurado: integración tecnológica en el prototipo 30 %, relevancia/impacto/ética 20 %, viabilidad y escalabilidad 20 %, innovación 10 %, uso y justificación de IA 10 %, negocio y pitch 10 %. Prioriza que **la demo funcione de punta a punta** (predicción → robot → incidencia → seguimiento → modo sin internet) sobre cualquier detalle extra.
