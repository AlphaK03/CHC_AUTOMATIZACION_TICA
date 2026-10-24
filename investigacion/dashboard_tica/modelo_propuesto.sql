-- Esquema analítico ilustrativo. NO ejecutar sobre las bases del Workbench.
-- Cada carga usa un corte coherente elegido explícitamente; no sumar cortes.
PRAGMA foreign_keys=ON;

CREATE TABLE corte_fuente (
    corte TEXT PRIMARY KEY,
    bot TEXT NOT NULL,
    procedimiento TEXT,
    periodo TEXT NOT NULL,
    capturado_en TEXT NOT NULL,
    fuente TEXT NOT NULL,
    cobertura TEXT NOT NULL DEFAULT 'muestra'
);

CREATE TABLE dua (
    dua_key TEXT PRIMARY KEY,
    aduana TEXT NOT NULL,
    anio TEXT NOT NULL,
    numero TEXT NOT NULL,
    UNIQUE(aduana,anio,numero)
);

CREATE TABLE cabecera_dua (
    corte TEXT NOT NULL REFERENCES corte_fuente,
    dua_key TEXT NOT NULL REFERENCES dua,
    regimen TEXT,
    fecha_registro TEXT,
    estado TEXT,
    bultos_texto TEXT,
    peso_bruto_texto TEXT,
    valor_aduanero_texto TEXT,
    moneda_valor_aduanero TEXT, -- NULL hasta validar la unidad de la fuente.
    PRIMARY KEY(corte,dua_key)
);

CREATE TABLE tributo_dua (
    corte TEXT NOT NULL REFERENCES corte_fuente,
    dua_key TEXT NOT NULL REFERENCES dua,
    fila_origen INTEGER NOT NULL,
    codigo_tributo TEXT NOT NULL,
    descripcion TEXT,
    importe_mn_texto TEXT NOT NULL,
    importe_mn_centimos INTEGER, -- Validar conversión exacta; no usar REAL para dinero.
    PRIMARY KEY(corte,dua_key,fila_origen)
);

CREATE TABLE linea_transito (
    corte TEXT NOT NULL REFERENCES corte_fuente,
    dua_key TEXT NOT NULL REFERENCES dua,
    fila_origen INTEGER NOT NULL,
    item TEXT,
    partida TEXT,
    descripcion TEXT,
    bultos_texto TEXT,
    tipo_bulto TEXT,
    PRIMARY KEY(corte,dua_key,fila_origen)
);

CREATE TABLE asociacion_dua_movimiento (
    corte TEXT NOT NULL REFERENCES corte_fuente,
    dua_key TEXT NOT NULL REFERENCES dua,
    fila_origen INTEGER NOT NULL,
    deposito TEXT NOT NULL,
    anio_movimiento TEXT NOT NULL,
    numero_movimiento TEXT NOT NULL,
    tipo_movimiento TEXT NOT NULL,
    bultos_asociados_texto TEXT,
    PRIMARY KEY(corte,dua_key,fila_origen)
);
-- La llave depósito/año/movimiento no se sustituye por el número aislado.
-- Estas cantidades son asociaciones, no saldo de existencias.

CREATE TABLE manifiesto (
    manifest_key TEXT PRIMARY KEY, -- Identidad compuesta original, sin recortar.
    modalidad TEXT,
    tipo_manifiesto TEXT,
    numero TEXT,
    ubicacion TEXT,
    fecha_arribo TEXT
);

CREATE TABLE conocimiento (
    manifest_key TEXT NOT NULL REFERENCES manifiesto,
    secuencia_tica TEXT NOT NULL,
    bl_comercial TEXT NOT NULL, -- No se impone unicidad global al BL comercial.
    PRIMARY KEY(manifest_key,secuencia_tica)
);

CREATE TABLE linea_bl (
    corte TEXT NOT NULL REFERENCES corte_fuente,
    manifest_key TEXT NOT NULL,
    secuencia_tica TEXT NOT NULL,
    fila_origen INTEGER NOT NULL,
    numero_linea TEXT,
    contenedor TEXT,
    tipo_bulto TEXT,
    peso_texto TEXT,
    bultos_texto TEXT,
    estado TEXT,
    PRIMARY KEY(corte,manifest_key,secuencia_tica,fila_origen),
    FOREIGN KEY(manifest_key,secuencia_tica) REFERENCES conocimiento
);

-- Propuesto: no existen filas locales confirmadas para poblarlo en esta muestra.
CREATE TABLE asociacion_dua_conocimiento (
    corte TEXT NOT NULL REFERENCES corte_fuente,
    fila_origen INTEGER NOT NULL,
    dua_key TEXT NOT NULL REFERENCES dua,
    dua_item TEXT NOT NULL,
    manifest_key TEXT NOT NULL,
    secuencia_tica TEXT NOT NULL,
    conocimiento_linea TEXT NOT NULL,
    bultos_asociados_texto TEXT,
    estado_asociacion TEXT NOT NULL,
    fecha_asociacion TEXT,
    PRIMARY KEY(corte,fila_origen),
    FOREIGN KEY(manifest_key,secuencia_tica) REFERENCES conocimiento
);
-- Estado/fecha se preservan; hace falta definir qué estados son vigentes.
-- El CSV local no acredita peso bruto asociado ni unidades comerciales.

CREATE VIEW tributos_por_dua AS
SELECT corte,dua_key,SUM(importe_mn_centimos) importe_mn_centimos,
       COUNT(*) filas,COUNT(importe_mn_centimos) filas_con_importe_interpretable
FROM tributo_dua GROUP BY corte,dua_key;
-- Unir esta agregación con cabeceras, no filas de tributos con filas de movimientos.
-- Elegir los cortes compatibles explícitamente; las fechas pueden ser distintas.
