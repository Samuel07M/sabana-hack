-- contrato/schema.sql · Berry Good Idea
-- Frontera entre el simulador (Santiago) y el hub/dashboard (Samuel).
-- Se cambia solo con acuerdo de los dos (ver NOTAS.md).

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
  estado TEXT,                      -- 'sospecha' | 'confirmada' | 'en_tratamiento' | 'en_seguimiento' | 'cerrada' | 'descartada'
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

CREATE TABLE alertas (              -- las crea el simulador; el hub solo cambia estado y accion
  alerta_id INTEGER PRIMARY KEY,
  corrida_id TEXT, hora INTEGER, cama_id TEXT, incidencia_id INTEGER,
  severidad TEXT,                   -- 'info' | 'advertencia' | 'critica'
  tipo TEXT,                        -- 'riesgo_7d' | 'confirmacion' | 'seguimiento' | 'ventilacion' | 'descartada'
  titulo TEXT, mensaje TEXT,
  estado TEXT DEFAULT 'nueva',      -- 'nueva' | 'vista' | 'resuelta'
  accion TEXT                       -- lo que eligió el agrónomo (valores en config/default.yaml, dashboard.acciones)
);

CREATE TABLE drones (               -- posición y estado, una fila por cambio
  corrida_id TEXT, hora REAL, dron_id TEXT, cama_id TEXT,
  estado TEXT,                      -- 'patrulla' | 'prioridad' | 'inspeccionando' | 'carga'
  bateria REAL
);

CREATE TABLE ventilacion (          -- la escribe solo el simulador (apagado automático)
  corrida_id TEXT, hora INTEGER, bloque INTEGER, nave INTEGER,
  estado TEXT,                      -- 'encendida' | 'apagada'
  motivo TEXT                       -- 'auto: incidencia #12' | 'auto: fin de apagado'
);

CREATE TABLE cola_sync (            -- nivel 2: el simulador escribe con hora_recibida NULL; el hub la llena
  id INTEGER PRIMARY KEY,
  corrida_id TEXT, origen TEXT,     -- 'dron:B1' | 'celular'
  hora_generada INTEGER, hora_recibida INTEGER,
  tipo TEXT,                        -- 'lectura' | 'inspeccion' | 'seguimiento'
  payload TEXT                      -- JSON con las columnas de la tabla destino
);

CREATE INDEX idx_lecturas_corrida_cama_hora ON lecturas (corrida_id, cama_id, hora);
CREATE INDEX idx_riesgo_corrida_dia ON riesgo (corrida_id, dia);
CREATE INDEX idx_alertas_corrida_hora ON alertas (corrida_id, hora);
