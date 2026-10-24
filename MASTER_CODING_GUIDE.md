# MASTER_CODING_GUIDE.md · Berry Good Idea (Sabana Hack 2026)

Guía maestra de implementación para **Claude Sonnet**. Une `CLAUDE.md` (contrato, convenciones, flujo de trabajo) y `planSantiago.md` (arquitectura, fases, fórmulas, parámetros) en instrucciones ejecutables.

- **Fuente de verdad:** si esta guía y `CLAUDE.md` o `planSantiago.md` se contradicen, ganan esos dos documentos y hay que avisar a Santiago para corregir la guía.
- **Alcance:** lado de Santiago (`sim/`, `prediccion/`, `analisis/`) y los archivos compartidos (`contrato/`, `config/`). El lado de Samuel (`hub/`, `dashboard/`) solo se describe para no romperlo.
- Las decisiones que **no** están en los documentos originales están marcadas como **[decisión pendiente]** o **[recomendación]**. No las presentes como hechos.

---

## 0. Instrucciones para Sonnet al iniciar una sesión

Haz esto **siempre**, en este orden, antes de escribir código:

1. Lee esta guía completa. Después lee `CLAUDE.md`. De `planSantiago.md` lee **solo la fase** de la tarea actual (sección 13 de esta guía te dice cuál).
2. Comprueba el estado del repo:
   ```powershell
   git status
   git branch --show-current
   ```
   - Si estás en `main`, crea una rama: `git switch -c santiago/<tema>`.
   - Si hay cambios sin commit que no son tuyos, **pregunta** antes de tocarlos.
3. Activa el entorno y corre las pruebas para saber el punto de partida:
   ```powershell
   .venv\Scripts\Activate.ps1
   pytest -q
   ```
   Si ya fallaban antes de tu cambio, dilo en tu respuesta; no los "arregles" sin que te lo pidan.
4. Identifica qué **invariantes** (sección 4) toca la tarea. Si la tarea obliga a romper uno, **detente y pregunta**.
5. Trabaja con el marco de la sección 11 y cierra con el checklist de la sección 12.

**Economía de contexto:** no releas archivos que ya tienes en contexto, no pegues archivos enteros en la respuesta, no expliques lo que no se pidió. Respuestas cortas con el formato de la sección 11.

---

## 1. Qué es el sistema

Sistema **simulado** (no hay hardware) para detectar a tiempo **Botrytis** en invernaderos de arándano y dejar registro de cada caso.

Flujo lineal (el corazón de la propuesta):

```
 Predicción (06:00 diario)        Detección (dron de cable)          Seguimiento (automático)
 ─────────────────────────        ─────────────────────────          ────────────────────────
 variables por cama        ──►    patrulla 1→72→1 por bloque  ──►    revisita cada 3 días
 reglas + IA (prob. 7 días)       prioridad a camas 'alto'           empeora / igual / mejora / limpia
 nivel bajo/medio/alto            inspección cámara 360              2× limpia → cerrada
 alerta riesgo_7d                 incidencia + alerta critica        ventilación apagada 48 h
```

**Conectividad (sin internet por defecto):**

| Nivel | Situación | Cómo llegan los datos |
|---|---|---|
| 1 | Hub local con red propia (wifi/radio, sin internet) | Tiempo real |
| 2 | Peor caso: sin red | El dron guarda; un celular descarga por Bluetooth cuando pasa un trabajador, corre el modelo ahí y sincroniza al encontrar señal (`cola_sync`) |
| 3 | Internet | Solo respaldo e historial. **Nunca es requisito** |

**Consecuencia:** nada en tiempo de ejecución puede depender de internet. Librerías, fuentes y mapas empaquetados localmente. Base de datos: **SQLite**.

---

## 2. Stack exacto (cerrado)

| Pieza | Uso | Origen en los documentos |
|---|---|---|
| **Python 3.13** | Todo | `CLAUDE.md` (actualizado de 3.12 a 3.13, versión instalada) |
| `.venv` | Entorno virtual | `CLAUDE.md` |
| **numpy** | Simulación vectorizada; única fuente aleatoria `numpy.random.default_rng(semilla)` | `CLAUDE.md`, plan 2.3 |
| **scipy.sparse** | Matriz de vecindad dispersa | plan 2.1 ("matriz dispersa") |
| **pandas + pyarrow** | Verdad del simulador en `data/verdad_<corrida>.parquet`; métricas en `data/resultados/metricas.parquet` | `CLAUDE.md`, plan 5.3 |
| **sqlite3** (librería estándar) | `data/finca.db`, modo **WAL** | `CLAUDE.md`, checklist del plan |
| **scikit-learn** | `HistGradientBoostingClassifier`, AUC, PR-AUC, importancia por permutación | plan 3.4 |
| **joblib** | `data/modelo_ia.joblib` | plan 3.4 |
| **PyYAML** | `config/*.yaml` | `CLAUDE.md` |
| **matplotlib** | Gráficas PNG 1920×1080, fondo oscuro | plan 5.4 (la librería es **[recomendación]**: el plan pide PNG pero no la nombra) |
| **pytest** | Pruebas | `CLAUDE.md` |
| Streamlit | Dashboard | **Solo Samuel.** No lo importes desde `sim/`, `prediccion/` ni `analisis/` |

Reglas:
- **No agregues dependencias** sin preguntar. LightGBM solo si ya está instalado (plan 3.4); por defecto, scikit-learn.
- Prohibido: el módulo `random` de la librería estándar, cualquier llamada de red, ORMs, frameworks de tareas o de inyección de dependencias, bases de datos distintas de SQLite.
- Versiones fijadas en `requirements.txt` (se genera en la Fase 1, ver sección 13).

---

## 3. Arquitectura y límites de módulo

### 3.1 Árbol del repositorio

```
SabanaHack/
├── CLAUDE.md                 contexto del repo            (ambos)
├── MASTER_CODING_GUIDE.md    esta guía                    (Santiago)
├── planSantiago.md           plan de Santiago             (Santiago)
├── planSamuel.md             plan de Samuel               (Samuel · solo lectura)
├── prompts/                  prompts de Samuel            (Samuel · NO TOCAR)
├── NOTAS.md                  notas entre los dos          (ambos)
├── requirements.txt          versiones fijadas            (ambos)
├── .gitignore / .gitattributes                            (ambos)
├── contrato/
│   └── schema.sql            frontera simulador ↔ dashboard  (ambos · solo con acuerdo)
├── config/
│   ├── default.yaml          todos los parámetros         (ambos)
│   └── demo.yaml             escenario de la demo         (Santiago)
├── sim/                      simulador                    (Santiago)
├── prediccion/               variables, reglas, IA        (Santiago)
├── analisis/                 escenarios, métricas, gráficas (Santiago)
├── hub/                      API local, cola, celular     (Samuel · NO TOCAR)
├── dashboard/                interfaz Streamlit           (Samuel · NO TOCAR)
├── tests/                    cada uno los suyos
└── data/                     generado, en .gitignore      (nunca se sube)
    ├── finca.db
    ├── verdad_<corrida>.parquet
    ├── modelo_ia.joblib / modelo_ia.json
    └── resultados/           metricas.parquet + PNG
```

**Regla de propiedad:** no edites carpetas de Samuel. Si necesitas algo de su lado, propón el cambio en `contrato/` o deja una nota en `NOTAS.md`.

### 3.2 Módulos del lado de Santiago

| Archivo | Responsabilidad | Entra | Sale |
|---|---|---|---|
| `sim/config.py` **[recomendación]** | Cargar y validar YAML | ruta YAML | `dict` validado |
| `sim/geometria.py` | Índices de planta, `cama_id`, bordes, matriz de vecindad, pesos de aire | config `geometria` | arreglos numpy, `scipy.sparse` |
| `sim/clima.py` | `T`, `HR`, eventos húmedos, ventilación, horas de mojado por cama y hora | config `clima`, rng, estado de ventilación | arreglos `(horas, camas)` en memoria |
| `sim/enfermedad.py` | Estados por planta, infección, latencia, pérdida, `tratar()`, focos iniciales | clima, vecindad, ventilación, rng | estado por planta, eventos de verdad |
| `sim/sensores.py` | Sensor central por bloque | clima verdadero, rng | filas `lecturas` (`sensor_fijo`) |
| `sim/drones.py` | Patrulla, prioridad, inspección, incidencias, alertas, ventilación, tratamiento, seguimiento, batería | estado de plantas, riesgo, rng | filas `lecturas`, `drones`, `incidencias`, `seguimientos`, `alertas`, `ventilacion` |
| `sim/escritor.py` | Crear la base desde `contrato/schema.sql`, WAL, inserciones por lote | conexión, filas | `data/finca.db` |
| `sim/run_temporada.py` | CLI de temporada completa | `--escenario --semilla --dias` | `finca.db`, `verdad_<corrida>.parquet` |
| `sim/run_vivo.py` | CLI de demo hora a hora | `--config --velocidad` | escrituras incrementales en `finca.db` |
| `prediccion/variables.py` | Variables por cama a las 06:00 **sin verdad** | `lecturas`, `incidencias` confirmadas, `ventilacion`, `camas` | `DataFrame` de variables |
| `prediccion/etiquetas.py` | `y` a 7 días (usa verdad, solo entrenamiento/evaluación) | eventos de verdad | `Series` 0/1 |
| `prediccion/reglas.py` | Línea base biológica | variables | `riesgo_reglas` ∈ [0,1] |
| `prediccion/ia.py` | Cargar modelo y predecir | variables, `modelo_ia.joblib` | `prob_ia_7d` ∈ [0,1] |
| `prediccion/entrenar.py` | Entrenar con semillas 0–39, probar con 40–49 | temporadas simuladas | modelo, lista de variables, AUC/PR-AUC impresos |
| `analisis/metricas.py` | Anticipación, retraso, afectadas, falsas alarmas, no detectados, métricas del modelo | `finca.db` + verdad | `DataFrame` por semilla y escenario |
| `analisis/validar.py` | CLI: correr escenarios × semillas, IC 95 % bootstrap | `--semillas N` | `data/resultados/metricas.parquet` |
| `analisis/graficas.py` | 6 gráficas para las slides | `metricas.parquet` | PNG en `data/resultados/` |

Todos los paquetes llevan `__init__.py` y se ejecutan como módulos (`python -m sim.run_temporada`).

### 3.3 Flujo de datos

```
config/default.yaml ──► sim/geometria ──► sim/clima ──► sim/enfermedad ──┐
                                             │               │            │
                                             ▼               ▼            ▼
                                     sim/sensores      sim/drones    verdad (memoria)
                                             │               │            │
                                             └──► lecturas ◄─┘            ▼
                                                      │          data/verdad_<corrida>.parquet
                                                      ▼                   │
                         prediccion/variables (06:00, SIN verdad)         │
                                │                                         │
                    ┌───────────┴───────────┐                             │
                    ▼                       ▼                             │
           prediccion/reglas        prediccion/ia ◄── entrenar ◄── etiquetas ◄┘
                    └───────────┬───────────┘
                                ▼
                        tabla riesgo + alertas riesgo_7d ──► sim/drones (prioridad)
                                ▼
                         data/finca.db ──► hub/ + dashboard/ (Samuel, solo lectura)
                                ▲
                         analisis/ lee finca.db + verdad ──► data/resultados/
```

---

## 4. Invariantes no negociables

Romper cualquiera de estos es una regresión. Si una tarea lo exige, **pregunta primero**.

1. **Sin internet en tiempo de ejecución.** Ninguna importación ni llamada de red.
2. **Propiedad de carpetas.** Nunca escribas en `hub/` ni `dashboard/`.
3. **Quién escribe qué en la base.** El simulador escribe `corridas`, `camas`, `lecturas`, `riesgo`, `incidencias`, `seguimientos`, `drones`, `ventilacion`, `cola_sync` y crea `alertas`. El hub/dashboard solo escribe `alertas.estado`, `alertas.accion`, `ventilacion` y la cola de sincronización. `ventilacion` y `cola_sync` las escriben los dos: el reparto exacto está pendiente (sección 13, decisiones abiertas con Samuel).
4. **El contrato (`contrato/schema.sql`) no cambia sin acuerdo de los dos.** Ni columnas, ni nombres, ni valores permitidos.
5. **La verdad no va a la base ni al dashboard.** El estado real de cada planta se guarda en `data/verdad_<corrida>.parquet` y solo lo usan `prediccion/etiquetas.py`, `prediccion/entrenar.py` y `analisis/`. Excepción del contrato: `incidencias.verdad_infectada` (solo validación; el dashboard no lo muestra).
6. **`prediccion/variables.py` nunca lee la verdad.** Solo lecturas medidas, incidencias **confirmadas**, ventilación y geometría.
7. **Entrenamiento separado por temporada:** semillas 0–39 entrenan, 40–49 prueban. Nunca separar por fila.
8. **Una sola fuente aleatoria por corrida:** `rng = numpy.random.default_rng(semilla)`, creado una vez y pasado como argumento. Nunca `random`, nunca `np.random.<función>` global.
9. **Números aleatorios comunes:** todos los escenarios de una comparación usan la misma semilla.
10. **Cero números mágicos.** Todo parámetro vive en `config/default.yaml` con comentario `# fuente: biología (Sara B.)`, `# fuente: supuesto` o `# fuente: ficha técnica`.
11. **Tiempo:** `hora` = horas simuladas desde el inicio (entero); `dia = hora // 24`. Excepción: `drones.hora` es `REAL` (el dron cambia de cama cada pocos minutos).
12. **El riesgo se calcula una vez al día a las 06:00** (`hora % 24 == 6`), una fila por cama por día en `riesgo`.
13. **Niveles:** `alto` si `prob_ia_7d ≥ umbral_alto` (0.6), `medio` si `≥ umbral_medio` (0.3), si no `bajo`. Umbrales leídos de `config`, nunca escritos en el código.
14. **Ubicación:** siempre `Bloque · Nave · Cama`, nunca x/y en la interfaz. Camas numeradas **continuas dentro del bloque** (nave 1 = 1–12, nave 2 = 13–24, …, nave 6 = 61–72). `cama_id = f"B{bloque}-N{nave}-C{cama:02d}"`, ej. `B1-N2-C14`.
15. **`es_borde` vs `es_borde_planta`:** `es_borde` es por cama (primera o última cama de la nave), va a `camas` y es variable del modelo. `es_borde_planta` es por planta (cama de borde **o** posiciones 1–5 y 36–40), es interno de `sim/` y nunca va a la base.
16. **`lecturas` contiene mediciones, no la verdad:** siempre con ruido de medición y con `fuente` (`sensor_fijo` | `dron:B{n}`).
17. **Archivos de texto siempre con `encoding="utf-8"`**; rutas siempre con `pathlib.Path`.

---

## 5. Contrato de datos

### 5.1 Esquema (`contrato/schema.sql`, copia exacta de `CLAUDE.md`)

```sql
CREATE TABLE corridas (
  corrida_id TEXT PRIMARY KEY,      -- 'demo', 'temporada-7', 'exp-drones-12'
  modo TEXT NOT NULL,               -- 'vivo' | 'temporada' | 'experimento'
  escenario TEXT NOT NULL,          -- 'actual' | 'sensor_central' | 'drones' | 'drones_celular' | 'drones_sin_vent' | 'demo'
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
  fuente TEXT                       -- 'sensor_fijo' | 'dron:B1'
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

CREATE TABLE seguimientos (         -- registrado automáticamente por el dron
  seguimiento_id INTEGER PRIMARY KEY,
  incidencia_id INTEGER, corrida_id TEXT, hora INTEGER,
  dron_id TEXT, resultado TEXT,     -- 'empeora' | 'igual' | 'mejora' | 'limpia'
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

CREATE TABLE drones (               -- posición y estado, una fila por cambio
  corrida_id TEXT, hora REAL, dron_id TEXT, cama_id TEXT,
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
  corrida_id TEXT, origen TEXT,     -- 'dron:B1' | 'celular'
  hora_generada INTEGER, hora_recibida INTEGER, tipo TEXT, payload TEXT
);
```

**Cómo usarlo en código:** define los valores permitidos **una sola vez** en Python, en un módulo compartido del lado de Santiago (p. ej. `sim/valores.py` **[recomendación]**), con tuplas como `ESCENARIOS`, `ESTADOS_INCIDENCIA`, `TIPOS_ALERTA`, y valida contra ellas antes de insertar. Agregar `CHECK (... IN (...))` al SQL es **[decisión pendiente]** con Samuel.

### 5.2 Máquina de estados de una incidencia

```
              inspección positiva                tratamiento (+6 h)          primera revisita
  sospecha ───────────────────────► confirmada ───────────────► en_tratamiento ──────────────► en_seguimiento
     │                                  ▲                                                        │   │
     │ inspección negativa              │                    resultado 'empeora'                 │   │ 2 revisitas 'limpia'
     ▼                                  └────────────────────────────────────────────────────────┘   │ seguidas
  descartada                                                                                         ▼
                                                                                                  cerrada
```

Transiciones válidas (cualquier otra es un error y debe lanzar `ValueError`):

| Desde | Hacia |
|---|---|
| `sospecha` | `confirmada`, `descartada` |
| `confirmada` | `en_tratamiento` |
| `en_tratamiento` | `en_seguimiento` |
| `en_seguimiento` | `confirmada` (si empeora), `cerrada` |

### 5.3 Alertas que crea el simulador

| Evento | `tipo` | `severidad` | Mensaje modelo (plan) |
|---|---|---|---|
| Cama pasa a `alto` | `riesgo_7d` | `advertencia` | `B1 · Nave 2 · Cama 14: alto riesgo de Botrytis en los próximos 7 días (prob. 0.74). HR > 90 % durante 15 h.` |
| Inspección positiva | `confirmacion` | `critica` | `Botrytis confirmada · B1 · Nave 2 · Cama 14 · posición 22. 3 plantas afectadas (confianza 0.88).` |
| Inspección negativa | `descartada` | `info` | — |
| Ventilación apagada | `ventilacion` | — **[decisión pendiente]** | — |
| Revisita | `seguimiento` | — **[decisión pendiente]** | — |

Los textos de las alertas se arman en **una función** por tipo, con la ubicación en formato `B{b} · Nave {n} · Cama {c}`.

---

## 6. Modelos matemáticos (exactos del plan)

### 6.1 Geometría (`sim/geometria.py`)
- Por defecto 4 bloques × 6 naves × 12 camas × 40 plantas = **11 520 plantas**, 288 camas.
- Índice global de planta `i` con arreglos `bloque[i]`, `nave[i]`, `cama[i]`, `posicion[i]` (posiciones 1…40).
- **Vecindad** `V` (dispersa, se construye una vez): misma cama a ±2 posiciones → peso **1.0**; camas contiguas de la misma nave a ±1 posición → peso **0.4**.
- **Corriente de aire:** la ventilación sopla a lo largo de la nave en un sentido fijo. Una planta infecciosa aporta presión a las camas "aguas abajo" de su nave: `w_aire = exp(-d / L_aire)`, con `d` en camas.

### 6.2 Clima por cama y hora (`sim/clima.py`)
```
T  = T_media  + A_T  · sin(2π(h − 9)/24) + offset_nave + ruido
HR = HR_media − A_HR · sin(2π(h − 9)/24) + offset_nave + extra_borde · es_borde + ruido     → recortar a [30, 100]
```
- Eventos húmedos aleatorios (tasa `eventos_humedos_por_dia`), duran 6–18 h y suben la HR del **bloque**.
- Ventilación **encendida**: HR de la nave `+ delta_ventilacion_hr` (−5) y activa la corriente de aire. **Apagada**: HR más alta, sin transporte de esporas. (Este dilema se muestra en la demo.)
- Horas de mojado: horas con `HR ≥ umbral_mojado_hr` en ventanas de 24 h y 72 h.
- `T`, `HR` y mojado **verdaderos** se guardan en memoria (numpy), no en la base.

### 6.3 Enfermedad (`sim/enfermedad.py`, vectorizado)
Estados por planta: `0 sana · 1 latente (contagia, sin síntomas) · 2 con síntomas · 3 tratada · 4 perdida`.

```
f_T  = exp(-((T - T_opt) / T_ancho)^2)
f_M  = min(1, horas_mojado_24h / horas_mojado_full)
p    = 1 - exp(-(β_vec·presion_vecinos + β_aire·presion_aire + β_0) · f_T · f_M)

presion_vecinos = V @ (0.5·[latente] + 1.0·[síntomas])
presion_aire    = solo si la ventilación de la nave está encendida
```
- Latente → síntomas tras `U(latencia_min, latencia_max)` días. Síntomas → perdida tras `sintomas_a_perdida_dias` si no se trata.
- `tratar(plantas)`: éxito con probabilidad `eficacia_tratamiento` → tratada (deja de contagiar) → vuelve a sana tras `dias_proteccion`.
- Focos iniciales: `focos_por_temporada` (1–3) en plantas aleatorias, preferir `es_borde_planta`.
- **Calibración de β:** en `sensor_central`, la temporada termina con **5–15 %** de plantas afectadas. Barrido rápido de `β_vec` y `β_aire`.
- **Verdad a disco [recomendación]:** guardar **eventos de cambio de estado** (`planta`, `cama_id`, `hora`, `estado_nuevo`) en vez de una foto por hora (11 520 × 1 440 filas sería innecesario). Basta para etiquetas y métricas.

### 6.4 Sensores fijos (`sim/sensores.py`)
- Escenario `sensor_central`/`actual`: un sensor por bloque en la **cama central**, mide `T` y `HR` con ruido cada hora → `lecturas` con `fuente='sensor_fijo'`.
- Para las demás camas el sistema solo "sabe" ese valor.

### 6.5 Drones (`sim/drones.py`)
- Un dron por bloque. Estados `patrulla → prioridad → inspeccionando → carga`.
- **Patrulla:** camas del bloque en orden 1 → 72 → 1…, `min_por_cama` (6 min) por cama → ~10 camas por hora, una vuelta ≈ 7.2 h. Resolución por debajo de la hora, por eso `drones.hora` es `REAL`.
- En cada cama: mide `T` y `HR` con ruido → `lecturas` con `fuente='dron:B{n}'`; inspecciona cada planta: latente detectada con `sens_latente` (0.25), con síntomas con `sens_sintomas` (0.90), falso positivo con `1 − especificidad`.
- **Prioridad:** cama del bloque con `nivel='alto'` sin visita en las últimas 24 h → interrumpe la patrulla; cola ordenada por `prob_ia_7d` descendente.
- **Hallazgo:** crea incidencia `sospecha` → positiva: `confirmada` + alerta `critica`; negativa: `descartada` + alerta `info`.
- **Ventilación:** confirmación en nave con `tiene_ventilacion=1` → apagar 48 h → fila en `ventilacion` + alerta `ventilacion`. (No aplica en `drones_sin_vent`.)
- **Tratamiento:** `horas_hasta_tratamiento` (6 h) después → `en_tratamiento` y se llama `tratar()`.
- **Seguimiento automático:** revisita cada `dias_revisita` (3) → fila en `seguimientos` (`empeora`/`igual`/`mejora`/`limpia`). Dos `limpia` seguidas → `cerrada`. `empeora` → `confirmada` y se trata de nuevo.
- Cada cambio de cama → fila en `drones`.
- **Batería:** baja por hora de trabajo; al llegar a `bateria_min` va a `carga` durante `horas_carga`.

### 6.6 Variables del modelo (`prediccion/variables.py`) · cada cama, cada día a las 06:00
| Grupo | Variables |
|---|---|
| Temperatura | `temp_media_24h`, `temp_min_24h`, `temp_max_24h` |
| Humedad | `hr_media_24h`, `hr_max_24h`, `delta_hr_24h` (contra el día anterior) |
| Mojado | `horas_mojado_24h`, `horas_mojado_72h`, `dias_seguidos_hr_alta` |
| Vecinos | `confirmadas_misma_cama`, `confirmadas_camas_vecinas`, `distancia_a_confirmada_en_nave` (en camas; **99** si no hay) |
| Contexto | `ventilacion_encendida`, `es_borde` |
| Calidad del dato | `edad_lectura_h` (horas desde la última medición real de esa cama) |

Si una cama no tiene lecturas propias en la ventana, usa el sensor central de su bloque y refleja la antigüedad en `edad_lectura_h` **[recomendación de implementación]**.

### 6.7 Etiqueta (`prediccion/etiquetas.py`)
`y = 1` si alguna planta de la cama pasa de sana a latente en las próximas **168 h**. Usa la verdad; solo para entrenar y evaluar.

### 6.8 Reglas biológicas (`prediccion/reglas.py`)
```
riesgo_reglas = f_T(temp_media_24h) · min(1, horas_mojado_72h / umbral) · (1 + bonus si hay confirmadas cerca)    → recortar a [0, 1]
```

### 6.9 Modelo de IA (`prediccion/ia.py`, `prediccion/entrenar.py`)
- `HistGradientBoostingClassifier`, `class_weight='balanced'` (o pesos por muestra).
- 40 temporadas (semillas 0–39) entrenan, 10 (40–49) prueban.
- Guarda `data/modelo_ia.joblib` y la lista ordenada de variables en `data/modelo_ia.json`. `ia.py` valida que las columnas coincidan con ese JSON.
- Importancia por permutación para la slide de IA.
- Salida esperada: AUC y PR-AUC de reglas vs. IA en las semillas de prueba.

---

## 7. Configuración

### 7.1 `config/default.yaml` (valores iniciales del plan · reemplazar con los de Sara B.)

```yaml
semilla: 7
sim: {dias: 60, inicio: "2026-11-01T00:00:00"}
geometria: {bloques: 4, naves_por_bloque: 6, camas_por_nave: 12, plantas_por_cama: 40}
clima:
  T_media: 18.0            # fuente: supuesto (invernadero en altiplano)
  A_T: 6.0
  HR_media: 78.0
  A_HR: 10.0
  extra_borde_hr: 4.0       # esquinas y bordes más húmedos
  delta_ventilacion_hr: -5.0
  eventos_humedos_por_dia: 0.15
  umbral_mojado_hr: 90.0
enfermedad:                 # botrytis, fuente: supuesto hasta recibir datos de Sara B.
  T_opt: 18.0
  T_ancho: 6.0
  horas_mojado_full: 10
  beta_vec: 0.05
  beta_aire: 0.02
  beta_0: 2.0e-6
  L_aire_camas: 3.0
  latencia_dias: [7, 14]
  sintomas_a_perdida_dias: [14, 28]
  eficacia_tratamiento: 0.85
  dias_proteccion: 4
  focos_por_temporada: [1, 3]
drones:
  por_bloque: 1
  min_por_cama: 6
  sens_latente: 0.25
  sens_sintomas: 0.90
  especificidad: 0.98
  dias_revisita: 3
  horas_hasta_tratamiento: 6
  bateria_horas: 6
  horas_carga: 1
riesgo: {umbral_alto: 0.6, umbral_medio: 0.3}
actual: {p_humano: 0.35, dias_ronda: 4}
```

### 7.2 Parámetros que el plan usa pero el YAML no tiene

Agrégalos en la Fase 1 con `# fuente: supuesto` (valor del plan cuando lo hay). **No los escribas en el código.**

| Parámetro | Valor del plan | Sección |
|---|---|---|
| `clima.duracion_evento_h` | `[6, 18]` | 2.2 |
| `clima.ruido_T`, `clima.ruido_HR`, `clima.offset_nave_T`, `clima.offset_nave_HR` | — (definir) | 2.2 |
| `clima.hr_rango` | `[30, 100]` | 2.2 |
| `geometria.vecindad` | misma cama ±2 → 1.0; cama contigua ±1 → 0.4 | 2.1 |
| `geometria.posiciones_esquina` | 1–5 y 36–40 | 2.1 |
| `enfermedad.peso_latente`, `peso_sintomas` | 0.5, 1.0 | 2.3 |
| `enfermedad.meta_afectadas_sensor_central` | `[0.05, 0.15]` | 2.3 |
| `sensores.ruido_T`, `sensores.ruido_HR` | — (definir) | 2.4 |
| `drones.horas_sin_visita_prioridad` | 24 | 4 |
| `drones.horas_ventilacion_apagada` | 48 | 4 |
| `drones.limpias_para_cerrar` | 2 | 4 |
| `drones.bateria_min` | — (definir) | 4 |
| `riesgo.hora_calculo` | 6 | 3.5 |
| `riesgo.horizonte_h` | 168 | 3.2 |
| `riesgo.bonus_confirmadas`, `riesgo.umbral_mojado_72h` | — (definir) | 3.3 |
| `entrenamiento.semillas_train`, `semillas_test` | 0–39, 40–49 | 3.4 |
| `celular.ventana_hora` | `[7, 15]`, una vez al día | 5.1 |
| `analisis.top_k_camas` | 10 | 5.2 |
| `analisis.umbral_foco_no_detectado` | 5 plantas con síntomas | 5.2 |

### 7.3 Reglas
- `config/demo.yaml` sobrescribe solo lo que cambia respecto a `default.yaml` (carga: default → demo encima).
- La config completa usada se guarda en `corridas.config_json`.
- Validar al cargar: claves obligatorias presentes, rangos lógicos (`0 ≤ prob ≤ 1`, listas `[min, max]` con `min ≤ max`). Error → `ValueError` con el nombre de la clave.

---

## 8. Convenciones de código

- Python 3.13, todo ejecutable como módulo: `python -m paquete.modulo`.
- **Funciones pequeñas con docstring de una línea.** Sin abstracciones de más: es un hackathon. Funciones puras que reciben arreglos y devuelven arreglos; las clases solo si hay estado real que mantener (el dron es el candidato natural).
- **Vectorizado:** en el paso horario nada de bucles por planta. Los bucles por hora y por dron sí están permitidos.
- **Aleatoriedad:** `rng` como parámetro explícito de toda función que sortee algo.
- **Nombres:** español o inglés, pero consistente **dentro de cada módulo**. Los nombres del dominio van como en el contrato (`cama_id`, `nave`, `incidencia`, `seguimiento`).
- **Archivos:** `open(ruta, encoding="utf-8")`, `pathlib.Path` para rutas, raíz del repo resuelta desde `Path(__file__)`.
- **SQLite:** inserciones con `executemany` y parámetros `?`, nunca SQL armado con f-strings sobre datos.
- **CLI:** `argparse`, cada script con `main()` y `if __name__ == "__main__": main()`.
- **Commits:** pequeños, en español, `area: descripción` (ej. `sim: contagio por corriente de aire`).

---

## 9. Manejo de errores

| Situación | Qué hacer |
|---|---|
| Config inválida o incompleta | `ValueError` inmediato al cargar, con el nombre de la clave |
| Valor fuera del contrato (escenario, estado, tipo, severidad) | `ValueError` antes de insertar |
| Transición de estado inválida | `ValueError` con estado origen y destino |
| Modelo ausente (`modelo_ia.joblib`) | Error claro que diga correr `python -m prediccion.entrenar`. **[decisión pendiente]**: si en su lugar el sistema usa `riesgo_reglas` (ver sección 13, Fase 3) |
| Columnas del modelo no coinciden con `modelo_ia.json` | `ValueError` |
| Base SQLite | `with sqlite3.connect(...)`, transacción por lote, `PRAGMA journal_mode=WAL` y `PRAGMA busy_timeout` al abrir, para que `run_vivo` escriba mientras el dashboard lee |

- Prohibido `except:` o `except Exception: pass`. Captura solo lo que sabes manejar.
- Sin `print` de depuración en el código final; los CLI pueden imprimir un resumen (filas escritas, tiempo, métricas).

---

## 10. Pruebas (`tests/`, `pytest -q`)

Escribe pruebas cortas para lo que toques. Mínimo por módulo:

| Módulo | Prueba |
|---|---|
| `geometria` | 288 camas, 11 520 plantas; `B1-N2-C14` está en nave 2; nave 6 = camas 61–72; `es_borde` solo en primera/última cama de cada nave; `V` simétrica con los pesos correctos |
| `clima` | Misma semilla → mismos arreglos; `HR` siempre en [30, 100]; ventilación encendida baja la HR |
| `enfermedad` | Reproducibilidad; solo transiciones de estado válidas; sin focos ni β_0 → nadie se infecta; tratada no contagia |
| `sensores` | Una lectura por bloque por hora, `fuente='sensor_fijo'` |
| `drones` | Prioridad interrumpe la patrulla; positiva → `confirmada` + alerta `critica`; ventilación apagada solo si `tiene_ventilacion=1`; 2 `limpia` → `cerrada` |
| `escritor` | Las tablas creadas coinciden con `contrato/schema.sql`; WAL activo |
| `variables` | **No lee la verdad** (construir variables sin pasar la verdad debe funcionar); `distancia_a_confirmada_en_nave = 99` si no hay |
| `etiquetas` | Infección a las 167 h → 1; a las 169 h → 0 |
| `reglas` | Salida en [0, 1] |
| `entrenar` | Semillas de train y test no se cruzan |
| Integración | `python -m sim.run_temporada --dias 1` crea `data/finca.db` con `camas` llena (usar ruta temporal de pytest `tmp_path`) |

Rendimiento (verificación manual, no prueba automática): **temporada de 60 días en menos de 60 s.**

---

## 11. Marco de ejecución de tareas para Sonnet

Para cada tarea:

1. **Ubicar:** ¿qué fase y qué archivo de la sección 3.2? ¿Qué invariantes de la sección 4 toca?
2. **Planear en ≤ 5 puntos** (mentalmente o en la respuesta si la tarea es grande). Si falta un parámetro, agrégalo al YAML con `# fuente: supuesto`; si falta una decisión de diseño, **pregunta**.
3. **Implementar la pieza más pequeña que corra de punta a punta.** Regla de oro del plan: *primero que todo corra con valores simples; después se afina.*
4. **Probar:** prueba nueva en `tests/` + `pytest -q`.
5. **Verificar** el criterio "Listo cuando" de la fase (sección 13) con el comando real.
6. **Checklist** de la sección 12 → commit en la rama `santiago/<tema>`.

**Formato de respuesta al terminar una tarea:**

```
Hecho: <una línea>
Archivos: <lista corta>
Comando: <lo que corriste> → <resultado: pruebas pasadas, tiempo, filas>
Pendiente / decisiones: <solo si hay>
```

Sin volcar archivos completos, sin repetir esta guía, sin explicar código obvio.

---

## 12. Checklist antes de cada commit

- [ ] `pytest -q` pasa (o dejas explícito qué falla y por qué).
- [ ] Ningún número mágico nuevo: todo parámetro está en `config/default.yaml` con `# fuente:`.
- [ ] Ningún `import random` ni `np.random.<función>` global; solo el `rng` de la corrida.
- [ ] Todo `open()` lleva `encoding="utf-8"`.
- [ ] Nada de `data/` en el commit (`git status` limpio de `data/`).
- [ ] Ningún archivo de `hub/` ni `dashboard/` modificado.
- [ ] `contrato/schema.sql` sin cambios (o cambio acordado con Samuel y anotado en `NOTAS.md`).
- [ ] La verdad no se filtró a la base ni a `prediccion/variables.py`.
- [ ] Mensaje de commit en español, `area: descripción`.
- [ ] Merge a `main` solo si corre y pasa `pytest`.

---

## 13. Fases con criterios de aceptación

Fecha límite: **sábado 24 de octubre, 11:30 código congelado.**

### Fase 1 · Base y contrato (22:00–23:30)
- Crear: `.gitignore` (`data/`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`), `.gitattributes` (`* text=auto eol=lf`), `contrato/schema.sql` (copia exacta de la sección 5.1), `config/default.yaml` (sección 7.1 + parámetros de 7.2), paquetes `sim/`, `prediccion/`, `analisis/`, `tests/` con `__init__.py`.
- `requirements.txt`: instalar numpy, scipy, pandas, pyarrow, scikit-learn, joblib, pyyaml, matplotlib, pytest y fijar con `pip freeze > requirements.txt`.
- `sim/escritor.py`: crea la base desde `contrato/schema.sql`, activa WAL, llena `camas`.
- Parámetros biológicos de Sara B. si llegan; si no, quedan como `# fuente: supuesto`.
- **Listo cuando:** `python -m sim.run_temporada --dias 1` crea `data/finca.db` con las tablas vacías y `camas` llena.

### Fase 2 · Simulador del invernadero (23:30–01:30)
- `geometria.py`, `clima.py`, `enfermedad.py`, `sensores.py` (sección 6.1–6.4). Calibrar β hasta 5–15 % afectadas en `sensor_central`.
- **Listo cuando:** una temporada de 60 días corre en < 60 s y genera focos que crecen y se expanden por la nave.

### Fase 3 · Modelo predictivo (01:30–03:30)
- `variables.py`, `etiquetas.py`, `reglas.py`, `ia.py`, `entrenar.py` (sección 6.6–6.9) y escritura diaria en `riesgo` + alertas `riesgo_7d`.
- **[decisión pendiente] Huevo y gallina:** para generar las temporadas de entrenamiento todavía no existe el modelo, y en el escenario `drones` la prioridad depende de `prob_ia_7d`. Opción recomendada: si no hay modelo, `nivel` se calcula con `riesgo_reglas` y `prob_ia_7d` queda `NULL`; se entrena; luego se re-simulan las semillas de prueba ya con IA. Confirmar con Santiago antes de implementarlo.
- **Listo cuando:** `python -m prediccion.entrenar` imprime AUC y PR-AUC de reglas vs. IA en las semillas de prueba.

### Descanso (03:30–06:30)

### Fase 4 · Drones de cable y seguimiento (06:30–08:00)
- `sim/drones.py` completo (sección 6.5).
- **Listo cuando:** en una temporada `drones` hay incidencias en todos los estados y seguimientos registrados solos.

### Fase 5 · Escenarios y validación (08:00–10:30)
| Escenario | Qué tiene |
|---|---|
| `actual` | Sensor central + revisión manual (`p_humano` por pasada, una pasada por cama cada `dias_ronda`). Sin predicción |
| `sensor_central` | Sensor central + modelo + dron que solo va cuando hay alerta |
| `drones` | Drones patrullando y midiendo + modelo + prioridad + seguimiento. **La solución** |
| `drones_celular` | Igual que `drones`, sin red: datos llegan al modelo una vez al día (hora aleatoria 7–15 h) vía `cola_sync` |
| `drones_sin_vent` | `drones` sin apagar la ventilación |

Métricas (`analisis/metricas.py`):
- **Días de anticipación** por foco: día de primeros síntomas − día de la primera alerta `alto` o confirmación en esa cama (positivo = avisamos antes).
- **Retraso de detección:** día de confirmación − día real de infección del primer caso de la cama.
- **Plantas afectadas** (latentes + síntomas + perdidas) al final y en el pico.
- **Falsas alarmas:** alertas `alto` sin infección en 7 días; incidencias `descartada`.
- **Focos no detectados:** camas con ≥ 5 plantas con síntomas nunca confirmadas a tiempo.
- **Modelo:** AUC, PR-AUC, aciertos en el top-10 diario; reglas vs. IA vs. IA solo con sensor central.
- **Costo del peor caso:** días de anticipación perdidos en `drones_celular` frente a `drones`.

Corridas: `python -m analisis.validar --semillas 30` → `data/resultados/metricas.parquet`, media + IC 95 % bootstrap + diferencias pareadas por semilla.

Gráficas (`analisis/graficas.py`, PNG 1920×1080, fondo oscuro): (1) anticipación por escenario (cajas); (2) plantas afectadas en el tiempo `actual` vs. `drones` (media ± IC); (3) ROC/PR reglas vs. IA vs. IA solo sensor central; (4) importancia de variables; (5) tabla de aciertos, falsas alarmas, no detectados; (6) anticipación red local vs. celular.

Casos donde falla (mostrarlos): periodos secos con contagio por aire; latentes que la cámara no ve; muchos focos con un solo dron por bloque.

### Fase 6 · Demo y cierre (10:30–12:00)
- `config/demo.yaml`: Bloque 1, foco latente en Nave 2 · Cama 14 el día 1; evento húmedo la noche del día 2; ventilación encendida en Nave 2.
- Secuencia en ~3 min: alerta `riesgo_7d` → dron de patrulla a prioridad → inspecciona → `confirmada` → ventilación apagada → seguimiento 3 días después → `mejora`.
- Comando para Samuel: `python -m sim.run_vivo --config config/demo.yaml --velocidad 1` (1 hora simulada por segundo).

### Entrega a Samuel
- [ ] `data/finca.db` de una temporada `drones` con todas las tablas llenas.
- [ ] `run_vivo` escribe hora a hora sin bloquear la lectura (WAL).
- [ ] Escenario `demo` con la secuencia completa en < 3 min.
- [ ] Gráficas en `data/resultados/`.

**Decisiones abiertas con Samuel (`planSamuel.md`, Fase 0):** afectan al simulador y **no se implementan hasta que estén escritas en `NOTAS.md`**. Propuestas de Samuel:

| # | Tema | Propuesta de Samuel | Impacto en `sim/` |
|---|---|---|---|
| 1 | Quién escribe `ventilacion` | Simulador = apagado automático; dashboard = cambios manuales; `motivo` distingue (`auto: incidencia #12` / `manual: agrónomo`) | Formato de `motivo` |
| 2 | ¿Ventilación automática o sugerida? | Sugerida con botón *Apagar 48 h / Mantener* | `run_vivo` debe **leer** `ventilacion` cada hora y obedecerla |
| 3 | Quién escribe `cola_sync` | Simulador escribe con `hora_recibida = NULL`; el hub la llena | `drones_celular` y `run_vivo` escriben `cola_sync` |
| 4 | Quién crea `alertas` | El simulador | Ya es así en esta guía |
| 5 | Valores de `alertas.accion` | Tabla por tipo, en `config/default.yaml` | Solo `apagar_48h` vuelve al simulador |
| 6 | Modo sin red en la demo | Interruptor *Sin red* + botón *Pasa el celular* | `run_vivo` escribe `cola_sync` también |
| 7 | Formato de `cola_sync` | `tipo ∈ {lectura, inspeccion, seguimiento}`; `payload` = JSON con las columnas de la tabla destino | Serializar así |
| 9 | Dashboard lee directo | Sí, con `hub/db.py` en solo lectura | WAL obligatorio |
| — | Índices | Pide `lecturas(corrida_id, cama_id, hora)`, `riesgo(corrida_id, dia)`, `alertas(corrida_id, hora)` | Cambio al contrato, acordado |

**Otros huecos:** las banderas `run_temporada --dias` y `run_vivo --velocidad` aparecen en el plan pero no en la lista de comandos de `CLAUDE.md`: son obligatorias.

---

## 14. Prioridades y recortes

**Si vamos tarde, cortar en este orden:**
1. Una sola enfermedad (Botrytis).
2. Batería de los drones.
3. Escenario `drones_sin_vent`.
4. Bajar a 15 semillas.

**Nunca cortar:** predicción a 7 días con IA comparada contra reglas; drones con patrulla y prioridad; seguimiento automático; escenario `drones_celular`; gráfica de anticipación con sus errores.

**Criterios del jurado:** integración tecnológica 30 %, relevancia/impacto/ética 20 %, viabilidad y escalabilidad 20 %, innovación 10 %, uso y justificación de IA 10 %, negocio y pitch 10 %. Prioridad absoluta: **que la demo funcione de punta a punta** (predicción → dron → incidencia → seguimiento → modo sin internet).

---

## 15. Guardarraíles anti-regresión

- **No** cambies el contrato por tu cuenta, ni siquiera para "mejorarlo".
- **No** crees jerarquías de clases, fábricas, registros de plugins ni capas de servicio. Funciones y, como mucho, una clase `Dron`.
- **No** agregues frameworks, ORMs ni dependencias.
- **No** optimices antes de que todo corra de punta a punta.
- **No** toques β sin volver a verificar el 5–15 % de afectadas en `sensor_central`.
- **No** separes train/test por fila ni uses semillas de prueba para ajustar nada.
- **No** uses la verdad en variables, en la base (salvo `verdad_infectada`) ni en el dashboard.
- **No** escribas umbrales, pesos ni tiempos literales en el código.
- **No** cambies firmas de funciones ya usadas por otros módulos sin actualizar a todos sus llamadores y sus pruebas.
- **No** borres ni reescribas pruebas que fallan para que pasen; arregla el código o reporta.
- **No** hagas push a `main` directamente; rama `santiago/<tema>` y merge cuando pase `pytest`.

---

## 16. Comandos (Windows · PowerShell)

```powershell
# Entorno
python -m venv .venv
.venv\Scripts\Activate.ps1          # si sale "running scripts is disabled": Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt

# Simulación y modelo
python -m sim.run_temporada --escenario drones --semilla 7          # temporada completa → data\finca.db
python -m sim.run_temporada --dias 1                                # prueba rápida (Fase 1)
python -m sim.run_vivo --config config/demo.yaml --velocidad 1      # demo en vivo, 1 h simulada por segundo
python -m prediccion.entrenar                                       # entrena y compara reglas vs. IA
python -m analisis.validar --semillas 30                            # escenarios, métricas y gráficas → data\resultados\

# Lado de Samuel (solo para verificar integración)
python -m hub.api
streamlit run dashboard/app.py

# Pruebas
pytest -q

# Git
git switch -c santiago/<tema>
git add <archivos>
git commit -m "sim: <descripción>"
git switch main; git merge santiago/<tema>; git push origin main   # solo si pytest pasa
```
