# Resultados organizados, DUAs y Movimientos

La [guía de replicación en otros bots](docs/GUIA_REPLICACION_BOTS.md) conserva
la arquitectura compartida con Detalles, las estrategias de navegación,
configuración, pruebas, garantías de reanudación y límites de las mediciones.
Usarla como punto de entrada al retomar o adaptar otro procedimiento.

La sección independiente **Crear base para BLs_BOT** permite detectar o elegir
salidas locales de Conocimientos, unirlas por año/mes/modalidad y generar un XLSX
Courier=N con identificadores de texto y columna `Mes`. Su uso, recuperación de
ceros verificables y manejo de duplicados/conflictos están en
[BASES_BLS.md](docs/BASES_BLS.md).

Los tres procedimientos Conocimientos, Recorrer DUAs por manifiesto y Movimientos
usan la misma ventana de progreso. Antes de iniciar se elige la concurrencia
(1–32) y si se quiere exportar el CSV al terminar. Los valores predeterminados
son 32 para Conocimientos y 4 para DUAs y Movimientos, independientes entre sí.

DUAs y Movimientos consultan directamente los enlaces de TICA con las cookies
del navegador, sin abrir una pestaña por manifiesto. Se conservan todas las
columnas y sus valores: índices `index_flujo_duas` / `index_flujo_movimientos`,
ceros iniciales, columna vacía de Movimientos y `manifiesto`. La salida sigue el
orden de selección y el orden original de las filas; no se deduplican registros
del contenido. La concurrencia usa solicitudes asíncronas; SQLite tiene un único
escritor y Tk se actualiza únicamente desde el hilo de la interfaz.

Las páginas examinadas de estos dos procedimientos contienen el grid completo,
sin paginación. Se confirma la identidad, esquema y cantidad de registros antes
de guardarlos. Una tabla vacía válida queda Guardado con cero filas. Los errores
permanecen Pendiente y no se omiten trabajos cuando falla un enlace.

El avance se guarda en SQLite por manifiesto y, si hubiera paginación verificable,
por página. Reintentar omite los Guardado. Se reutilizan la recuperación ante
desconexión, renovación del formulario y cancelación de Conocimientos. En una
respuesta completa de DUAs o Movimientos no se puede recuperar la mitad de la
respuesta HTTP: se guarda al recibirla y validarla; si falla antes, se repite
únicamente ese manifiesto.

## Rutas actuales (2026-10-11)

Cada bot agrupa sus CSV por año y modalidad en `resultados/<procedimiento>/<año>/<modalidad>/`.
Los nombres utilizan el mes en español y el año corto, por ejemplo
`conocimientos_maritimo_enero26.csv` y `duas_excluidas_aereo_septiembre26.csv`.
SQLite y auxiliares son privados, bajo `datos_app`; las bases mantienen sus
nombres internos y su progreso en `datos_app/SQLite/<procedimiento>/<año>/<modo>/`.
Los XLSX para BLS se guardan fuera de resultados, en `bases_bls`.

Los archivos de fallidos, fallidas y excluidas se separan dentro de
`resultados/<bot>/<año>/<modalidad>/fallidos/` para las salidas actuales.
Los históricos se separan ahora en `historicos/` dentro de esa modalidad,
y los históricos de fallidos en `historicos/fallidos/`.
Los datos principales permanecen directamente en la carpeta de modalidad.
Esta separación se aplica tanto a los archivos existentes como al exportar.

La migración conserva el contenido byte por byte, pospone archivos activos y
se repite al reiniciar. Los informes y archivos originales se conservan bajo
`datos_app/organizacion` y `datos_app/archivos_originales`, respectivamente.
Leer [ORGANIZACION_RESULTADOS_20261011.md](docs/ORGANIZACION_RESULTADOS_20261011.md)
para configuración, compatibilidad, traslado del progreso y pruebas.
Las rutas citadas a continuación documentan la organización histórica anterior.



La limpieza explícita de CSV conserva solo copias únicas: elimina duplicados
identificados por SHA-256 y versiones antiguas totalmente cubiertas por otra
salida, respetando texto, ceros iniciales y repeticiones legítimas. Las versiones
con datos distintos se conservan. No modifica las bases ni las filas extraídas.
Los informes se guardan en `datos_app/organizacion/limpieza_*.json`.

## Datos anteriores

Se organizaron los resultados existentes manteniendo sus nombres y comprobando
SHA-256 antes y después de moverlos. Los informes están en `resultados/organizacion`.
Las bases activas no se mueven: se pospone su organización hasta que cierren.
Los archivos CSV anteriores de DUAs y Movimientos con el esquema original se
incorporan a SQLite automáticamente al iniciar ese período. Sus manifiestos con
datos quedan reconocidos como guardados; las tablas vacías no registradas en el
CSV deben verificarse una vez. Antes de la primera exportación se conserva una
copia intacta del CSV anterior en la carpeta `historicos` del período.

Se incorporaron ya a SQLite los cuatro CSV de agosto 2026 (aéreo y marítimo,
DUAs y Movimientos), conservando intactos los CSV: 1.990.097 filas en total.
El informe está en `resultados/organizacion/migracion_sqlite_agosto_2026.json`.

Los registros originales duplicados, si los hay, se conservan al importar:
la nueva reanudación evita generar nuevas copias, pero no limpia históricos
automáticamente. Los índices de exportación se calculan en orden, de 1 a N.

## Verificación

- 33 pruebas automáticas aprobadas, incluyendo 357 trabajos para cada procedimiento
  nuevo: 330 guardados y 27 fallidos, reintento de solo los 27 y final con 357.
- Prueba real: 10 manifiestos entre DUAs/Movimientos y aéreo/marítimo; 322 filas
  idénticas al extractor anterior. Incluye dos tablas vacías correctamente guardadas.
- Reanudación real con cero descargas adicionales para los trabajos guardados.
- Interfaz probada para ambos procedimientos: configuración antes del inicio,
  máximo de 32, mismas ocho columnas y exportación SQLite con un solo CSV de datos.
- Lectura directa de las ocho tablas no vacías: aproximadamente 3,70 segundos
  de solicitudes HTTP frente a 11,21 segundos de navegación/extracción original.
  Son mediciones acotadas; la consulta mensual inicial y la velocidad de TICA
  influyen en el tiempo total de una ejecución.

Evidencia: `src/pruebas_astracode/analisis_duas_movimientos`, con respuestas,
CSV originales, comparación, validación nueva y comprobación de la interfaz.

## Consola

Desde cualquier carpeta, usar la ruta al Python del entorno y al script. Ejemplo
desde `src`, con una raíz de salida explícita:

```powershell
python conocimientos_cli.py --procedimiento duas --modalidad aereo --ano 2026 --mes 8 --concurrencia 4 --salida D:/MisResultados/duas
python conocimientos_cli.py --procedimiento movimientos --modalidad maritimo --ano 2026 --mes 8 --concurrencia 4 --salida D:/MisResultados/movimientos --solo-sqlite
python conocimientos_cli.py --exportar-db D:/MisResultados/movimientos/2026/08/maritimo/SQLite/movimientos_maritimo_2026_08.sqlite3
```

Reiniciar la aplicación para cargar esta versión. En la GUI se mantienen las
opciones de modalidad y período y se abre la pantalla de seguimiento para los
tres procedimientos. Las opciones de concurrencia no alteran otros bots.

## DUAs: consultas lentas, 2026-10-10

Se corrigió el bloqueo entre consultas que compartían sesión ASP.NET. DUAs y
Movimientos usan un cliente HTTP independiente por manifiesto, conservando
cookies GX/acceso y User-Agent; solo se excluye `ASP.NET_SessionId`. DUAs espera
sin timeout de descarga ni límite total hasta respuesta o Detener. Los otros
trabajadores continúan. Un HTTP distinto de 200 o contenido inválido queda
Pendiente y el trabajador sigue, sin reintentos internos multiplicados.

La columna final ahora muestra «Actividad / último error» y actualiza la espera
cada 15 segundos. SQLite, filas vacías válidas, orden, duplicados y ceros iniciales
conservan el contrato anterior. El formulario principal y los otros flujos
mantienen sus límites. La GUI y la CLI utilizan el cliente independiente.

74 pruebas automáticas aprobadas. Diagnóstico y prueba real de las filas 19, 20
y 28 del 1 de septiembre en salida aislada: las dos rápidas se guardaron mientras
la 20 esperaba. Consultar [el diagnóstico](docs/DUAS_SESIONES_Y_ESPERA_20261010.md)
y `src/pruebas_astracode/diagnostico_duas_20261010/flujo_corregido` para el resultado
final y los tiempos, sin alterar la base del período en producción.

La descarga completa de la fila 20 aún no fue confirmada: respondió con una
tabla de cantidades inconsistentes y, en otras pruebas, una pantalla de error
con HTTP 200. Se conserva Pendiente. Las pruebas adicionales fueron detenidas;
el cambio de espera y aislamiento está validado. La lectura del HTML se realiza
en un hilo aparte para mantener disponible el bucle de descargas.

## DUAs: exclusión de frmAmbiente y dos CSV

Por solicitud posterior del usuario, la pantalla `frmAmbiente` con formulario
`aspxerrorpath=/Tica/hcgduama.aspx` sin GXState de tabla válida pasa a **Excluido**.
El estado, motivo e intento se confirman en SQLite; al iniciar otra ejecución
se consultan solo los Pendientes. Los Excluidos no se vuelven a intentar.
Los errores HTTP genéricos, otras páginas inválidas y cantidades inconsistentes
siguen pendientes; solo esa pantalla confirmada dispara esta exclusión.

DUAs exporta dos archivos dentro de su carpeta CSV:

- `duas_<modo>_<año>_<mes>.csv`: datos normales, con sus columnas y ceros originales.
- `duas_excluidas_<modo>_<año>_<mes>.csv`: fila de origen, IDManifiesto, fecha,
  motivo e intentos. Incluye cabecera aun cuando no haya exclusiones.

No es posible identificar los números de DUA individuales cuando la página
no devolvió la tabla: el segundo CSV identifica el manifiesto cuya consulta falló.
La GUI muestra Excluido y su contador; la exportación automática, la manual
y la CLI desde SQLite producen ambas salidas. La actualización de bases previas
conserva selección, datos e historial mediante una migración transaccional del
CHECK de jobs, realizada bajo el bloqueo de salida.

81 pruebas locales aprobadas, incluyendo la respuesta HTML guardada, reanudación
sin consultar Excluidos, migración y rollback, exportaciones y ceros originales.
No se iniciaron nuevas consultas reales para comprobar este cambio. Reiniciar
la app antes de usarlo; no se reclasifican fallos históricos ambiguos a partir
de su texto genérico de error.

## DUAs: errores de conversión y reconsideración al reiniciar

Se verificaron 14 trabajos con `invalid literal for int() with base 10: '****'`
en la base de aéreo septiembre 2026: todos estaban Pendientes, separados de dos
exclusiones frmAmbiente. Por eso ya se incorporan al siguiente inicio.
No se escribió en la base usada por la aplicación mientras se corregía el código.

El lector de DUAs ahora admite un contador enmascarado con asteriscos solamente
si el número de filas alcanza el desbordamiento de su ancho y existe otro
contador numérico que coincide con todas las filas de DataV. Se conservan los
controles de identidad, esquema, anchura, paginación, cantidades y los valores
originales. Si no se puede validar el resultado sigue Pendiente.

Además, `ManifestTableStore.start_run` recupera cualquier exclusión antigua que
contenga ese error de conversión, sin datos confirmados y sin motivo frmAmbiente:
la devuelve a Pendiente y registra el motivo anterior en `job_reconsiderations`.
Conserva la fila, los ceros y todo el historial de intentos. Las exclusiones
frmAmbiente y los resultados guardados permanecen como estaban.
La recuperación corre bajo el bloqueo de salida al iniciar con el código nuevo;
no requiere editar a mano la base ni repetir consultas largas como prueba.

Pruebas locales: `tests/test_duas_contadores.py`, con 10.000 registros y contador
`****`, contador numérico independiente, rechazo de cantidades/formas inválidas,
reapertura y reconsideración de errores antiguos, auditoría y conservación de
exclusiones frmAmbiente y ceros a la izquierda.

Verificación final: 87 pruebas aprobadas. Las pruebas de paneles BLS se ejecutan
en procesos aislados para que sus objetos Tk no se destruyan desde el recolector
de un trabajador asyncio de otra prueba; también se mantiene su validación real.

## DUAs: nRC negativo con tablas grandes

El usuario reportó `datos=61356, grid=61356, nRC=-4180` para la fila 20.
Las cantidades de DataV y Count coinciden; la discrepancia de nRC encaja
exactamente con un contador de 16 bits con signo: 61356 - 65536 = -4180.
El lector anterior rechazaba esa equivalencia aunque las cantidades independientes
coincidieran. No es una respuesta frmAmbiente ni una exclusión definitiva.

Se acepta esa representación únicamente para DUAs cuando Count es numérico e
igual al número de filas y nRC coincide con `(filas + 32768) % 65536 - 32768`.
Se mantienen identidad, esquema, anchura y EOF. Las discrepancias reales permanecen
Pendientes. Los contadores originales de la respuesta y todas las celdas se
conservan; la corrección modifica solo su comprobación, sin convertir identificadores.

Prueba local: 61.356 filas guardadas en SQLite y exportadas completas a CSV,
con ceros y duplicados; también se verificaron 32.768, 65.536, 65.537 y 100.000
filas para límites y vueltas completas. Contador incorrecto, otro Count y otro
esquema se rechazan. No se repitió la consulta real ni se modificó la base activa.
Reabrir la app carga la corrección; la fila pendiente se volverá a considerar.
Verificación final de esta corrección: 90 pruebas locales aprobadas.
