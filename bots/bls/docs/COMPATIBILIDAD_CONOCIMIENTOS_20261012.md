# Compatibilidad con las bases de Conocimientos — 2026-10-12

Nota para la sesión de Codex que está trabajando en BLs_BOT.

Corrección terminada y ejecutable actualizado. El usuario autorizó estos cambios
en ambos repositorios. Se conservaron los cambios previos de la otra sesión;
no se creó otra rama ni se hizo commit. No se cambió el motor de consultas ni
el progreso real, configuración local o cachés de producción.

El generador publica XLSX con hoja BLS o SQLite con una tabla BLS, ambos con:
`IDManifiesto`, `Secuencia Tica`, `BL original`, `Fecha Manifiesto`, `Mes`.
Las cinco columnas SQLite son TEXT NOT NULL y su orden es ORDER BY rowid.
No es la caché interna metadata/input_rows ni la base SQLite del progreso.

## Causa y corrección

El registro `dist/logs/debug.log` mostró a las 13:19:16 el rechazo de la base
SQLite exportada con `no such table: metadata`. El lector reconocía únicamente
la caché interna. La base del generador era correcta, pero el consumidor no
conocía su contrato.

- `src/input_files.py`: reconoce la tabla BLS exportada, exige las cinco columnas
  TEXT, descarta entradas vacías/nulas y tablas ajenas, abre `mode=ro` con
  `query_only` y lee `ORDER BY rowid`. La hoja lógica es BLS incluso al renombrar
  el archivo. Sigue leyendo las cachés anteriores y rechazando SQLite de progreso.
- `src/data_reader.py`: extrajo `prepare_bls` de `leer_bls` para normalizar ambos
  formatos igual. Incluye Fecha Manifiesto y columnas derivadas ID2/ID3/ID4,
  necesarias para que la firma del lote coincida con la entrada XLSX existente.
  No agrega ni elimina ceros ni convierte BL/secuencia a números.
- `tests/test_input_files.py`: equivalencia de filas, fechas, trabajos, firma,
  caché, ceros y CLI; rechazo seguro de entradas incompatibles/nulas/vacías y
  comprobación de que una ruta inexistente no crea una base nueva.
- `tests/test_ui.py`: selección y carga en segundo plano de XLSX, tabla BLS
  exportada y caché interna; una entrada fallida conserva la base anterior.
- `src/core/self_test.py`: el ejecutable prueba la tabla BLS, la equivalencia
  con XLSX y la reanudación entre formatos sin repetir BL confirmados.
- `scripts/verify_conocimientos_input.py`: prueba reproducible entre los dos
  repositorios usando el generador real, archivos temporales y sesiones simuladas.
- README, CLAUDE y ARQUITECTURA documentan el contrato nuevo.

## Comprobaciones terminadas

1. Suite completa: **59 pruebas**, todas correctas.
2. Generador real de Manifiestos_Bot2: siete conocimientos de muestra produjeron
   tres BL en cada formato; Courier=S, duplicados y conflictos se filtraron igual.
   Se comprobó un BL numérico de más de 15 caracteres y secuencias 001/0002/003, intactos.
3. Muestra acotada de **12 filas** de los archivos existentes
   `Manifiestos_Bot2/bases_bls/Bls_sin_courier_maritimo_2026.xlsx` y `.sqlite3`:
   filas idénticas, trabajos válidos, fechas por mes correctas, misma firma y
   reanudación sin repetir consultas. Los originales se leyeron sin modificarlos.
4. Se ejecutó `build.bat`; el candidato quedó en `build/release/` y se actualizó
   **`dist/BLs_BOT_AstraCode.exe`**. No había una instancia de ese ejecutable abierta.
5. El ejecutable pasó `--verificar-instalacion`: `ready=true`, `frozen=true`,
   `knowledge_sqlite=true` y `cross_format_resume=true`. Chromium local funcionó;
   no se descargó otro navegador. Todas las consultas fueron simuladas, sin TICA.

Informes locales:

- `logs/compatibilidad_conocimientos_20261012.json`
- `logs/verificacion_compatibilidad_conocimientos_20261012.json`

Para repetir la comprobación entre repositorios:

```powershell
.\.venv\Scripts\python.exe scripts/verify_conocimientos_input.py --manifiestos D:\PortafolioDesarrollador\Manifiestos_Bot2 --informe logs/compatibilidad_conocimientos.json
```

## Uso y límites

Abrir el ejecutable actualizado y **Seleccionar base…**. El XLSX usa la hoja BLS
y SQLite la tabla BLS; no es necesario regenerar los archivos ya exportados con
este contrato. La caché propia se sigue guardando para restaurar la app al abrir.
Para continuar un lote no pulsar Nueva descarga. La igualdad de progreso depende
de conservar filas, orden, columnas, hoja y filtros; generar una selección distinta
crea otro lote. XLSX con más de una hoja se procesa por hoja; SQLite contiene
toda la selección en una tabla, por lo que no equivale a una sola hoja parcial.

No se hicieron consultas reales a TICA ni una descarga de producción para probar
la importación. La compatibilidad de carga y reanudación está comprobada localmente.
