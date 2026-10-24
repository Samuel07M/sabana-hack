# Prompt · Prototipo 1 del dashboard (datos simulados)

> Copia todo lo que está debajo de la línea en Claude Code, abierto en la raíz del repo `sabana-hack`.

---

## Rol y contexto

Eres el desarrollador del **hub local y el dashboard** de *Berry Good Idea* (Sabana Hack 2026). Antes de escribir una sola línea:

1. Lee completos `CLAUDE.md`, `planSamuel.md` y `planSantiago.md`.
2. Respeta todo lo que dice `CLAUDE.md`: contrato de datos, nomenclatura **Bloque · Nave · Cama**, SQLite, cero dependencias de internet en ejecución, `numpy.random.default_rng(semilla)`, parámetros en YAML con comentario `# fuente:`, funciones pequeñas con docstring de una línea, Windows + PowerShell, `pathlib.Path` y `encoding="utf-8"`.
3. Solo puedes crear o editar archivos en `hub/`, `dashboard/`, `tests/` (los del hub/dashboard), `.streamlit/`, `NOTAS.md` y los dos archivos compartidos indicados abajo. **No toques `sim/`, `prediccion/` ni `analisis/`.**
4. Trabaja directamente en la rama `main`.

## Objetivo

Construir un **primer prototipo funcional, moderno e intuitivo** del dashboard en Streamlit que funcione hoy **sin el simulador de Santiago**, alimentado por un generador de datos falsos que cumple el contrato al pie de la letra y que se comporta como se comportará el sistema real: clima por cama, riesgo diario a 7 días, drones patrullando, incidencias con su ciclo de vida, seguimientos automáticos, alertas, ventilación y cola de sincronización sin red.

Cuando Santiago entregue `data/finca.db`, el dashboard debe funcionar con ella **sin cambiar código**, solo cambiando la variable de entorno `FINCA_DB`.

El usuario final es un **agrónomo o trabajador de finca**, no un ingeniero. Tiene que entender en 5 segundos: dónde está el riesgo, qué encontró el dron y qué tiene que hacer.

---

## Paso 0 · Archivos compartidos que todavía no existen

- **`contrato/schema.sql`:** si no existe, créalo copiando **exactamente** el bloque SQL de `CLAUDE.md` (mismas tablas, columnas, tipos y comentarios). No inventes columnas. Al final añade solo índices (no cambian el contrato):
  ```sql
  CREATE INDEX IF NOT EXISTS ix_lecturas ON lecturas(corrida_id, cama_id, hora);
  CREATE INDEX IF NOT EXISTS ix_riesgo   ON riesgo(corrida_id, dia);
  CREATE INDEX IF NOT EXISTS ix_alertas  ON alertas(corrida_id, hora);
  CREATE INDEX IF NOT EXISTS ix_drones   ON drones(corrida_id, dron_id, hora);
  ```
  Usa `CREATE TABLE IF NOT EXISTS`. Deja una nota en `NOTAS.md`: “Samuel creó `contrato/schema.sql` desde `CLAUDE.md` + índices; Santiago debe revisarlo”.
- **`config/default.yaml`:** es de Santiago y de Samuel. Si no existe, **no lo crees**. Crea `config/dashboard.yaml` (mío) y lee la geometría y los umbrales de `config/default.yaml` si existe; si no, usa los valores de respaldo de `config/dashboard.yaml`, que son los mismos de `planSantiago.md`.

## Paso 1 · `config/dashboard.yaml`

Todo número que use el hub o el dashboard vive aquí con su `# fuente:`. Mínimo:

```yaml
db_por_defecto: "data/finca.db"          # fuente: CLAUDE.md
refresco_segundos: 2                     # fuente: supuesto (demo)
respaldo:                                # solo si no existe config/default.yaml
  geometria: {bloques: 4, naves_por_bloque: 6, camas_por_nave: 12, plantas_por_cama: 40}  # fuente: planSantiago.md
  riesgo: {umbral_alto: 0.6, umbral_medio: 0.3}                                         # fuente: CLAUDE.md
  clima: {umbral_mojado_hr: 90.0}                                                       # fuente: planSantiago.md
  drones: {min_por_cama: 6, dias_revisita: 3}                                           # fuente: planSantiago.md
acciones:                                # fuente: propuesta planSamuel.md Fase 0 punto 5 (pendiente de acordar)
  riesgo_7d: [inspeccion_priorizada, monitorear, ignorar]
  confirmacion: [tratamiento_programado, tratamiento_aplicado]
  seguimiento: [continuar_seguimiento, retratar]
  ventilacion: [apagar_48h, mantener_encendida]
  descartada: [entendido]
mock:
  semilla: 7                             # fuente: supuesto
  dias: 21                               # fuente: supuesto (alcanza para 2 ciclos de revisita y cierres)
  inicio: "2026-11-01T00:00:00"          # fuente: planSantiago.md
  ventilacion_naves: [2, 3, 5]           # fuente: supuesto (qué naves tienen ventilación)
```

Las acciones y los puntos marcados “pendiente de acordar” vienen de la Fase 0 de `planSamuel.md`. Implementa la **propuesta** de esa tabla, aislada en una sola función o en el YAML, con un comentario `# TODO Fase 0 punto N` para cambiarla fácil si Santiago decide otra cosa.

---

## Paso 2 · Capa de datos `hub/`

### `hub/config.py`
Carga `config/dashboard.yaml` y, si existe, `config/default.yaml` (con `encoding="utf-8"`). Expone geometría, umbrales y acciones. Ruta de la base: `os.environ.get("FINCA_DB")` o `db_por_defecto`.

### `hub/ubicacion.py`
- `cama_id(bloque, nave, cama) -> "B1-N2-C14"`, `partes(cama_id) -> (1, 2, 14)`.
- `nave_de_cama(cama)` con numeración continua dentro del bloque (cama 14 → nave 2; cama 61 → nave 6).
- `legible(cama_id) -> "Bloque 1 · Nave 2 · Cama 14"`.

### `hub/tiempo.py`
- `dia(hora) = hora // 24`; `a_fecha(hora, inicio_sim)`; `etiqueta(hora) -> "Día 3 · 14:00"`.
- `drones.hora` es `REAL`: soporta fracciones (muestra minutos).

### `hub/db.py`
- Lectura **solo lectura**: `sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False)`.
- Escritura (solo para `alertas.estado`, `alertas.accion`, `ventilacion` y `cola_sync.hora_recibida`): conexión aparte con `PRAGMA busy_timeout=5000`.
- Todas las funciones reciben `corrida_id` y devuelven `pandas.DataFrame`:
  `corridas()`, `camas()`, `hora_actual()`, `riesgo_dia(dia)`, `riesgo_cama(cama_id)`, `lecturas_cama(cama_id, desde, hasta)`, `ultima_lectura_por_cama(hasta)`, `alertas(filtros)`, `incidencias(filtros)`, `seguimientos(incidencia_id)`, `drones_actual()`, `recorrido_dron(dron_id, desde)`, `ventilacion_actual()`, `cola_pendiente()`.
- `incidencias()` **nunca** selecciona `verdad_infectada`: lista las columnas explícitamente, sin `SELECT *`.
- Todas las consultas aceptan `hasta_hora` para el modo sin red (ver Paso 5) y para el reloj de reproducción.

### `hub/alertas.py`
- `marcar_vista(alerta_id)`, `resolver(alerta_id, accion)`.
- Transiciones solo hacia adelante: `nueva → vista → resuelta`. Rechaza `accion` que no esté en la lista de su `tipo`.

### `hub/ventilacion.py`
- `estado_actual()` por (bloque, nave); `cambiar(bloque, nave, estado, hora, motivo="manual: agrónomo")` inserta una fila nueva (no actualiza las anteriores: es historial).

### `hub/celular.py`
- `pendientes()`; `sincronizar(hora)` llena `hora_recibida` de todo lo pendiente con `hora_generada ≤ hora`, sin duplicar.

---

## Paso 3 · Generador de datos falsos `hub/mock.py`

Comando: `python -m hub.mock` (crea `data/mock.db`) y `python -m hub.mock --vivo` (escribe una hora simulada por segundo, en modo WAL, para probar el refresco). Usa `contrato/schema.sql` para crear las tablas. Una sola `rng = numpy.random.default_rng(semilla)`.

Los datos deben **parecer los del sistema real**, no ruido. Reglas:

**Corridas:** inserta 3: `mock` (escenario `drones`, modo `temporada`), `mock-celular` (escenario `drones_celular`) y `demo` (escenario `demo`, modo `vivo`, con la historia guionada de abajo).

**Camas:** geometría completa; `es_borde = 1` en la primera y última cama de cada nave; `tiene_ventilacion = 1` en las naves de `mock.ventilacion_naves`.

**Lecturas (por hora):**
- `T = 18 + 6·sin(2π(h−9)/24) + ruido`; `HR = 78 − 10·sin(2π(h−9)/24) + 4·es_borde + ruido`, recortada a [30, 100]. Unos pocos eventos húmedos de 6–18 h que suben la HR del bloque.
- En `mock`, cada cama tiene lectura solo cuando el dron pasa (`fuente='dron:B{n}'`) más el sensor central del bloque cada hora (`fuente='sensor_fijo'`). Así se ve la diferencia de cobertura.

**Riesgo (06:00 de cada día):** `prob_ia_7d` coherente con la HR de las últimas 72 h, con el borde y con incidencias confirmadas cercanas en la misma nave; `riesgo_reglas` parecido pero más ruidoso. `nivel` según los umbrales. Pocas camas en `alto` por día (≈2–5 % de las camas).

**Drones (uno por bloque, `dron_id='B{n}'`):** patrulla 1 → 72 → 1 a `min_por_cama` minutos por cama, con una fila en `drones` por cambio de cama. Si una cama del bloque está en `alto` y no se visitó en 24 h, pasa a `prioridad`, va allí, `inspeccionando` y luego vuelve a `patrulla`. Batería que baja y un ciclo de `carga`.

**Incidencias:** que existan en **todos** los estados (`sospecha`, `confirmada`, `en_tratamiento`, `en_seguimiento`, `cerrada`, `descartada`), con `origen` `prediccion` y `patrulla`, posición 1–40, confianza 0.6–0.95 y plantas afectadas 1–8. `verdad_infectada` lleno (para probar que no se muestra).

**Seguimientos:** cada `dias_revisita` días tras el tratamiento, resultados `empeora` / `igual` / `mejora` / `limpia`. Dos `limpia` seguidos cierran la incidencia; un `empeora` la devuelve a `confirmada`.

**Alertas:** de los 5 tipos y 3 severidades, con estos textos exactos (vienen de `planSantiago.md`):
- `riesgo_7d` (`advertencia`): `B1 · Nave 2 · Cama 14: alto riesgo de Botrytis en los próximos 7 días (prob. 0.74). HR > 90 % durante 15 h.`
- `confirmacion` (`critica`): `Botrytis confirmada · B1 · Nave 2 · Cama 14 · posición 22. 3 plantas afectadas (confianza 0.88).`
- `descartada` (`info`), `seguimiento` (`info` o `advertencia` si empeora), `ventilacion` (`advertencia`).
- Algunas `nueva`, otras `vista` y `resuelta` con acción.

**Ventilación:** estado inicial `encendida` en las naves con ventilación; apagada 48 h tras cada confirmación en esa nave (`motivo='auto: incidencia #N'`), luego encendida de nuevo.

**Cola de sincronización (`mock-celular`):** cada lectura, inspección y seguimiento del dron también va a `cola_sync` con `origen='dron:B{n}'`, `tipo ∈ {lectura, inspeccion, seguimiento}` y `payload` en JSON con las columnas de la tabla destino. Una vez al día, a una hora aleatoria entre 7 y 15, todo lo pendiente recibe `hora_recibida` (como si pasara el celular). Deja pendientes las últimas horas para que se vea la cola.

**Historia guionada en la corrida `demo`** (es la secuencia de la demo de `planSantiago.md`; el dashboard tiene que contarla sola):
1. Día 0: Bloque 1 tranquilo, dron en patrulla, ventilación de la Nave 2 encendida.
2. Noche del día 2: evento húmedo en el Bloque 1 (HR > 90 % varias horas).
3. Día 3, 06:00: `B1-N2-C14` pasa a `alto` → alerta `riesgo_7d`.
4. El dron B1 cambia a `prioridad`, va a la cama 14, `inspeccionando`.
5. Incidencia `sospecha` → `confirmada` (posición 22, 3 plantas, confianza 0.88) → alerta `critica`.
6. Ventilación Nave 2 → `apagada` + alerta `ventilacion`.
7. 6 h después → `en_tratamiento`.
8. 3 días después → seguimiento `mejora`; 3 días más → `limpia`; otra → `limpia` → `cerrada`.

---

## Paso 4 · Dashboard `dashboard/app.py` (Streamlit)

Comprueba la versión instalada de Streamlit (`streamlit --version`) y usa sus funciones nativas cuando existan (`st.fragment(run_every=...)`, `st.dialog`, `st.toast`, `st.pills`/`st.segmented_control`, `st.plotly_chart(..., on_select="rerun")`). Si alguna no existe en la versión instalada, usa la alternativa más simple y anótalo en `NOTAS.md`. Fija las versiones en `requirements.txt` con lo instalado.

### Diseño visual: moderno, limpio y legible en un proyector

- **Tema oscuro** en `.streamlit/config.toml` (las gráficas de Santiago vienen con fondo oscuro):
  ```toml
  [server]
  headless = true
  [browser]
  gatherUsageStats = false
  [theme]
  base = "dark"
  primaryColor = "#7C9CFF"          # azul arándano
  backgroundColor = "#0F1420"
  secondaryBackgroundColor = "#182033"
  textColor = "#E6EAF2"
  ```
- **Paleta semántica única**, definida una vez en `dashboard/estilo.py` y usada en todas partes:
  - riesgo `bajo` #2E7D5B (verde apagado), `medio` #D9A441 (ámbar), `alto` #E5484D (rojo);
  - severidad `info` #5B8DEF, `advertencia` #D9A441, `critica` #E5484D;
  - dron #7C9CFF; ventilación apagada #8A94A6.
  - El color **nunca** va solo: siempre acompañado de texto o icono (accesibilidad y proyector).
- **CSS propio mínimo** inyectado con `st.markdown(..., unsafe_allow_html=True)` desde `dashboard/estilo.py`: tarjetas con bordes redondeados (12 px), sombra suave, espaciado generoso, números grandes en los KPIs, chips de estado con fondo translúcido del color semántico. Oculta el menú y el pie de Streamlit.
- **Tipografía:** la que trae Streamlit o la pila del sistema (`system-ui, "Segoe UI", sans-serif`). **Prohibido** Google Fonts, CDNs o cualquier recurso remoto.
- **Iconos:** emoji Unicode o los símbolos Material que trae Streamlit (`:material/...:`). Nada externo.
- Todo el texto de la interfaz en **español**, con lenguaje de finca (“Cama”, “Nave”, “Bloque”, “Dron”, “Tratamiento”), sin jerga técnica (“prob_ia_7d” se muestra como “Probabilidad de infección en 7 días”).
- `layout="wide"`, título de página y favicon con emoji 🫐.

### Estructura de la pantalla

**Barra superior (siempre visible)**
- Logo/título: “🫐 Berry Good Idea · Monitoreo de Botrytis”.
- Selector de corrida (muestra escenario).
- Reloj simulado grande: `Día 3 · 14:00` y la fecha real debajo.
- Indicador de red con chip: 🟢 **Red local** o 🟠 **Sin red · última sincronización hace X h**.
- 4 KPIs en tarjetas: *Alertas críticas nuevas*, *Incidencias abiertas*, *Camas en riesgo alto hoy*, *Naves con ventilación apagada*. Cada uno con su delta frente al día anterior.

**Pestañas** (en este orden): 🗺️ Finca · 🔔 Alertas · 🩺 Incidencias · 🌬️ Ventilación · 📶 Sincronización · 📊 Evidencia.

#### 🗺️ Finca (la pantalla principal de la demo)
- Selector de bloque como píldoras (B1–B4), cada una con un punto rojo si el bloque tiene alertas críticas nuevas.
- **Mapa del bloque**: cuadrícula de **6 filas (naves) × 12 columnas (camas)** hecha con Plotly (heatmap + anotaciones) — **no** `st.map`, `pydeck` ni nada con teselas.
  - Cada celda muestra el número de cama real (nave 2 → 13–24) y se colorea por nivel de riesgo del día.
  - Encima: 🛸 en la cama donde está el dron (con su estado en el tooltip), ⚠️ si hay incidencia abierta (con estado), borde más grueso en camas de borde.
  - A la izquierda de cada fila: “Nave N” y el estado de la ventilación (🌬️ encendida / ⏸️ apagada / — sin ventilación).
  - Tooltip: ubicación legible, probabilidad, nivel, última lectura de T y HR, fuente y hace cuánto.
  - Leyenda clara debajo.
  - Clic en una celda → abre el detalle de esa cama. Respaldo si el clic falla: selectores *Nave* + *Cama*.
- **Tarjeta del dron del bloque**: estado (patrulla / prioridad / inspeccionando / carga) como chip, cama actual, batería con barra, próximas camas prioritarias.
- **Detalle de cama** (en `st.dialog` o columna derecha):
  - Título `Bloque 1 · Nave 2 · Cama 14` y chip de nivel.
  - Probabilidad de infección a 7 días (número grande) y riesgo por reglas al lado, con una frase de explicación generada a partir de los datos (“HR sobre 90 % durante 15 h en las últimas 72 h”).
  - Gráfica de T y HR de las últimas 72 h, con línea punteada del umbral de mojado y puntos diferenciados por fuente (`sensor_fijo` vs dron). Evolución del riesgo de los últimos días.
  - Incidencias de la cama con su **línea de tiempo** (creada → confirmada → tratamiento → seguimientos → cerrada).
  - Última visita del dron.

#### 🔔 Alertas
- Bandeja tipo correo: tarjetas ordenadas por severidad y hora; chip de severidad y tipo, título, mensaje, ubicación legible, hora simulada.
- Filtros en píldoras: severidad, tipo, estado; selector de bloque/nave.
- Las `nueva` resaltadas; al expandir una alerta pasa a `vista`.
- Botones de acción según el tipo (desde `config/dashboard.yaml`); al elegir una, la alerta pasa a `resuelta` con esa acción y se muestra un `st.toast` de confirmación.
- Botón “Ver en el mapa” que lleva a la cama.
- `st.toast` cuando entra una alerta `critica` nueva durante el refresco.

#### 🩺 Incidencias
- Embudo o barra horizontal por estado.
- Tabla con ubicación legible, posición, origen, estado (chip), confianza, plantas afectadas, horas creada/confirmada/cerrada (en formato `Día N · HH:00`). Valores NULL como “—”.
- Al seleccionar una: línea de tiempo con los seguimientos (resultado con color e icono: ↗ empeora, → igual, ↘ mejora, ✓ limpia), dron, plantas y nota. Un texto destaca: “Registrado automáticamente por el dron”.
- Exportar CSV.

#### 🌬️ Ventilación
- Tarjeta por nave con ventilación: estado, desde cuándo, motivo (auto o manual).
- Botones *Apagar 48 h* / *Encender* que escriben en `ventilacion` (`# TODO Fase 0 punto 2`).
- Recuadro corto explicando el dilema: apagar sube la humedad pero corta el transporte de esporas.
- Historial en una línea de tiempo.

#### 📶 Sincronización
- Interruptor **Red local / Sin red**.
- En *Sin red*: todo el dashboard (mapa, alertas, incidencias) filtra con `hora_recibida ≤ hora_actual`; lo pendiente se ve atenuado con el texto “Guardado en el dron, sin sincronizar”.
- Botón grande **📱 Pasa el celular** → `hub.celular.sincronizar()` y el dashboard se pone al día con un `st.toast`.
- Métricas: pendientes por dron, antigüedad del dato más viejo, última sincronización. Diagrama simple de los 3 niveles (red local / celular / internet como respaldo).

#### 📊 Evidencia
- Muestra los PNG de `data/resultados/` si existen, con título y una frase de lectura cada uno; si existe `data/resultados/metricas.parquet`, tabla resumen por escenario. Si no hay nada: estado vacío amable “Pendiente de validación del simulador”.

### Comportamiento en vivo
- El reloj, el mapa, la tarjeta del dron, los KPIs y la bandeja de alertas se refrescan dentro de `st.fragment(run_every=refresco_segundos)`, sin recargar la página entera.
- Consultas con `st.cache_data(ttl=refresco_segundos)`.
- **Control de reproducción** para corridas de temporada: deslizador de hora simulada + botones ⏮ ⏯ ⏭, para recorrer la temporada como si fuera en vivo (todas las consultas usan `hasta_hora`).
- Estados vacíos y errores amables (base no encontrada → mensaje con el comando para generarla).

---

## Paso 5 · Pruebas (`tests/`, `pytest -q`)

- `test_ubicacion.py`: ida y vuelta de identificadores; cama 14 → nave 2; cama 61 → nave 6.
- `test_tiempo.py`: hora → día y etiqueta; horas fraccionarias.
- `test_mock.py`: `data/mock.db` usa el esquema del contrato; cubre todos los estados de incidencia, los 5 tipos de alerta, las 3 severidades, los 4 estados de dron y los 4 resultados de seguimiento; la historia `demo` contiene la secuencia completa en orden.
- `test_alertas.py`: transiciones válidas e inválidas; acción no permitida rechazada.
- `test_privacidad.py`: ninguna función de `hub/db.py` devuelve la columna `verdad_infectada`.
- `test_celular.py`: sincronizar llena `hora_recibida` y no duplica.

Usa una base temporal (`tmp_path`) en las pruebas, nunca `data/`.

---

## Paso 6 · Cómo se corre (añádelo al final de `NOTAS.md`)

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m hub.mock                       # crea data\mock.db
$env:FINCA_DB = "data\mock.db"
streamlit run dashboard/app.py
# en otra terminal, para probar el refresco en vivo:
python -m hub.mock --vivo
pytest -q
```

---

## Criterios de aceptación (verifícalos tú mismo antes de terminar)

1. `python -m hub.mock` y `streamlit run dashboard/app.py` funcionan **con el wifi apagado** y sin errores en la consola.
2. En la corrida `demo`, recorriendo la reproducción, se ve en orden: riesgo alto en la Cama 14 → dron en prioridad → inspección → confirmada con toast crítico → ventilación de la Nave 2 apagada → tratamiento → seguimientos → cerrada.
3. Con `python -m hub.mock --vivo` el reloj avanza, el dron se mueve y aparecen alertas sin recargar la página.
4. Resolver una alerta con una acción la deja en `resuelta` en la base; apagar una nave escribe una fila nueva en `ventilacion`.
5. En *Sin red* desaparece lo no sincronizado; tras *Pasa el celular* reaparece.
6. `verdad_infectada` no aparece en ninguna pantalla ni DataFrame de la interfaz.
7. Ninguna petición de red sale del navegador ni del servidor (revisa que no haya URLs `http` en el código del dashboard salvo `localhost`).
8. `pytest -q` en verde.
9. Todas las ubicaciones en pantalla se leen como `Bloque · Nave · Cama`.

## Entrega

- Commits pequeños en español directamente en `main` (`hub: generador de datos falsos`, `dashboard: mapa por bloque`, …), con `pytest -q` en verde antes de cada push.
- Al terminar, resume en `NOTAS.md`: qué funciona, qué decisiones de la Fase 0 asumiste con la propuesta por defecto (con su `TODO`), qué funciones de Streamlit no estaban disponibles y qué necesitas de Santiago.
- Toma 4 capturas (Finca, detalle de cama, Alertas, Sincronización) y guárdalas en `docs/capturas/`.
