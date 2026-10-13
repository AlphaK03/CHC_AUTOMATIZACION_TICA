# Organización de resultados desde 2026-10-11

Cada bot tiene su carpeta. Dentro, todos sus CSV de un año y modalidad comparten
carpeta, sin subcarpetas por mes. Los meses se escriben en español y el año con dos dígitos:

```text
resultados/
  conocimientos/2026/maritimo/
    conocimientos_maritimo_enero26.csv
    conocimientos_maritimo_febrero26.csv
  conocimientos/2026/aereo/
    conocimientos_aereo_abril26.csv
  duas/2026/maritimo/
    duas_maritimo_septiembre26.csv
    fallidos/duas_excluidas_maritimo_septiembre26.csv
  movimientos/2026/maritimo/
    movimientos_maritimo_septiembre26.csv
  tabla/2026/maritimo/
    manifiestos_maritimo_septiembre26.csv
  contenedores/2026/maritimo/
    contenedores_maritimo_septiembre26.csv
datos_app/
  SQLite/<procedimiento>/<año>/<modalidad>/
    <procedimiento>_<modalidad>_<año>_<mes>.sqlite3
    <procedimiento>_<modalidad>_<año>_<mes>.sqlite3.exportacion.json
  archivos_originales/
  organizacion/
  bases_bls/auditoria/
bases_bls/
  Bls_sin_courier_....xlsx
  Bls_sin_courier_....sqlite3
```

La base conserva su nombre numérico interno e identidad de período. El JSON
adyacente indica la ubicación relativa del CSV: permite exportar directamente
una base existente y trasladar el proyecto sin incrustar rutas personales.
`resultados_folder` configura la raíz pública; `app_data_folder`, si se define,
configura el almacenamiento privado. Las rutas específicas históricas
`output_manifest_<procedimiento>_folder` (o `output_manifest_folder` para Tabla)
y `--salida` de descarga son espacios de trabajo independientes que contienen
sus propias carpetas `resultados` y `datos_app`.

La migración traslada archivos completos, sin reescribir tablas ni celdas. Verifica
SHA-256 antes y después, conserva los ceros iniciales, duplicados, trabajos,
intentos, resultados vacíos y páginas parciales. Guarda informes en
`datos_app/organizacion`. Los CSV históricos o con nombres en conflicto reciben
el sufijo `_historico_<identificador>` en `historicos/`, sin sobrescribir
el CSV actual. Los antiguos CSV de control conservan su variante en el nombre.
Los archivos de variantes `fallidos`, `fallidas` y `excluidas`, incluidos sus
históricos únicos, se separan de los datos: los actuales se guardan en la
subcarpeta `fallidos` y los antiguos en `historicos/fallidos` de cada bot/año/modalidad.
Las exportaciones de Contenedores y de exclusiones DUAs también usan esa ruta;
la exportación manual desde SQLite crea la subcarpeta cuando sea necesaria.
La migración al iniciar mueve los archivos anteriores conservando sus nombres
y contenido. Los CSV de datos principales quedan directamente en la modalidad.
Separación aplicada: 33 CSV trasladados a `fallidos`, conservando los 119 CSV
totales. Los hashes de los archivos trasladados se verificaron antes y después.
El histórico de fallidos de abril aéreo se trasladó independientemente: su
nombre `_historico_` no es un destino de exportación ni participa en la descarga
activa de Conocimientos. La base activa siguió registrando progreso; no se movió.
Informe: `datos_app/organizacion/separacion_fallidos_20261011.json`.

Separación posterior de versiones anteriores: todos los CSV cuyo nombre incluye
`_historico_` se guardan en `resultados/<bot>/<año>/<modalidad>/historicos/`.
Si son históricos de fallidos, van en `historicos/fallidos/`. Los nombres y
contenidos se conservan; no se mezclan con los resultados ni fallidos actuales.
Se trasladaron los 13 históricos presentes y se comprobaron sus hashes antes y
después, manteniendo los 118 CSV que había en esta pasada. Informe:
`datos_app/organizacion/separacion_historicos_20261011.json`.
La migración de la app mantiene esta distribución para futuros históricos.
Los Excel y auxiliares originales se archivan en almacenamiento privado; los
Excel ya generados para BLS se trasladan a `bases_bls`.
Desde 2026-10-12 también se pueden generar bases BLS de datos en SQLite en
esa carpeta. Son exportaciones con la tabla BLS, separadas de las bases de
progreso de `datos_app`. En la ventana de generación, los CSV actuales y el
progreso SQLite se muestran como un solo origen «Datos de esta app»; las
carpetas antiguas dejaron de añadirse automáticamente.

Corrección de organización: la carpeta del bot se incluye también al leer y
exportar. Los CSV de la organización plana anterior se trasladan conservando
los nombres históricos y se actualizan los enlaces relativos de exportación.
SQLite permanece en su ruta privada, sin reescribir progreso.

`src/limpiar_resultados.py` permite revisar redundancias sin borrar y aplicar
la limpieza con `--aplicar`. Solo compara archivos del mismo bot/período/variante.
Elimina copias idénticas por SHA-256 y versiones históricas cuyos registros
ya estén totalmente conservados en otro CSV. La comparación ignora únicamente
el índice generado `index_flujo_*`; conserva texto exacto, ceros iniciales y
la cantidad de repeticiones legítimas. Mantiene versiones con valores únicos,
columnas distintas o repeticiones adicionales. También retira controles históricos
vacíos; conserva las salidas actuales vacías y el CSV requerido de exclusiones.
La limpieza reserva el bloqueo de cada período, comprueba ambas copias antes
de borrar y registra cada eliminación en `datos_app/organizacion/limpieza_*.json`.
No se ejecuta automáticamente al iniciar ni elimina registros individuales.

Limpieza aplicada el 2026-10-11: se eliminaron cuatro copias idénticas de DUAs y
Movimientos de agosto y cuatro controles históricos vacíos de Conocimientos.
Quedaron 119 CSV, incluidos 14 históricos con diferencias no totalmente cubiertas
por las salidas actuales. Se verificaron los hashes de las 35 bases y de todos
los CSV conservados: contenido y progreso sin cambios. Informe:
`datos_app/organizacion/limpieza_aplicada_20261011_195444_634342.json`.
La suite local completa pasó sus 100 pruebas, incluida esta organización,
conservación de históricos únicos, multiplicidad, bloqueo y exportación portable.

Antes de mover un período, se reservan las rutas antigua y nueva mediante los
mismos bloqueos que usa el bot. Si está en uso o tiene un journal pendiente,
se pospone íntegramente. Una aplicación abierta sigue usando el código que cargó
al iniciarse: cerrar y abrir de nuevo incorpora estas rutas. Al iniciar la GUI,
la organización se vuelve a ejecutar; los procedimientos también revisan su
período antes de procesarlo. No se vuelve a descargar un manifiesto Guardado.

La detección de Conocimientos para crear BLS admite las rutas nuevas y las
anteriores, y prefiere SQLite confirmado frente a su CSV exportado. Los Excel
nuevos se generan por defecto en `bases_bls`; su auditoría interna va en
`datos_app/bases_bls/auditoria`. No cambian las columnas ni los filtros.

Para trasladar el progreso a otra PC, cerrar las instancias y copiar el proyecto
incluyendo `datos_app`, `resultados` y configuración. Los CSV por sí solos no
transportan la selección, los intentos ni las páginas pendientes.

Verificación local: pruebas de reanudación con pendientes y páginas parciales,
exclusiones de DUAs, bloqueo activo, rollback ante un archivo en uso, conservación
de históricos, exportación y copia portable de las rutas. Las pruebas no consultan
TICA. El inventario y la comparación del progreso real se guardan por separado
en `datos_app/organizacion/inventario_antes_20261011.json` y
`datos_app/organizacion/verificacion_20261011.json`.
