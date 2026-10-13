# Crear una base unificada para BLs_BOT

Desde 2026-10-11, la detección incluye `resultados/<procedimiento>/<año>/<modalidad>` y
`datos_app/SQLite/conocimientos`; los nombres mensuales usan `enero26`, etc.
Ver [organización de resultados](ORGANIZACION_RESULTADOS_20261011.md).

Desde 2026-10-12, el origen predeterminado es **Datos de esta app**: usa internamente
los CSV de `resultados/conocimientos` y el progreso confirmado de
`datos_app/SQLite/conocimientos`. Las carpetas `src/output_manifest_conocimientos`
y `src/output_manifest_conocimientos_v2` ya no se agregan automáticamente.
**Carpetas externas** permite elegir otras entradas sin mezclarlas con las de la app.
La ventana muestra un origen único, sin listar las rutas internas de almacenamiento.
Las salidas BLS, tanto XLSX como SQLite, se guardan por defecto en `bases_bls`.

Implementado en AstraCode el 6 de octubre de 2026, dentro de Manifiestos_Bot2.
Es una sección independiente de las descargas. Trabaja con salidas locales y
no consulta TICA ni requiere abrir un navegador.

## Uso desde la app

La ventana se adapta a la pantalla (860×650 como máximo al abrir). La pestaña
**Meses** muestra la selección principal; **Archivos y opciones** contiene la
selección de fuentes, formato de entrada e históricos. El formato de salida,
ruta y botón **Generar base** permanecen fijos abajo al cambiar de pestaña o
reducir la ventana. Los meses se muestran por nombre y año.

1. Abrir Manifiestos y pulsar **Crear base para BLs_BOT**, en **Bases para otros bots**.
2. La ventana enumera los nombres de las salidas de Conocimientos sin abrir las
   bases ni recorrer filas. Elegir primero **Año**, **Mes** (en español) y
   **Modalidad**. El tipo de archivo está en **Archivos y opciones**.
   **Preferir SQLite** evita leer de nuevo
   el CSV exportado de la misma base. **Incluir históricos** está desmarcado;
   fallidos, estados y salidas de otros bots se omiten siempre.
   Pulsar **Cargar datos** para consultar únicamente esa selección.
   Se usa el origen **Datos de esta app** con las rutas actuales públicas/privadas.
   Elegir **Carpetas externas** y **Agregar…** permite sumar carpetas de
   otro disco o de versiones anteriores;
   prepara opciones sin leer todavía los datos. **Vaciar** permite elegir
   solo entradas externas. CSV/Excel externos pueden mezclar meses; sus períodos
   se verifican al cargarlos, sin descartarlos solo por el nombre del archivo.
3. La pestaña **Meses** enumera los meses y
   modalidades reales de las filas, incluso en archivos mezclados. Muestra si
   hay manifiestos pendientes; un período sin datos guardados no se puede generar.
   Pulsar la columna **Incluir** en los meses deseados. **Todos** y **Ninguno**
   seleccionan o desmarcan los meses visibles. En **Archivos y opciones**, usar
   la columna **Usar** para elegir los archivos/hojas. **Todas** y **Ninguna**
   facilitan seleccionar. Se aceptan CSV, SQLite y XLSX que tengan los campos
   de Conocimientos; se omiten controles, salidas de otros procedimientos,
   CSV/Excel vacíos y los XLSX de bases ya generadas, que no tienen Courier.
   Los SQLite con trabajos pendientes o tablas vacías confirmadas se muestran
   para informar el estado del período, aunque no tengan filas exportables.
   Se prefiere el SQLite confirmado frente a su CSV exportado; elegir **Solo CSV**
   o **Todos los archivos** antes de cargar permite consultar otras versiones.
4. Elegir **Año**, **Mes** y **Modalidad** entre los valores detectados.
   Esos controles filtran los períodos visibles y los que se incluirán al generar.
   Para unir lo marítimo de
   2025: año 2025, mes Todos y modalidad Marítimo. Para 2026, cambiar el año.
   Las etiquetas de archivo son informativas: los filtros se aplican a las filas,
   incluso si un archivo contiene varios meses o modalidades.
   Se pueden unir meses no consecutivos de distintos años; dejar año y mes en
   **Todos** y marcar solo los períodos deseados. Las marcas ocultas por un filtro
   se conservan al volver a mostrar el período. Espacio cambia las filas resaltadas.
   «Sin pendientes en la selección» describe la selección registrada en esa
   descarga, que pudo haber usado filtros de fechas o de manifiestos.
   Cambiar a un año/mes/modalidad cuyos archivos no se cargaron exige pulsar
   **Cargar datos** otra vez. La generación permanece deshabilitada
   hasta tener datos de la nueva selección. Para unir varios años o meses,
   cargar **Todos** en esos filtros y marcar después los períodos deseados.
   Si un archivo elegido no se pudo leer, no se habilita la generación para
   esa selección incompleta: volver a cargarlo o elegir un alcance sin ese archivo.
5. En **Guardar base**, elegir **Excel (.xlsx)** o **SQLite (.sqlite3)**,
   elegir la ruta con **Guardar en…** y pulsar **Generar base**. Las
   preferencias de filtros sugieren nombres como
   `Bls_sin_courier_maritimo_2025_11_periodos.xlsx`; puede editarse. La raíz inicial es
   `bases_bls/`, resuelta desde el proyecto (configurable con `bases_bls_folder`).
6. Cargar el XLSX o SQLite en BLs_BOT mediante **Seleccionar base…**. En Excel,
   seleccionar la hoja **BLS**; SQLite usa automáticamente la tabla **BLS**. Las columnas
   adicionales no afectan a su lector actual. Para archivos que superen el límite
   de Excel, procesar también **BLS_002**, **BLS_003**, etc.

Detener cancela la generación sin publicar una base incompleta. Si el destino
ya existe, la GUI pregunta antes de sustituirlo. La base se escribe en un
temporal y se reemplaza al finalizar; si está bloqueado por Excel, se conserva
el anterior. Una nueva instancia no puede generar simultáneamente el mismo
destino. Se usa un archivo pequeño `<destino>.lock` junto al destino para ese bloqueo.

## Salida SQLite

La extensión `.sqlite3` (también `.sqlite` o `.db` por CLI) genera una base con
una única tabla `BLS` y las mismas cinco columnas del Excel, todas `TEXT NOT NULL`.
Contiene únicamente BL válidos Courier=N de la selección. Conserva texto y ceros
iniciales, filtros, deduplicación y exclusión de conflictos. Se insertan las filas
en el mismo orden del Excel; consultar con `SELECT * FROM BLS ORDER BY rowid` para
mantener ese orden explícitamente. No se divide por el límite de filas de Excel.

La auditoría de procedencia, problemas y conflictos permanece separada en
`datos_app/bases_bls/auditoria`; no se añade a la base de datos exportada.
El lector actual del repositorio BLs_BOT (`src/input_files.py`) también admite
esta tabla exportada, además del XLSX y su propia caché `metadata/input_rows`.
Normaliza ambos formatos de la misma manera, preserva los ceros y calcula la
misma identidad de lote cuando filas, orden y columnas coinciden. Cambiar solo
el formato recupera los BL confirmados sin volver a consultarlos. La entrada se
abre en modo solo lectura y no se confunde con la base SQLite del progreso.
Se requiere el ejecutable actualizado de BLs_BOT. La nota de coordinación está
en `BLs_BOT/docs/COMPATIBILIDAD_CONOCIMIENTOS_20261012.md`.

Ejemplo CLI (el formato de salida depende de la extensión, `--formato` elige entradas):

```powershell
.\.venv\Scripts\python.exe src/bls_base_cli.py --ano 2026 --mes 2 --modalidad maritimo --salida bases_bls/Bls_sin_courier_maritimo_2026_02.sqlite3
```

Prueba local: febrero marítimo 2026 produjo 33.509 BL en una base SQLite de
2,34 MB, en 7,96 segundos. Se verificaron todas las columnas como texto y la
ausencia de tablas de auditoría en el archivo exportado. Informe:
`datos_app/organizacion/validacion_base_bls_sqlite_20261012.json`.
Las pruebas comparan ambas salidas fila por fila y cubren cancelación, archivo
en uso, selección de origen, creación desde la GUI y conservación de ceros.

Actualización 2026-10-12: se eliminó la lectura automática de todas las fuentes
al abrir. La consulta SQLite cuenta filas una sola vez y permite interrumpir
consultas mediante el botón Detener. CSV/Excel informan las filas revisadas;
las consultas SQLite mantienen la indicación de actividad. Tk se actualiza
desde la cola de eventos en el hilo principal; los trabajadores no leen controles.
No cambia la selección de datos confirmados, Courier=N, el orden, las columnas
ni la conservación de ceros iniciales. El CLI ofrece `--listar` sin leer datos,
`--incluir-historicos` y `--formato`, y aplica los filtros antes de cargar archivos
de períodos administrados por el bot.

Medición local acotada: 64 archivos catalogados en 0,008 segundos; febrero de
2026 marítimo, 35.750 filas confirmadas, cargó desde una sola base SQLite en
0,151 segundos. Son mediciones de ese equipo y esa entrada; no tiempos garantizados.
La generación acotada de esa entrada produjo 33.509 BL Courier=N en 9,91 segundos,
con cero filas inválidas y cero conflictos; el XLSX se verificó con identificadores
de texto. Los archivos temporales de prueba se retiraron y quedó el informe en
`datos_app/organizacion/validacion_bls_20261012.json`. Las 105 pruebas locales
pasaron; tras añadir el bloqueo por fuentes ilegibles, también pasaron las
35 pruebas específicas de BLS, incluida la selección anterior a la lectura.

## Columnas y filtros

| Columna | Regla |
| --- | --- |
| `IDManifiesto` | Identidad original, conservada como texto |
| `Secuencia Tica` | Secuencia original, conservada como texto |
| `BL original` | Número original, conservado como texto |
| `Fecha Manifiesto` | Fecha de arribo incluida al final del ID, en `DD/MM/AAAA` |
| `Mes` | Período de arribo `AAAA-MM`, por ejemplo `2025-01` |

Solo se incluyen conocimientos con Courier **N** después de limpiar espacios
y normalizar mayúsculas. Un Courier vacío o S no equivale a N. No se filtra
por nombre de transportista: un BL de DHL puede tener Courier=N. No se cruza
automáticamente contra DUAs ya descargados ni contra la lista del jefe.

La fecha corresponde al arribo, no al año que parece indicar el número de
manifiesto. Un manifiesto `20240739` con arribo de enero 2025 pertenece a
`Mes=2025-01`. La regla original de la columna de fecha del archivo del jefe
sigue sin confirmarse; aquí se usa la regla verificable que ya tenía la base de prueba.

El Excel se ordena por período, fecha, modalidad, número de manifiesto y secuencia.
El orden de entrada de archivos no decide el orden de salida. Se pueden mezclar
año/modalidad eligiendo Todos/Todas; las columnas Mes e ID permiten distinguirlos.

## Ceros a la izquierda

- CSV se lee como texto, sin convertir los identificadores a números con pandas.
- SQLite conserva los valores almacenados como texto en los datos de Conocimientos.
- En XLSX se conservan las cadenas literalmente. Si una celda numérica tiene
  formato explícito como `000000`, se reconstruye ese ancho: 123 pasa a `000123`.
- Si una celda numérica no declara ese ancho, se conserva el valor disponible y
  se registra un aviso. No existe una regla general para inferir cuántos ceros
  perdió un Excel anterior. Preferir el SQLite/CSV original en ese caso.
- Una celda numérica de más de 15 cifras, no entera, con fórmula o error se excluye
  para revisión. Excel puede haber perdido precisión; inventar cifras sería inseguro.
- Todas las celdas exportadas son texto real con formato `@`, incluidas las fechas
  y el período. BLs_BOT reconoce la fecha `DD/MM/AAAA`; no se usa notación científica
  ni se convierte en fórmula un BL literal que empiece con `=`.

## Duplicados, errores y datos incompletos

La clave de un conocimiento es **IDManifiesto + Secuencia Tica**. Para comparar
secuencias, 1 y 001 representan la misma posición, pero se conserva la representación
textual de la primera fuente aceptada. El BL se compara literalmente, incluidos ceros.

Si dos fuentes repiten esa clave y el mismo BL, se exporta una vez. Esto permite
seleccionar un SQLite y su CSV sin duplicar toda la lista. El mismo BL en otro
manifiesto o secuencia sigue siendo un conocimiento diferente y no se borra.

Si una clave tiene BL distintos, se excluye ese conocimiento y se registra el
conflicto; no se supone que agregar ceros resuelva la discrepancia. Los IDs,
secuencias o BL inválidos también se excluyen con su fuente y fila. El resumen
informa estos conteos y **Ver diagnóstico** muestra las incidencias. Los avisos
de BL numéricos sin máscara no implican que esos registros se hayan excluido.

SQLite aporta únicamente manifiestos confirmados y trabajos Guardado, además de
resultados históricos confirmados que aún no tenían una entrada de cola. Las páginas
parciales, los trabajos Pendiente y Descargando no se convierten en entradas de
la base BL. Los CSV/XLSX se consideran salidas locales proporcionadas: no pueden
acreditar por sí solos que se descargó todo un mes. La base reúne lo disponible,
no garantiza cubrir todos los manifiestos del período. Agregar salidas después
y regenerar permite ampliar la lista sin multiplicar sus duplicados.

Si un archivo seleccionado no se puede leer completamente, se aborta la generación
para no presentar una fuente parcial como completa. Durante la detección, la app
muestra archivos ilegibles en el diagnóstico y permite elegir las fuentes legibles.
Un resultado sin filas válidas no sustituye el Excel anterior.

## Persistencia y eficiencia

La unificación usa SQLite local bajo `datos_app/bases_bls/auditoria/base_<fecha>_<id>.sqlite3`:
fuentes, registros, procedencia por fila, conflictos, avisos, filtros y resumen.
La ventana muestra hasta 1000 incidencias; la base conserva todas. No se agrega
una hoja de diagnóstico al Excel que consumirá BLs_BOT.

Los archivos fuente se abren de solo lectura. Los XLSX usan lectura/escritura
streaming y las filas se ordenan desde SQLite; no se cargan todos los datos en
un DataFrame. En SQLite se aplican filtros al ID antes de decodificar JSON y se
vuelven a verificar al normalizar cada fila. La GUI permanece disponible mediante
un hilo de trabajo y una cola de eventos; Tk se actualiza en su hilo principal.
No hacen falta múltiples consultas al portal ni trabajadores de navegador aquí.

Cada generación es nueva: no altera la cola de descargas ni el progreso del bot
de BLS. El diagnóstico interno no constituye una reanudación de esta generación;
si se detiene, se vuelve a generar desde los archivos locales.

## Uso desde consola

Desde la raíz de Manifiestos_Bot2, con su entorno virtual:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/bls_base_cli.py --detectar
.\.venv\Scripts\python.exe src/bls_base_cli.py --periodo 2025-01 --periodo 2026-04 --modalidad maritimo --salida bases_bls/Bls_sin_courier_dos_periodos.xlsx
.\.venv\Scripts\python.exe src/bls_base_cli.py --carpeta datos_app/SQLite/conocimientos/2025 --ano 2025 --modalidad maritimo --salida bases_bls/Bls_sin_courier_maritimo_2025.xlsx
.\.venv\Scripts\python.exe src/bls_base_cli.py --carpeta D:/MisDatos/Conocimientos --carpeta E:/MasDatos/Conocimientos --ano 2026 --mes 8 --modalidad aereo --salida bases_bls/Bls_sin_courier_aereo_2026_08.xlsx
.\.venv\Scripts\python.exe src/bls_base_cli.py --periodo 2025-01 --periodo 2026-01 --modalidad maritimo --salida bases_bls/Bls_sin_courier_eneros.xlsx
```

Sin `--carpeta`, se usan las mismas raíces automáticas de la app. Sin año, mes
o modalidad, se incluyen todos los valores de ese filtro. El CLI aborta si
detecta archivos ilegibles; revisar primero `--detectar` y acotar carpetas.
`--periodo` puede repetirse para elegir meses específicos de distintos años.
El CLI prefiere SQLite a su CSV exportado, igual que la selección inicial de la GUI.
El CLI sustituye el destino al finalizar sin confirmación interactiva.
`--periodo AAAA-MM` es repetible; se intersecta con año, mes y modalidad si también
se especifican. `--detectar` incluye los períodos reales y su estado por fuente.

Para abrir la GUI, desde `src/`: `../.venv/Scripts/python.exe manifest_gui.py`.
Reiniciar la app que estuviera abierta para cargar la nueva sección.

## Verificación y mapa de código

`src/bls_base.py` contiene detección, lectura, validación, unificación y exportación;
`src/bls_base_panel.py` la ventana independiente y `src/bls_base_cli.py` la consola.
El botón se integra en `src/manifest_gui.py` sin cambiar el panel de descarga.
`openpyxl>=3.1,<4` queda declarado en `requirements.txt` e instalado en el entorno
del proyecto. Las instrucciones de continuación están en `CLAUDE.md`.

Pruebas offline:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`tests/test_bls_base.py` comprueba filtros por fila, orden cronológico, ceros y
formatos explícitos, fórmulas, precisión, lectura por contrato BLs_BOT, duplicados,
conflictos, exclusión de checkpoints, división de hojas, bloqueo, cancelación,
Excel bloqueado, preservación de fuentes y funcionamiento de la GUI.
Suite completa: **63 pruebas aprobadas**, incluidas las de esta nueva sección
y la detección/selección de períodos descargados.
`tests/test_bls_periods.py` incluye meses no consecutivos de distintos años,
BL de más de 15 cifras con ceros iniciales, cancelación de detección, fuentes
pendientes/vacías, preferencia de SQLite y conservación de las marcas ocultas.

Validación de enero 2025 y abril 2026 marítimos: **72.223 BL sin courier**,
576 de ellos con cero inicial. Las cinco columnas coinciden con las fuentes;
todas las celdas son texto y se comprobó por SHA-256 que las fuentes no cambiaron.
El lector real `BLs_BOT/src/data_reader.py` aceptó las 72.223 filas y conservó
las cinco columnas exactamente, incluidos los BL con cero inicial.
Informe y Excel de prueba en `src/pruebas_astracode/base_bls_periodos_20261006/`.

La muestra original de abril 2026 produjo 55 conocimientos idénticos en sus tres
campos de identidad/BL, ahora ordenados cronológicamente y con fecha numérica y Mes.
Se comprobó la aceptación de las 55 filas mediante `BLs_BOT.src.data_reader.leer_bls`,
sin ejecutar consultas al portal. Evidencia local:
`src/pruebas_astracode/base_bls_20261006/validacion_muestra.json`.

La prueba con las 22 salidas locales (11 SQLite y 11 CSV) de marítimo 2025 produjo
**404.832 BL Courier=N** de enero a noviembre, con 404.832 repeticiones de los
CSV/SQLite unificadas, cero filas inválidas y cero conflictos. Diciembre no estaba
disponible en esas entradas. Se verificaron todas las filas del XLSX contra SQLite
y todas sus celdas como texto; 3.731 BL conservaron ceros iniciales.
El archivo quedó en `bases_bls/Bls_sin_courier_maritimo_2025.xlsx` y
la evidencia en `src/pruebas_astracode/base_bls_20261006/validacion_maritimo_2025.json`.

Para replicar la arquitectura de descarga o el patrón de datos confirmados,
consultar [GUIA_REPLICACION_BOTS.md](GUIA_REPLICACION_BOTS.md).
