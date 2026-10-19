# Actividad de los bots — 19/10/2026

La consola está implementada en Detalles, DUAs Tránsito, Talón, XMovimientos,
BLs y los cinco procedimientos de Manifiestos. Observa las operaciones existentes;
no cambia las consultas, hilos, reintentos, límites, pendientes ni resultados.

## Uso

En Procesamiento, **Actividad** muestra mensajes con hora y nivel. Lo más reciente
queda arriba. Al bajar para leer, las inserciones y actualizaciones de contadores
conservan la fila y el desplazamiento; volver arriba retoma el seguimiento.
**Ampliar/Reducir** ajusta su altura y **Limpiar** vacía solo la vista, sin borrar
bases, resultados ni archivos de registro. Conserva hasta 2.000 eventos por
bot/procedimiento durante la sesión.

La lista superior presenta las etapas activas y su duración. Incluye identidad
cuando está disponible, y permite desplazar las etapas de múltiples consultas.
Las tareas de coordinación pueden aparecer junto a sus consultas: cada fila es
una etapa, no necesariamente un hilo adicional.

Se muestran, entre otras, apertura de navegador/formulario, CAPTCHA, respuesta
HTTP, lectura/validación de páginas, reintentos, base diaria, espera de las 00:01,
lectura de progreso SQLite, exportación de CSV y actualización local de resultados.
BLs conserva la información de páginas/checkpoints y filas acumuladas. Un parcial
no se presenta como Guardado por emitir estos mensajes.

**Última señal del motor** mide cuándo se recibió un mensaje del proceso. Un hilo
de observación emite su etapa cada segundo incluso si el bucle de consultas está
esperando HTTP o ejecutando una operación síncrona. Cada 15 s añade un mensaje
«Sigue en…» con el tiempo de esa etapa. Esto acredita comunicación del proceso;
no acredita respuesta de TICA ni progreso de la descarga. El reloj de la vista
continúa mientras espera otra señal. Tras diez segundos sin mensajes muestra
«Sin señales del motor…»; no declara automáticamente un bloqueo ni cancela.

DUAs por manifiesto conserva su espera HTTP ilimitada (`timeout=0`, un intento,
sin recuperación interna de errores). La consola la identifica y mantiene
**Detener**. Los demás plazos y supervisores tampoco cambian. Una tarea que perdió
su supervisor deja de aparecer activa aunque ignore su cancelación.

## Implementación y verificación

- `chc_runtime/activity.py`: observador stdlib por tarea/hilo, contexto de identidad,
  sesiones por comando y transmisión JSONL. Nunca lee SQLite ni realiza red.
- `manifest_activity.py`: envolturas en memoria de adaptadores, HTTP y parsers;
  mantiene callbacks y fuentes originales intactos. El log de los motores Batch
  se transmite a Qt y continúa guardándose en `data/logs/<procedimiento>.log`.
- `playwright_processor.py`, `transit.py`, `import_bots.py`, `bls_session.py` y
  `daily.py`: etapas alrededor de las operaciones existentes; sin nuevos plazos,
  acciones de portal o escrituras de resultados.
- `workbench/live_activity.py`: última señal/tiempos y modelo incremental de etapas.
  `activity_model.py` conserva el historial incremental existente. Las lecturas
  de solo consulta concurrentes de DUA no cierran ni reinician el monitor activo.
- `ActivityConsole.qml`/`ActivityView.qml`: consola común; texto plano para mensajes,
  ajuste de línea, desplazamiento independiente y temporizadores hijos de la vista.

Pruebas nuevas: `chc_runtime/tests/test_activity.py`, `test_manifest_activity.py`,
`workbench/tests/test_live_activity.py` y `test_activity_console_qml.py`.
Cubren trabajo síncrono, concurrencia, tareas abandonadas, señales atrasadas,
conservación de respuesta/callback/timeout ilimitado/cancelación y ajustes en
1000×600/1440×900, ambos temas, seis perfiles y cinco procedimientos.
Las pruebas de workers de Manifiestos y reanudación BLs también verifican que
las etapas lleguen al modelo real de Qt y que sus resultados conserven intentos,
identidades y salidas previas. El portal de todas estas pruebas es local/simulado.

La comprobación de la interfaz se hace fuera de la instancia activa. Conservar
las consultas del usuario: la nueva consola se cargará al próximo arranque que
él decida hacer. No es una investigación de rendimiento con datos de producción
ni garantiza que un portal externo responda antes.
