# planSamuel.md · Hub local, dashboard y sistema de alertas

Dueño: **Samuel**. Carpetas: `hub/`, `dashboard/`, `tests/` (los míos).
Lee primero `CLAUDE.md` (contrato de datos y convenciones) y `planSantiago.md` (qué datos llegan y cuándo).

**Objetivo:** que un agrónomo, sin internet, vea en una sola pantalla **dónde** está el riesgo (Bloque · Nave · Cama), **qué** encontró el dron, **qué hacer** y **qué pasó después**, y que la demo muestre el flujo completo: predicción → dron → incidencia → seguimiento → ventilación → modo sin red.

**Regla de oro:** el dashboard nunca espera a Santiago. Trabajo contra datos falsos que cumplen el contrato y cambio a los reales en cuanto lleguen.

**Lo que ya está fijado en el repo (no se discute):**
- Interfaz: **Streamlit** (`streamlit run dashboard/app.py`). API local: `python -m hub.api`.
- Base: **SQLite** en `data/finca.db`, en modo WAL. El simulador escribe; yo leo.
- Yo solo escribo: `alertas.estado`, `alertas.accion`, `ventilacion` y `cola_sync` (según `CLAUDE.md`).
- Ubicaciones siempre como `Bloque · Nave · Cama`, nunca x/y.
- Nada en ejecución depende de internet.
- `incidencias.verdad_infectada` **no se muestra nunca**.

---

## Fase 0 · Decisiones abiertas con Santiago (22:00–22:30)

Los documentos se contradicen o no definen estos puntos. **No empiezo a codificar la parte afectada hasta cerrarlos.** Anoto la respuesta en `NOTAS.md`.

| # | Pregunta | Por qué importa | Lo que propongo |
|---|---|---|---|
| 1 | ¿Quién escribe `ventilacion`? `CLAUDE.md` dice que el hub/dashboard; `planSantiago.md` dice que el simulador. | Si los dos escriben, hay filas duplicadas o contradictorias. | El simulador escribe el apagado automático; el dashboard escribe solo cuando el agrónomo cambia algo a mano. Columna `motivo` distingue (`auto: incidencia #12` / `manual: agrónomo`). |
| 2 | ¿La ventilación se **apaga sola** (plan de Santiago) o se **sugiere** y el agrónomo decide (`CLAUDE.md`)? | Define si la alerta `ventilacion` tiene botón de acción o es informativa. | Se sugiere con botón *Apagar 48 h / Mantener*; en la demo el agrónomo pulsa *Apagar*. Requiere que `run_vivo` lea `ventilacion` cada hora. |
| 3 | ¿Quién escribe `cola_sync`? Ambos documentos lo reclaman. | Es la base del modo sin red. | El simulador escribe lo que genera el dron (`hora_recibida = NULL`); el hub (simulación del celular) llena `hora_recibida`. |
| 4 | ¿Quién crea las filas de `alertas`? `planSantiago.md` las crea en el simulador pero no lista `alertas` entre sus tablas. | Si nadie lo asume, no hay alertas. | Las crea el simulador (tiene el contexto: prob., HR, horas de mojado). Yo solo cambio `estado` y `accion`. |
| 5 | ¿Qué opciones de `accion` puede elegir el agrónomo y alguna vuelve al simulador? | El campo existe pero no tiene valores definidos. | Tabla de acciones abajo (Fase 3). Ninguna cambia el simulador salvo la de ventilación (punto 2). |
| 6 | ¿El modo sin red (nivel 2) se muestra en la demo en vivo? La secuencia de `config/demo.yaml` no lo incluye. | `CLAUDE.md` lo pone como parte del flujo que debe funcionar de punta a punta. | Interruptor en el dashboard *Red local / Sin red*: en *Sin red* solo se ve lo que ya llegó por `cola_sync`; botón *Pasa el celular* sincroniza. Requiere que `run_vivo` también escriba `cola_sync`. |
| 7 | Formato de `cola_sync.tipo` y `payload`. | Tengo que poder decodificarlo. | `tipo ∈ {lectura, inspeccion, seguimiento}`; `payload` = JSON con las mismas columnas de la tabla destino. |
| 8 | `corridas.escenario` lista 4 valores, pero `planSantiago.md` usa también `actual` y `drones_sin_vent`. | Filtros y etiquetas del selector de corrida. | Añadir los dos al comentario del contrato. |
| 9 | ¿El dashboard lee SQLite directo o pasa por `hub.api`? | Define si la API es imprescindible o recortable. | El dashboard lee con `hub/db.py` (directo, solo lectura). `hub.api` expone las mismas funciones por HTTP para otros dispositivos en la red local. |
| 10 | ¿Qué pasa con la `confianza` y `plantas_afectadas` de una incidencia en `sospecha`? | Saber si se muestran vacíos. | Se muestran como “—” si son NULL. |

También confirmar con Santiago los **horarios de entrega** que dependen de él (de su plan):
- 23:30 → `data/finca.db` con `camas` llena y tablas vacías.
- ~08:00 → `finca.db` de una temporada `drones` con todas las tablas llenas.
- ~10:30 → `run_vivo` con `config/demo.yaml` y gráficas en `data/resultados/`.

**Listo cuando:** las 10 preguntas tienen respuesta escrita en `NOTAS.md` y los cambios al contrato están acordados.

---

## Fase 1 · Base del lado del hub (22:30–00:00)

### 1.1 Esqueleto
```
hub/
  __init__.py
  db.py          # conexión y consultas (única puerta a la base)
  tiempo.py      # hora simulada ↔ fecha/hora legible
  ubicacion.py   # 'B1-N2-C14' ↔ (1, 2, 14) ↔ 'Bloque 1 · Nave 2 · Cama 14'
  alertas.py     # ciclo de vida de alertas (estado, acción)
  ventilacion.py # leer estado actual, registrar cambio manual
  celular.py     # simulación del celular (nivel 2)
  mock.py        # datos falsos que cumplen el contrato
  api.py         # API local
dashboard/
  app.py
  componentes/   # mapa, alertas, incidencias, ventilacion, sync, evidencia
.streamlit/config.toml
```

### 1.2 `hub/db.py`
- Conexión de **solo lectura** para consultas: `sqlite3.connect("file:data/finca.db?mode=ro", uri=True)`.
- Conexión de escritura aparte, usada solo por `alertas.py`, `ventilacion.py` y `celular.py`, con `PRAGMA busy_timeout` para no chocar con el simulador que escribe en WAL.
- Funciones (todas reciben `corrida_id`):
  - `corridas()`, `camas()`
  - `hora_actual(corrida)` = máx. `hora` en `lecturas`/`drones`.
  - `riesgo_dia(corrida, dia)` → nivel, `prob_ia_7d`, `riesgo_reglas` por cama.
  - `lecturas_cama(corrida, cama_id, desde, hasta)`.
  - `alertas(corrida, filtros)`, `incidencias(corrida, filtros)` (**sin** `verdad_infectada`), `seguimientos(incidencia_id)`.
  - `drones_actual(corrida)` → última fila por `dron_id`.
  - `ventilacion_actual(corrida)` → último estado por `(bloque, nave)`.
  - `cola_pendiente(corrida)`.
- Todas devuelven `pandas.DataFrame`.

### 1.3 `hub/tiempo.py` y `hub/ubicacion.py`
- `hora → datetime` con `corridas.inicio_sim`; `dia = hora // 24`; formato en pantalla: `Día 3 · 14:00` y fecha real.
- Conversión de identificadores en ambos sentidos. Pruebas en `tests/test_ubicacion.py` (ej. cama 14 → nave 2; cama 61 → nave 6).

### 1.4 `hub/mock.py` (lo más importante de esta fase)
- Crea `data/mock.db` usando **`contrato/schema.sql` tal cual** (si cambia el contrato, el mock cambia solo).
- Geometría leída de `config/default.yaml` (no números fijos).
- Llena una corrida `mock` con: lecturas por cama, riesgo diario con algunas camas `alto`, incidencias en **todos** los estados, seguimientos con los 4 resultados, alertas de los 5 tipos y 3 severidades, drones moviéndose, una nave con ventilación apagada, filas en `cola_sync` con y sin `hora_recibida`.
- Modo `--vivo`: añade una hora por segundo para probar el refresco.
- Usa `numpy.random.default_rng(semilla)`.

### 1.5 Configuración
- `.streamlit/config.toml`: `server.headless = true`, `browser.gatherUsageStats = false`, tema oscuro (las gráficas de Santiago vienen con fondo oscuro).
- Ruta de la base por variable de entorno (`FINCA_DB`) con valor por defecto `data/finca.db`, para cambiar entre mock y real sin tocar código.
- Fijar versiones en `requirements.txt` con lo instalado (`pip freeze`), coordinado con Santiago (el archivo es compartido).

**Listo cuando:** `python -m hub.mock` crea `data/mock.db` y `pytest -q` pasa.

---

## Fase 2 · Dashboard: vista principal (00:00–02:30)

Una página, pensada para la demo en pantalla grande y para un agrónomo sin entrenamiento.

### 2.1 Barra superior (siempre visible)
- Selector de corrida (`corridas`), escenario y semilla.
- Reloj simulado: `Día N · HH:00` + fecha.
- Indicador de red: **Red local** (verde) / **Sin red · última sincronización hace X h** (ámbar). Ver Fase 4.
- Contadores: alertas nuevas críticas, incidencias abiertas, camas en riesgo alto.

### 2.2 Mapa de la finca (sin mapas externos)
- Selector de bloque (1–4).
- Cuadrícula **6 naves (filas) × 12 camas (columnas)**, cada celda rotulada con el número de cama real (nave 2 = 13–24).
- Color por `nivel` de riesgo del día (`bajo` / `medio` / `alto`), con texto además del color (accesible y legible en proyector).
- Marcas sobre la celda: incidencia abierta (con su estado), dron actual del bloque (con su estado: patrulla / prioridad / inspeccionando / carga), cama de borde.
- Al lado de cada nave: estado de la ventilación (`encendida` / `apagada`) si `tiene_ventilacion = 1`.
- Hecho con Plotly (heatmap + anotaciones) o con HTML/CSS propio. **No usar `st.map` ni pydeck**: piden teselas de internet.
- Clic en una celda → abre el detalle de la cama. Si el clic sobre el gráfico da problemas, un selector `Nave` + `Cama` como respaldo.

### 2.3 Detalle de cama (panel lateral)
- Título: `Bloque 1 · Nave 2 · Cama 14`.
- Riesgo: `prob_ia_7d`, `riesgo_reglas`, nivel, y evolución de los últimos días.
- Clima: T y HR de las últimas 72 h desde `lecturas`, con línea del umbral de mojado (`umbral_mojado_hr` de `config/default.yaml`) y la **fuente** de cada lectura (`sensor_fijo` vs `dron:B1`). Esto muestra en pantalla por qué el dron reemplaza al sensor central.
- Incidencias de la cama y su línea de tiempo (creada → confirmada → tratamiento → seguimientos → cerrada).
- Última visita del dron.

### 2.4 Refresco
- Partes que cambian en vivo (reloj, mapa, alertas, dron) dentro de un `st.fragment` con refresco periódico (ej. cada 1–2 s, en `config`), para no recargar la página entera.
- Consultas cacheadas con TTL corto.

**Listo cuando:** contra `mock.db` en modo `--vivo`, el dron se mueve, el reloj avanza y los colores cambian sin recargar la página.

---

## Fase 3 · Sistema de alertas e incidencias (02:30–03:30 y 06:30–07:30)

### 3.1 Bandeja de alertas
- Lista ordenada por severidad (`critica` > `advertencia` > `info`) y luego por hora.
- Filtros: severidad, tipo, estado, bloque/nave.
- Cada alerta muestra `titulo`, `mensaje`, ubicación legible, hora simulada y, si tiene `incidencia_id`, enlace al detalle.
- Alertas nuevas resaltadas; al abrirla pasa a `vista` (`hub/alertas.py`).
- Aviso emergente (`st.toast`) cuando entra una `critica` nueva, para que en la demo se note el momento.

### 3.2 Ciclo de vida (`hub/alertas.py`)
- `nueva → vista → resuelta`. Solo hacia adelante. Prueba en `tests/test_alertas.py`.
- Al resolver, el agrónomo elige una `accion` (valores acordados en Fase 0, punto 5). Propuesta:

| tipo | acciones |
|---|---|
| `riesgo_7d` | `inspeccion_priorizada`, `monitorear`, `ignorar` |
| `confirmacion` | `tratamiento_programado`, `tratamiento_aplicado` |
| `seguimiento` | `continuar_seguimiento`, `retratar` |
| `ventilacion` | `apagar_48h`, `mantener_encendida` |
| `descartada` | `entendido` |

- Guardar estas listas en `config/default.yaml` (nada de valores fijos en el código).

### 3.3 Vista de incidencias
- Tabla: ubicación, posición, origen (`prediccion` / `patrulla`), estado, confianza, plantas afectadas, horas creada/confirmada/cerrada.
- Embudo por estado (`sospecha`, `confirmada`, `en_tratamiento`, `en_seguimiento`, `cerrada`, `descartada`).
- Detalle: línea de tiempo con los `seguimientos` (resultado, plantas afectadas, nota, dron). Esto es lo que demuestra el **registro automático**.
- Exportar a CSV (para el agrónomo; también sirve para mostrar que queda historial).
- Prueba que `verdad_infectada` no aparece en ningún DataFrame que llega a la interfaz.

### 3.4 Panel de ventilación
- Estado actual por nave con ventilación, último cambio y motivo.
- Si se acordó que es sugerencia (Fase 0, punto 2): botones *Apagar 48 h* / *Mantener*, que escriben en `ventilacion` con motivo `manual`.
- Mensaje explicativo corto del dilema: apagar sube la humedad, pero corta el transporte de esporas.

**Listo cuando:** contra `mock.db` puedo pasar una alerta de `nueva` a `resuelta` con acción, ver una incidencia con todos sus seguimientos y apagar la ventilación de una nave.

---

## Descanso (03:30–06:30)

Antes de parar: subir rama `samuel/dashboard`, dejar en `NOTAS.md` qué funciona y qué espera de Santiago.

---

## Fase 4 · Modo sin internet (07:30–08:30)

### 4.1 Nivel 1 (red local)
- `python -m hub.api` escucha en la red local (no solo en `localhost`) y sirve: `/corridas`, `/riesgo`, `/alertas`, `/incidencias`, `/drones`, `/ventilacion`, `/cola`. Son las mismas funciones de `hub/db.py`.
- El dashboard corre en el hub; se abre desde cualquier equipo de la red con la IP del hub. Probar desde un segundo equipo o celular conectado al mismo wifi **sin internet** (por ejemplo, el punto de acceso del portátil con datos apagados).

### 4.2 Nivel 2 (sin red, celular) · `hub/celular.py`
Según lo acordado en Fase 0 (puntos 3, 6 y 7):
- En modo *Sin red*, el dashboard solo muestra lo que tiene `hora_recibida` ≤ hora actual. Lo pendiente queda en gris con el texto “guardado en el dron, sin sincronizar”.
- Botón *Pasa el celular* (y modo automático una vez al día entre 7 y 15 h, igual que el escenario `drones_celular`): marca los pendientes como recibidos, y el dashboard se pone al día.
- Panel de sincronización: elementos pendientes por dron, antigüedad del dato más viejo, última sincronización.

### 4.3 Nivel 3
- Solo texto en el panel: “Respaldo en la nube: no requerido”. No se implementa.

**Listo cuando:** al cambiar a *Sin red*, las alertas nuevas dejan de verse hasta pulsar *Pasa el celular*, y entonces aparecen todas.

---

## Fase 5 · Integración con datos reales (08:00–09:30)

1. Cambiar `FINCA_DB` a `data/finca.db` de la temporada `drones` de Santiago.
2. Revisar pantalla por pantalla: tipos (`drones.hora` es `REAL`, el resto `INTEGER`), NULLs, volumen (4 bloques × 72 camas × 60 días de lecturas horarias), tiempos de carga.
3. Si una consulta tarda más de ~1 s: pedir a Santiago índices en `contrato/schema.sql` (`lecturas(corrida_id, cama_id, hora)`, `riesgo(corrida_id, dia)`, `alertas(corrida_id, hora)`) o filtrar por ventana de horas.
4. Probar `run_vivo` escribiendo mientras el dashboard lee: sin errores de base bloqueada.
5. Cualquier diferencia con el contrato se arregla en `contrato/` con acuerdo, no con parches en el dashboard.

### Pestaña de evidencia
- Muestra los PNG de `data/resultados/` (las 6 gráficas del plan de Santiago) con su título y una frase de lectura cada una.
- Si existe `data/resultados/metricas.parquet`, tabla resumen por escenario (anticipación, plantas afectadas, falsas alarmas, no detectados).
- Si las gráficas no existen, mensaje “Pendiente de validación” en vez de error.

**Listo cuando:** el dashboard funciona igual con `finca.db` real que con `mock.db`.

---

## Fase 6 · Demo, respaldo y cierre (09:30–11:30)

1. **Ensayar la demo con Santiago** usando `python -m sim.run_vivo --config config/demo.yaml --velocidad 1`. Guion en pantalla (≈3 min):
   1. Mapa del Bloque 1 tranquilo; dron en patrulla.
   2. Cama 14 (Nave 2) pasa a **alto** → alerta `riesgo_7d` con su mensaje.
   3. El dron cambia a **prioridad** y va a la cama 14 → **inspeccionando**.
   4. Incidencia **confirmada** → alerta `critica` + aviso emergente.
   5. Ventilación de la Nave 2 → **apagada** (automática o por botón, según Fase 0).
   6. El agrónomo resuelve la alerta con una acción.
   7. Seguimiento automático 3 días después → **mejora**.
   8. Cambio a *Sin red* → las nuevas alertas esperan → *Pasa el celular* → aparecen.
2. Botones de demo: pausar, saltar al siguiente evento (si `run_vivo` lo permite; si no, solo pausar la lectura).
3. **Video de respaldo** de la secuencia completa grabado antes de las 11:30.
4. Capturas para las slides (mapa, alerta crítica, línea de tiempo de incidencia, panel de sincronización).
5. Probar todo con wifi apagado: que no falte ninguna fuente, icono ni librería.
6. Merge a `main` con `pytest -q` en verde.

**11:30 código congelado.**

---

## Pruebas mínimas (`tests/`)

- `test_ubicacion.py`: conversiones de identificadores y numeración continua de camas.
- `test_tiempo.py`: hora → día y fecha.
- `test_alertas.py`: transiciones válidas e inválidas; acciones permitidas por tipo.
- `test_mock.py`: el mock cumple `contrato/schema.sql` y cubre todos los estados y tipos.
- `test_privacidad.py`: ninguna consulta de interfaz devuelve `verdad_infectada`.
- `test_celular.py`: sincronizar marca `hora_recibida` y no duplica.

---

## Si voy tarde: qué cortar (en este orden)

1. `hub/api.py` (el dashboard ya lee directo con `hub/db.py`).
2. Exportar CSV.
3. Filtros avanzados de la bandeja (dejar solo severidad).
4. Sincronización automática del celular (dejar solo el botón).
5. Gráfica de evolución del riesgo en el detalle de cama.

**Nunca cortar:** mapa por Bloque · Nave · Cama con riesgo y dron; bandeja de alertas con estado y acción; incidencia con su línea de seguimientos; ventilación; interruptor *Sin red* + *Pasa el celular*; funcionamiento sin internet; video de respaldo.

---

## Checklist de entrega

- [ ] `NOTAS.md` con las decisiones de la Fase 0.
- [ ] `python -m hub.mock` genera datos válidos.
- [ ] `streamlit run dashboard/app.py` abre sin internet.
- [ ] Mapa, alertas, incidencias, ventilación, sincronización y evidencia funcionan con `finca.db` real.
- [ ] Demo completa en menos de 3 minutos, ensayada con Santiago.
- [ ] `verdad_infectada` nunca visible.
- [ ] `pytest -q` en verde y merge a `main`.
- [ ] Video de respaldo y capturas para las slides.
