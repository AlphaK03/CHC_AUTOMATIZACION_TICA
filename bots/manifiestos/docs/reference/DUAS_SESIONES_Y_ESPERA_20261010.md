# DUAs: consultas lentas y trabajadores independientes

Cambio del 10 de octubre de 2026 en `D:/PortafolioDesarrollador/Manifiestos_Bot2`.
Caso: aéreo, septiembre 2026, fila 20, manifiesto
`4-0-26016862-P001-01/09/26`. La tabla grande tardaba varios minutos; los
trabajadores siguientes parecían detenidos y no se veía actividad durante la espera.

## Diagnóstico reproducido

- Una sola sesión HTTP compartida: la fila 19 respondió en 0,969 segundos;
  las filas 20 y 28 alcanzaron el límite de diagnóstico de 30 segundos.
- Fila 28 sola en sesión nueva: HTTP 200 y tabla vacía válida en 0,922 segundos.
- Tres sesiones independientes, excluyendo solo `ASP.NET_SessionId`: filas 19
  y 28 respondieron con HTTP 200 y vacío válido en 1,359 segundos; la fila 20
  seguía esperando cuando terminó el diagnóstico de 15 segundos.
- La pestaña visible solicitada quedó abierta y el usuario confirmó que la
  consulta lenta terminó mostrando aproximadamente 8.000 filas.

Esto demuestra bloqueo entre consultas que comparten sesión. El aislamiento
conserva los enlaces cifrados originales y las cookies GeneXus/acceso; no altera
la identidad de la consulta ni elimina ceros iniciales.

## Comportamiento vigente

`tablas_flow.IsolatedTableRequest` crea un cliente HTTP independiente por
manifiesto, conserva las cookies del navegador salvo `ASP.NET_SessionId` y usa
su User-Agent. Las páginas de un mismo manifiesto conservan su cliente; al
terminar, fallar o cancelar se libera. Movimientos también usa el aislamiento,
conservando sus límites y recuperación anteriores. El runner GUI y la CLI
proporcionan `pw.request` al scraper.

DUAs usa tiempo de descarga ilimitado (`timeout=0`) y límite total cero;
`duas_timeout_total` no corta consultas de este procedimiento. Un solo intento
por página evita los reintentos anidados anteriores. Un fallo HTTP distinto de
200, fallo de transporte o contenido incompleto queda Pendiente y el trabajador
continúa con el siguiente manifiesto. Al reintentar se descargan solo pendientes.
Una respuesta 200 exige identidad, columnas, cantidad y EOF válidos; una página
de error 200 nunca se transforma en un vacío exitoso.

La espera se informa cada 15 segundos en SQLite, logs y la última columna de la
pantalla («Actividad / último error»). Detener cancela la espera, libera el
cliente y deja recuperable el trabajo. Los resultados confirmados permanecen
guardados; las exportaciones mantienen columnas, orden, duplicados originales
y ceros a la izquierda. La consulta del formulario principal conserva su timeout.

## Pruebas y evidencia

Pruebas automáticas en `tests/test_duas_independientes.py`: aislamiento y
conservación de cookies, cliente estable para paginación, renovación, espera
sin límite con actividad, cancelación, rechazo de HTTP no-200 y páginas de error
200, límites por procedimiento, runner CLI y cola de dos trabajadores con una
consulta lenta, un HTTP 503 y dos rápidas. Las rápidas se guardan antes de
liberar la lenta; el HTTP fallido es el único que se reintenta posteriormente.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -q
```

La prueba real está en
`src/pruebas_astracode/diagnostico_duas_20261010/flujo_corregido.py` y escribe
SQLite/CSV y actividad en la subcarpeta `flujo_corregido`, separada de producción.
Selecciona solo las filas 19, 20 y 28 del 1 de septiembre, usa tres trabajadores
y vuelve a iniciar para comprobar la reanudación. El límite externo de 600
segundos se aplica SOLO a esta prueba para acotar consultas reales.

Resultado final: 74 pruebas automáticas aprobadas. En la prueba real las filas
19 y 28 se guardaron en aproximadamente 2 segundos mientras la 20 esperaba.
La fila 20 respondió con HTTP 200 después de 236,9 segundos, pero la tabla no
pasó la comprobación de cantidades: quedó Pendiente. La siguiente captura
aislada respondió en 118,8 segundos con una pantalla `frmAmbiente`, cuyo formulario
incluye `aspxerrorpath=/Tica/hcgduama.aspx`, sin GXState ni tabla DUAs; otra
respondió con la misma pantalla en 115 segundos. HTTP 200 no garantiza datos.
La captura está en `tabla_grande/respuesta_error_200.html`, bajo la carpeta del
diagnóstico. No se confirmó la descarga completa de la fila 20 ni se relajó
la integridad para aceptarla. Esta limitación queda pendiente de investigación.

Las pruebas adicionales fueron detenidas; su cierre y estados están en
`src/pruebas_astracode/diagnostico_duas_20261010/cierre_pruebas.json`. La base de
producción no fue modificada. La lectura del HTML se ejecuta fuera del bucle
asyncio mediante `to_thread`, sin trasladar las escrituras SQLite a otro hilo.

Para cargar el cambio en la app ya abierta, cerrar y volver a abrir
`src/manifest_gui.py`, seleccionar DUAs/Aéreo/septiembre 2026 e Iniciar descarga.
La selección original y sus filas guardadas siguen en la base de producción.

## Exclusiones solicitadas posteriormente

La regla actual para la pantalla capturada es **Excluido**, persistente en
SQLite, en lugar de Pendiente. Se detecta el formulario frmAmbiente cuyo
aspxerrorpath corresponde a hcgduama.aspx y que no contiene GXState de tabla.
No se excluye una tabla válida por tener un enlace a esa pantalla, ni cualquier
otro error genérico/HTTP o una cantidad inconsistente. Los trabajadores continúan
con el siguiente manifiesto y en futuras ejecuciones omiten el Excluido.

Al exportar DUAs se generan los datos normales y
`duas_excluidas_<modo>_<año>_<mes>.csv` en la misma carpeta CSV, con fila de origen,
IDManifiesto, fecha, motivo e intentos. Siempre se escribe su cabecera. La lista
identifica manifiestos: la página de error no informa los DUAs asociados.

La GUI distingue Excluido y su contador. La contabilidad incluye ese estado,
las bases anteriores se migran de forma transaccional y se conserva el historial.
Pruebas actuales: 81 aprobadas; `tests/test_duas_exclusiones.py` verifica el HTML
real guardado, detección precisa, persistencia/reanudación, conservación de datos
y ceros, rollback de migración y las dos salidas. Se hicieron exclusivamente
pruebas locales para esta actualización, sin repetir la consulta lenta.

## Contador **** y errores de conversión

El error `invalid literal for int() with base 10: '****'` no implica frmAmbiente
ni permite excluir una consulta. En la lectura local de la base de aéreo
septiembre había 14 casos, todos Pendientes; los dos Excluidos correspondían
a la pantalla frmAmbiente. Se dejaron intactos la ejecución y su base.

El lector acepta un contador enmascarado solo cuando el número de filas permite
su desbordamiento (por ejemplo, **** para al menos 10.000 filas) y el contador
numérico independiente coincide con DataV. Si ambos contadores son máscaras,
si hay menos filas o si las cantidades/identidad/esquema no concuerdan, no se
confirma el resultado: sigue Pendiente. Las celdas no se convierten a enteros.

Al iniciar con la nueva versión se reconsideran también exclusiones antiguas
cuyo motivo sea un error de conversión int/base 10, sin datos guardados ni
indicio frmAmbiente. Se marca Pendiente y se audita en job_reconsiderations,
conservando intentos y motivo anteriores. El bloqueo normal protege esta
recuperación. Pruebas exclusivamente locales en tests/test_duas_contadores.py.
Suite completa actual: 87 pruebas aprobadas, con pruebas de Tk en procesos aislados.

## nRC negativo: 61356 filas y -4180

El ejemplo recibido `datos=61356, grid=61356, nRC=-4180` tiene cantidades
independientes coincidentes y una diferencia exacta de 65.536, equivalente
al desbordamiento de un contador de 16 bits con signo. El lector DUAs acepta
nRC desbordado solo si Count es numérico, coincide con todas las filas de DataV
y nRC es exactamente `(filas + 32768) % 65536 - 32768`. La validación de identidad,
campos, columnas y EOF sigue activa. Cualquier otra discrepancia permanece
Pendiente. Esto no convierte celdas ni cambia ceros a la izquierda.

Las pruebas locales guardaron y exportaron las 61.356 filas completas y verificaron
los límites 32.768/65.536/65.537 y una segunda vuelta con 100.000 filas. También
comprueban el rechazo de cantidades y esquemas incorrectos. Se usaron fixtures
locales, sin nuevas consultas a TICA. La app en ejecución carga el cambio al reabrirla.
Suite completa tras esta corrección: 90 pruebas locales aprobadas.
