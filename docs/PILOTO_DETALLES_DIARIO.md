# Piloto: Detalles con base propia diaria

Rama: `feature/detalles-base-diaria-calendario`. Implementado para Detalles y
comprobado offline. Los otros bots siguen en demo. No se lanzó ninguna descarga
diaria real como prueba automática de esta entrega.

## Uso

1. Abrir el Workbench y elegir **Diario automático** en Modo.
2. Indicar **Desde**, con formato `AAAA-MM-DD`. Por defecto propone ayer;
   una fecha anterior recupera los días pendientes desde esa fecha.
   También puede elegirse desde **Calendario**: pulsar el primer y último día
   (en cualquier orden) y **Usar rango**. Se permiten días anteriores a Desde
   y rangos entre meses usando las flechas. No se permiten fechas futuras.
   **Hasta** limita la ejecución: se detiene al completar ese día. Dejar Hasta
   vacío mantiene el ciclo continuo de las 00:01. Elegir un rango no inicia consultas.
3. Revisar Guardar en y Configuración. Pulsar **Iniciar automático**.
4. Consultar **Calendario** y seleccionar un día para ver cantidades y errores.
5. **Detener** o cerrar la app conserva bases, resultados y calendario.

No se pide Excel. Detalles descarga los nueve regímenes del día elegible con el
proveedor integrado, valida cobertura y agrega sus DUAs directamente a SQLite.
Ejecuta su motor y sigue con los atrasados o espera hasta las 00:01 de Costa Rica.
La fecha inicial queda guardada al iniciar; reiniciar no descarta días pendientes.

En un equipo nuevo ejecutar `Instalar_Workbench.bat`, `Instalar_Detalles.bat` y
`Instalar_Base_Diaria.bat`. Este último prepara un Edge WebDriver propio compatible,
sin consultar TICA. Si Edge cambia de versión, volver a ejecutarlo. No se necesita
DUAS_SCRAPPING instalado ni su ejecutable, base, configuración o controlador.
`workbench/app.py --daily` abre esta vista sin iniciar descargas.

## Calendario y resultados

- Verde: todos los DUAs de ese día tienen resultados guardados, o la base está
  vacía y validada. Descargar la lista no basta para marcar completo el día.
- En curso: descargando o procesando. Pendiente: aún no se ha completado.
- Fechas todavía no disponibles aparecen atenuadas. Los días anteriores a Desde
  siguen disponibles para elegir un nuevo rango; figuran Sin ejecutar si no tienen registro.
- Mientras corre el bot, el calendario permite consultar estados. Detener antes
  de cambiar el rango. Los días ya completos se reutilizan sin volver a descargarlos.
- Una base incompleta o DUAs sin terminar quedan pendientes. El ciclo retoma
  automáticamente en cinco minutos, conservando regímenes y resultados guardados.
- Un régimen sin registros cuenta como consulta completa solo con respuesta
  confirmada de TICA. Los DUAs de los otros regímenes forman la base igualmente.
  Si los nueve están vacíos y confirmados, el día se registra como completo sin
  consultas de Detalles; se conserva la tabla/CSV mensual, incluso si está vacío.
- No se saltan días pendientes. Un fallo persistente puede mantener el ciclo
  en ese día y queda visible en el calendario.
- Una tabla por mes, como `octubre26`. Si ya existe, se agrega sin borrar datos.
  Una base manual preexistente no acredita días completos automáticamente.
- Únicamente `octubre26/Detalles_DUAs_octubre26.csv` en Resultados. Bases, TXT/JSON,
  calendario, diagnósticos y respaldos permanecen internos.
- Un día de septiembre terminado en octubre actualiza el archivo de septiembre.
- Cerrar el Workbench detiene el coordinador. Todavía no existe un servicio que
  continúe con la ventana cerrada ni arranque automático del sistema.

## Implementación

| Pieza | Responsabilidad |
| --- | --- |
| `integrations/duas_source/` | 21 archivos en la línea base SHA256; adaptación de consultas vacías documentada abajo |
| `integrations/duas_source/worker.py` | Descarga en proceso aislado con Selenium original |
| `bots/detalles/daily.py` | Calendario persistente, horario, recuperación cronológica y append mensual |
| `bots/detalles/workbench_worker.py` | Comandos daily_run/daily_calendar, extracción y cancelación |
| `workbench/details_bridge.py` | Estados de descarga, extracción, espera y cierre para Qt |
| `workbench/qml/DailyCalendar.qml` | Calendario mensual navegable |

El proveedor es un proceso separado; sus imports no se mezclan con los motores.
Los repositorios originales del generador y de Detalles permanecen intactos.
En esta copia se adaptó `src/tica_dua_bot.py` y se agregó `src/query_confirmation.py`.
El manifiesto del proveedor conserva los hashes de la copia inicial; la diferencia
del extractor es intencional y no se oculta actualizando su hash histórico.
`bots/detalles/data/daily/bases.sqlite3` contiene las descargas verificadas por
régimen y fecha. `calendar.sqlite3` registra días, DUAs y tablas mensuales.
Los resultados siguen en `data/queues/`. Los bloqueos impiden dos coordinadores
sobre los mismos datos y protegen las tablas al agregar y consultar.
`DailyJobStore` reserva solo los DUAs del día en curso mediante una selección
temporal en SQLite. No procesa otros pendientes de la tabla mensual. La exportación
conserva todos los resultados del mes; el motor original de Detalles sigue intacto.

Cada día tiene una revisión estable para reimportar sin duplicar entradas ni
historia de origen tras un cierre. Los días vacíos válidos también se registran.
Una exportación fallida no completa el día; SQLite conserva los resultados.

La cancelación conserva los límites del generador: una navegación de Edge activa
puede tardar hasta su límite de tres minutos en devolver el control. No se mata
el navegador a la fuerza. Las esperas entre ciclos se cancelan al instante.

## Consultas sin registros y errores

El contador del formulario empieza en cero y no acredita una consulta. Un botón
Datos XML oculto tampoco basta. La adaptación observa la respuesta del POST de
**Confirmar** (`EENTER.`), vinculada al envío exacto de fechas, régimen y CAPTCHA.
No realiza otra consulta para decidir si la primera estaba vacía.

Solo acepta cero con HTTP 200, respuesta JSON completa, CAPTCHA aceptado por el
servidor, fechas/régimen coincidentes, filtros generales, mensajes vacíos, contadores
coherentes y grilla vacía confirmada. Comprueba también que el servidor mantiene
ocultos Datos XML y el mensaje del formulario. Con datos se conserva la descarga
XML y su validación original. La confirmación vacía se registra en los mensajes.

Error HTTP, redirección, CAPTCHA rechazado, mensajes del portal, otra fecha/régimen,
respuesta incompleta, falta de respuesta o cantidades inconsistentes mantienen el
rango pendiente. Ninguno de esos casos completa un régimen ni un día. Si TICA
cambia el formato, la respuesta desconocida queda pendiente para revisión.

Esto acredita lo que TICA respondió; no puede garantizar que los datos internos
del portal estén completos si el propio servidor devuelve una respuesta válida
pero incorrecta.

## Verificación acotada

- Ciclo local de dos días con nueve regímenes: 18 DUAs confirmados, calendario,
  CSV acumulado y reanudación sin nuevas descargas.
- Dos comprobaciones rápidas de calendario/SQLite: límite de 00:01, primer día
  pendiente, cambio de mes, días vacíos y append idempotente.
- Comprobación QML de guardar/iniciar; captura sin advertencias.
- Las fixtures del proveedor y de Detalles exigen almacenamiento fuera de la
  instalación normal; la comprobación inicial del ciclo fue offline.
- Diagnóstico real autorizado: solo EXPORTACION TEMPORAL del 11/10/2026, en
  `runtime/pruebas/`. El portal confirmó cero; el extractor inicial agotaba la
  espera de Datos XML y dejaba el rango pendiente. Se capturó la respuesta de
  Confirmar y el nuevo validador acreditó su vacío sin otra descarga posterior.
- Cuatro pruebas enfocadas de `tests/test_query_confirmation.py`: servidor HTTP
  local con Edge (vacío, datos, fallo HTTP y CAPTCHA rechazado), respuestas
  incompletas/inconsistentes y cobertura diaria con algunos/todos los regímenes
  vacíos. Sin consultar otros días ni regímenes reales.
- Selección QML de un rango anterior entre meses y comprobaciones rápidas de
  límite final, reanudación y reservas restringidas a los DUAs del día, sin red.
