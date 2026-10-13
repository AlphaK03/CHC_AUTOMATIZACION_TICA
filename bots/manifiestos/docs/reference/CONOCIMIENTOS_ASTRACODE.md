# Extracción de conocimientos — AstraCode

La organización actual de rutas y la adaptación de DUAs y Movimientos se
documentan en [RESULTADOS_Y_FLUJOS_ASTRACODE.md](RESULTADOS_Y_FLUJOS_ASTRACODE.md).
Las exportaciones actuales generan únicamente el CSV de datos.

## Reanudación por página y renovación del formulario

El `TimeoutError` de la fila 150 (298 páginas, 7.450 registros) provenía del
límite total de 1.800 segundos por manifiesto. Los cinco fallos de este tipo
en el SQLite aéreo duraban 1.800–1.801 segundos. Se elimina ese límite por
defecto; se mantienen los tiempos máximos y reintentos por solicitud.

Cada página validada se confirma inmediatamente en `partial_pages` de SQLite.
Después de detener, cerrar o perder conexión, el siguiente intento recupera
esas páginas. Consulta la primera y la última página guardada para verificar
el punto de continuación y solicita solamente las páginas restantes. Si alguna
de esas páginas cambió, deja el manifiesto pendiente y conserva el avance para
revisión. Esto comprueba los puntos de continuación; TICA no proporciona una
instantánea inmutable de toda la tabla.

Cada 10 minutos se renueva el formulario del manifiesto entre páginas. Ante
errores de conexión se intenta recuperar el formulario y, cuando hace falta,
renovar el enlace desde la lista, sin cerrar el contexto de los otros trabajadores.
Los reintentos son limitados: si no se puede continuar, el avance permanece
en SQLite. Los datos parciales no se publican en el CSV ni se marcan Guardado
hasta confirmar el final; al finalizar se consolidan y se limpia `partial_pages`
dentro de la misma transacción.

Configuración en `config/config.json`:

- `conocimientos_refresco_segundos: 600`: renovación cada 10 minutos; usar 300
  para 5 minutos o 0 para desactivar la renovación periódica.
- `conocimientos_timeout_total: 0`: sin corte por duración del manifiesto.
  Un valor positivo establece un máximo en segundos explícitamente.
- `timeout_manifest: 120`: tiempo máximo por solicitud; no limita la duración
  completa de un manifiesto.

Se mantiene la interfaz de progreso. Al reintentar se omiten los manifiestos
Guardado y se recuperan las páginas parciales disponibles de los Pendiente.
Las versiones anteriores guardaban contadores, pero no los datos de las páginas
incompletas: esos manifiestos deberán comenzar desde la primera página una vez.
No borrar ni cambiar la carpeta de salida para conservar los datos existentes.

Validación: 24 pruebas automáticas aprobadas, incluyendo interrupción, reapertura
de SQLite, recuperación de conexión, renovación periódica, rechazo de páginas
cambiadas y recuperación de un final confirmado sin conexión. En TICA se verificó
el acceso directo a los offsets 25 y 7.425 del manifiesto de la captura; evidencia
en `src/pruebas_astracode/recuperacion_timeout/salto_validado.json`.

Prueba real completa: interrupción después de 3 páginas (75 registros), reapertura
y recuperación desde SQLite, final con 55 páginas y 1.369 conocimientos sin
duplicados. Se forzó renovación cada 5 segundos para comprobarla varias veces;
la configuración normal sigue siendo 600 segundos. Una tercera ejecución omitió
el manifiesto guardado (0 intentos). Evidencia y log en
`src/pruebas_astracode/reanudacion_paginas_real/validacion.json` y `validacion.log`.

## Corrección de identificadores de la lista (5 de octubre de 2026)

La fila 12 del mes marítimo agosto 2026 corresponde a
`1-0-20260376-P027-06/08/26`. El lector anterior tomaba `12/08/26`
de otra fila al interpretar las propiedades visuales comprimidas de TICA.
Ahora los identificadores se leen de los valores completos `Grid1ContainerDataV`.
La comprobación estricta de identidad del detalle se mantiene.

Al reiniciar, se corrigen los pendientes anteriores cuando la correspondencia
es inequívoca, conservando posición e historial; los cambios quedan registrados
en `identity_changes`. No se modifican los manifiestos guardados.

Validación: 17 pruebas automáticas aprobadas y descarga real de este manifiesto,
25 conocimientos en una página, sin errores. La respuesta real contenía 23
identificadores afectados entre 357 filas. Una simulación con esa lista conservó
las 357 filas y el historial al reparar los 23 identificadores. Evidencias en
`src/pruebas_astracode/diagnostico_20260376` y descarga aislada en
`src/pruebas_astracode/correccion_20260376`.

## Cola persistente y pantalla de progreso (5 de octubre de 2026)

Al elegir **Conocimientos asociados** en la GUI aparece una ventana con una fila
por manifiesto seleccionado: **Fila, Manifiesto, Estado, Intentos, Páginas,
Leídos, Guardados y Último error**. La consulta original puede tener 357
manifiestos; esos son los 357 trabajos de conocimientos, no 357 BL ni DUAs.

Antes de descargar, toda la selección queda registrada en SQLite. Los estados
son `Pendiente`, `Descargando` y `Guardado`. Solo una tabla validada hasta el
final se marca Guardado, junto con sus datos en la misma transacción. Una tabla
vacía confirmada también queda Guardado. Los errores permanecen Pendiente.

Se utilizan **32 descargas simultáneas por defecto**, ajustables de 1 a 32.
La ventana espera a que se configure el valor y se pulse **Iniciar descarga**;
no comienza automáticamente. También se puede ajustar antes de cada reintento.
El valor inicial se lee de `conocimientos_concurrencia` en `config/config.json`.
El límite es de la aplicación, no una garantía de capacidad o velocidad de TICA.
Se conserva la misma tabla de progreso; esta configuración solo afecta Conocimientos.
Cada trabajador toma la siguiente fila libre, sin esperar a que termine el
trabajador más lento. Los resultados se guardan inmediatamente en SQLite y el
CSV final conserva el orden original de selección y la secuencia del BL.
Las descargas usan concurrencia asíncrona; la GUI corre separada del trabajo,
sin compartir objetos de Playwright entre hilos ni actualizar Tk desde ellos.

Cada ejecución verifica:

```text
357 seleccionados = guardados + pendientes
pendientes al iniciar = intentos terminados en esta ejecución
descargando al finalizar = 0
```

Los mensajes incluyen `Fila 12/357`, trabajador, intento, páginas y resultado.
El botón **Reintentar pendientes** omite los Guardado. Si un manifiesto pendiente
ya no aparece en TICA, se contabiliza como pendiente con el motivo correspondiente;
no desaparece de la selección. La selección se congela en la primera ejecución:
para incorporar nuevos manifiestos del mismo período, usar una salida nueva.

**Detener** y cerrar la ventana cancelan las solicitudes, esperan el cierre de
los recursos y conservan las filas sin terminar como pendientes. Un cierre abrupto
se recupera al iniciar nuevamente. Un bloqueo por salida evita que dos versiones
nuevas del bot escriban simultáneamente en la misma base. Reiniciar la aplicación
anterior para cargar este mecanismo; no abrir ambas sobre la misma salida.

SQLite contiene `jobs` (selección y estado), `runs` (ejecuciones), `attempts`
(intentos), `rows` (conocimientos), `manifests` y `failures`. Las bases creadas por
la primera versión de AstraCode se amplían sin borrar los manifiestos guardados.
El estado de descarga no reemplaza la columna `Estado` de TICA del CSV original.

Se puede desmarcar **Exportar CSV al terminar** para dejar todo en SQLite y usar
después **Exportar SQLite a CSV**. Solo se exporta el CSV de datos. Los estados
y errores permanecen en SQLite y se muestran en la aplicación.
Por consola, desde `src`:

```powershell
python conocimientos_cli.py --modalidad maritimo --ano 2026 --mes 8 --concurrencia 3 --solo-sqlite --salida mi_descarga
python conocimientos_cli.py --exportar-db mi_descarga/2026/08/maritimo/SQLite/conocimientos_maritimo_2026_08.sqlite3
```

Validación de esta actualización:

- 17 pruebas automáticas aprobadas. Simulación de 357 trabajos con 32 descargas
  simultáneas: 330 guardados y
  27 fallidos; al reiniciar se intentaron solo esos 27 y terminaron 357 guardados.
- Probadas interrupciones, recuperación, enlaces ausentes, migración, bloqueo de
  segundo escritor y avance continuo aunque una descarga tarde más.
- Prueba real acotada de agosto marítimo: 5 manifiestos, 10 conocimientos,
  5/5 contabilizados, sin duplicados. Reanudación con cero descargas adicionales.
- Verificados guardado solo en SQLite, exportación posterior, seguimiento de estados y
  actualización de la GUI desde su hilo principal.

Evidencia: `src/pruebas_astracode/cola_20261005/validacion_cola.json`.
La prueba de 357 fue simulada; no se volvió a descargar el mes completo.

El flujo «Conocimientos asociados» ahora lee directamente las tablas que TICA
envía, usando la misma sesión de Playwright que generó los enlaces. No abre
líneas, pesos, DUAs, movimientos ni contenedores.

- Recorre las páginas hasta el fin confirmado por TICA y rechaza páginas
  repetidas, saltos, cambios de manifiesto o columnas inesperadas.
- Conserva las 15 columnas existentes y los identificadores como texto.
- Ordena por posición del manifiesto en la consulta y secuencia numérica.
- Guarda cada manifiesto completo en SQLite, incluidos los vacíos válidos.
  Una interrupción permite retomar los pendientes sin duplicar los completos.
- Publica los CSV mediante reemplazo de un archivo temporal; los manifiestos
  que fallan se listan una sola vez y se reintentan en la siguiente ejecución.
- Permite seleccionar fechas, manifiestos y Courier. El filtro Courier se
  aplica después de leer cada página: no omite páginas que podrían contener BL
  necesarios. Para reducir las consultas, limitar fechas o manifiestos.

## Uso

Desde `D:\PortafolioDesarrollador\Manifiestos_Bot2`, con `.venv` activado:

```powershell
cd src
python conocimientos_cli.py --modalidad aereo --ano 2026 --mes 2 --desde 2026-02-28 --hasta 2026-02-28 --limite 3 --courier N --salida pruebas_astracode/mi_prueba
```

Este comando consulta los primeros tres manifiestos del día, y conserva solo
Courier = N. Para procesar el intervalo completo, quitar `--limite 3` y usar
otra carpeta de salida. Para seleccionar un manifiesto específico, agregar
`--manifiesto "4-0-26004445-P001-28/02/26"`; se puede repetir el argumento.
`--courier todos` conserva la tabla completa. `--concurrencia 2` permite dos
manifiestos simultáneos, con un máximo de cuatro; el valor predeterminado es tres.

Para reanudar, repetir exactamente los filtros y la carpeta. No borrar el
`.sqlite3`: es el control de avance. Los CSV antiguos sin ese control no se
sobrescriben. La salida se considera una instantánea: para refrescar datos que
TICA haya cambiado después, usar una carpeta nueva.

La GUI continúa funcionando. Su salida predeterminada para conocimientos es
`resultados/conocimientos/año/mes/modalidad`, con carpetas `CSV` y `SQLite`.
Se respeta `output_manifest_conocimientos_folder` si está configurado.
Opciones exclusivas de conocimientos en la configuración: `conocimientos_courier`
(`null`, `N` o `S`), `conocimientos_fecha_inicio` y `conocimientos_fecha_fin`
(`YYYY-MM-DD`), `conocimientos_manifest_ids` (lista),
`conocimientos_limite_manifiestos` y `conocimientos_concurrencia`.

## Prueba realizada

Fecha de consulta: 4–5 de octubre de 2026. Tres manifiestos aéreos del 28/02/2026:

| Manifiesto | Páginas | Filas completas | Courier N |
|---|---:|---:|---:|
| 4-0-26004445-P001-28/02/26 | 55 | 1369 | 16 |
| 4-0-26004446-P001-28/02/26 | 1 | 0 | 0 |
| 4-0-26004447-P001-28/02/26 | 1 | 4 | 4 |

La tabla de 1.369 registros tomó 40,65 s con el extractor anterior y 27,50 s
con el nuevo en estas mediciones (aproximadamente 32 % menos). La segunda
medición leyó todas las páginas y conservó los no courier. No es un pronóstico
del tiempo mensual; las condiciones de red pueden variar.

La prueba filtrada completa tardó 32,55 s; su reanudación, 4,88 s, sin nuevas
consultas de conocimientos. Las 20 filas filtradas coinciden en las 15 columnas
con el subconjunto de la extracción completa de 1.373 filas; cero duplicados.

Resultados: `src/pruebas_astracode/sin_courier_final/validacion.json` y
`src/pruebas_astracode/sin_courier_final/conocimientos_aereo_2026_02.csv`.
La extracción sin filtro está en `src/pruebas_astracode/http_inicial/`.
No se ejecutó un mes completo.

Verificación local, desde `src`:

```powershell
python -m unittest discover -s ../tests -v
```

En la validación inicial pasaron 11 pruebas: paginación, errores sin resultados parciales, identificación,
esquema, orden, conservación de ceros, filtros, vacíos, reintentos y reanudación.
Se verificó por comparación de AST que los métodos compartidos y de los otros
cuatro procesos permanecen iguales a los existentes al comenzar esta tarea.

La rama activa es `AstraCode`. Se conservaron los cambios locales previos y no
se creó ningún commit: el repositorio no tenía un commit inicial.
