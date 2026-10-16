# Mantenimiento de CHC Workbench

- Leer primero `docs/CONTEXTO_PROYECTO.md`: objetivo final, stack, decisiones,
  restricciones y estado real para retomar desde otra sesión.
- Destino: una plataforma de escritorio modular Python + PySide6 + Qt Quick/QML
  que administre bots, bases, lotes y resultados desde un solo repositorio.
  Integrar generadores más adelante para eliminar aplicaciones auxiliares.
- Requisito confirmado de autonomía: leer `docs/AUTOMATIZACION_DIARIA.md`.
  Total_DUAS alimenta Detalles; Transito alimenta DUAs Tránsito; Importacion
  alimenta Talón y XMovimientos. Cada bot deberá obtener su base sin elegir Excel,
  con modos mensual y diario: día anterior, espera hasta 00:01 Costa Rica,
  recuperación de días atrasados y resultados acumulados en su mes correspondiente.
  Piloto diario de Detalles implementado en `feature/detalles-base-diaria-calendario`;
  leer `docs/PILOTO_DETALLES_DIARIO.md`. Los cuatro consumidores DUA están integrados.
- Alcance vigente ampliado: integrar y hacer funcionar Detalles, preservando
  todas sus funciones, SQLite, pendientes, validaciones, configuración y respaldos.
  El usuario autorizó usar datos base originales como prueba. Leerlos sin modificar
  los originales, probar una muestra acotada y usar almacenamiento/salida propios.
- Alcance ampliado por el usuario: integrar DUAs Tránsito con la estructura de
  Detalles, cambiando extracción y selección de base. Leer `docs/INTEGRACION_TRANSITO.md`.
  Talón y XMovimientos también están integrados; leer `docs/INTEGRACION_IMPORTACION.md`.
  BLs y Manifiestos ya están integrados; leer `docs/INTEGRACION_MANIFIESTOS.md`.
- Manifiestos tiene cinco procedimientos, un generador local de bases BLs y
  procesos independientes. BLs conserva su motor original aislado. Adaptadores:
  `batch_worker.py`, `manifest_service.py`, `manifest_adapters.py` y
  `workbench/batch_bridge.py`. No forzarlos al perfil DUA ni sustituir sus fuentes.
- Mantener instancia única con `single_instance.py`: otra apertura activa la
  ventana existente antes de crear workers. No interrumpir consultas al actualizar.
  Capturas y smoke quedan aislados, sin una nueva ventana interactiva.
- BLs obtiene su base desde Conocimientos terminados: leer
  `docs/BLS_DESDE_CONOCIMIENTOS.md`. El proveedor `bls_source` comprueba SQLite,
  ofrece solo Marítimo/Aéreo disponibles y prepara una instantánea sin tocar
  originales. Distinguir rangos terminados de un mes completo; no usar pendientes,
  páginas parciales, CSV ni filtros de IDs/límite como cobertura completa.
- Mantener separado el proveedor y el proceso BLs. Conservar reglas Courier N,
  firmas originales, texto/ceros, reanudación y compatibilidad por archivo.
  Detener la preparación debe impedir que una respuesta tardía inicie BLs.
- BLs añade paginación/reanudación mediante `chc_runtime/bls_session.py` y
  `bls_pages.py`, sin modificar las fuentes originales. Conservar la firma y
  reserva del motor, los checkpoints por BL y la verificación de primera/última
  páginas antes de seguir. Parciales no son Guardado ni CSV confirmado; validar
  identidad, secuencia, columnas, offsets, EOF y líneas sin duplicados. Nunca
  descartar un checkpoint incompatible ni inferir páginas para lotes antiguos.
- BLs captura AJAX antes de llenar/perder foco: TICA puede resolver la búsqueda
  por GET sin emitir el POST de Confirmar. `bls_search.py` valida los filtros
  GeneXus, mensajes, 24 columnas, manifiesto, BL y secuencia; nunca usar el DOM
  previo ni un timeout como ausencia. Cubrir GET y POST con el portal local.
- La infraestructura activa de los cuatro bots DUA está en `chc_runtime/`; los workers
  eligen un perfil. Compartir catálogo, cola, coordinador, puente Qt e interfaz,
  manteniendo configuración/datos/procesos separados. No duplicar este soporte.
- Tránsito usa exclusivamente TRANSITO para su base automática y conserva las
  ocho columnas y el parser de v2. Guardar todas las páginas y el éxito en una
  transacción; nunca confirmar el DUA con solo las primeras 50 líneas.
- Talón y XMovimientos usan la selección IMPORTACION (cuatro regímenes del
  generador original) y una caché verificada compartida en
  `integrations/duas_source/data/importacion/`. Mantener independientes sus colas,
  calendarios, configuraciones y resultados. Talón conserva siete columnas y el
  resumen Sftributos1; no paginarlo con el botón del grid Sftributos. XMovimientos
  conserva seis columnas y agrupa/suma bultos sobre todas las páginas del DUA.
  Mantener `MultiRowJobStore` común; no migrar índices/CSV antiguos como éxitos.
- XMovimientos registra `empty` con observación verificable de identidad, encabezado,
  cero filas y ausencia de errores/paginación (`movement_empty.py`). Separarlo de
  Guardado/Error: no generar filas CSV ni reintentos inmediatos. Permitir avanzar
  calendario/bitácora contando vacíos aparte. Reconsulta explícita `retry_empty`,
  acotada a vacíos elegidos/todos, reabre sus días y conserva historial/resultados.
  Migrar CHECK con respaldo y transacción; NoMovimientosError sin HTML válido
  permanece «Vacío por verificar», fuera del filtro Errores. Cubrir con
  `test_movement_empty.py`, `test_import_bots_bridge.py` y bitácora mensual.
- Mostrar los trabajos Descargando antes de limitar a 200 filas, para todos los
  procedimientos; mantener zona visible de trabajo activo fuera del historial.
  DUAs activos llegan con el progreso; BLs expone manifiesto/BL/página/filas.
  No forzar scroll del historial. `test_active_jobs*.py` cubre orden, actualizaciones
  simultáneas y QML. Registrar causas de parada BLs en su log persistente; fallar
  al escribir el historial JSON auxiliar no debe abortar un resultado SQLite.
- El usuario autorizó subir a Git y crear el piloto diario de Detalles con proveedor
  copiado desde DUAS_SCRAPPING y calendario persistente. Los orígenes quedan intactos.
  El modo automático se inicia por acción del usuario; verificar offline, sin
  descargas reales como pruebas rutinarias.
- En los nueve regímenes, cero registros solo acredita cobertura con respuesta
  confirmada de TICA para el envío exacto; no usar el cero inicial ni un botón XML
  oculto como prueba. Fallos de red, CAPTCHA, mensajes o respuestas incompletas
  quedan pendientes. Regímenes vacíos confirmados no impiden formar la base;
  si todos están vacíos y confirmados, registrar el día igualmente.
- El calendario permite elegir rangos pasados, incluso antes de Desde y entre
  meses. Por petición del 16/10, el diario normal continúa tras el rango elegido
  hasta ponerse al día y espera a las 00:01 de Costa Rica; al reabrir basta Iniciar.
  Mostrar el rango pendiente sin mover el origen persistido ni reabrir omitidos.
  Solo el inicio conjunto por mes y los reintentos explícitos se mantienen acotados.
  No consultar pendientes de otros días de la tabla mensual:
  conservar la selección diaria de DailyJobStore y el CSV mensual acumulado.
- Aislar cada motor en su propio proceso: la GUI Qt no importa paquetes de bots.
  El backend de demo nunca realiza consultas reales. No anunciar demos como éxitos.
- Las pruebas reales de esta integración están limitadas a dos DUAs de la base
  original y una ronda por DUA, con un trabajador y carpetas separadas.
- La interfaz clásica de la copia se conserva como compatibilidad temporal;
  no lanzar el ejecutable original ni depender de él.
- Interfaz en `workbench/qml/`; demo en `workbench/demo.py`; arranque en
  `workbench/app.py`; entorno propio `workbench/.venv/`.
- Actividad usa `activity_model.py` y `ActivityView.qml`: mantener inserciones
  incrementales y la fila/offset al leer; no reemplazar el modelo por un array
  al notificar contadores. Seguir novedades solo desde el inicio, con prioridad
  al desplazamiento manual. Temporizadores de scroll deben cancelarse al destruir
  la página. Ver `workbench/tests/test_activity_scroll.py` antes de modificarlo.
- Bitácora de Vista general: `workbench/monthly_progress.py` lee únicamente
  catálogos, calendarios y lotes existentes; `monthly_bridge.py` lo ejecuta fuera
  de Qt. No importar motores, iniciar descargas ni escribir en el progreso.
  Detalles requiere todos los DUAs confirmados. Los demás admiten omitidos fuera
  del resultado final sin borrar sus pendientes; días omitidos/base omitida y
  excepciones de lotes finalizados cuentan aparte. Mes actual puede estar «Al día»
  hasta la última fecha consultable (00:01 Costa Rica). Cierre manual por bot/
  procedimiento en metadatos separados; reversible, invalida al cambiar datos o
  intentos y nunca permite saltar DUAs pendientes en Detalles. La comprobación
  automática sigue exigiendo cobertura del período disponible;
  el nombre mensual de un archivo no prueba cobertura. Separar meses de BLs por
  payload y modalidades de Manifiestos; no sumar rangos entre modalidades.
  Pruebas aisladas en `test_monthly_progress.py` y `test_monthly_qml.py`.
- Inicio mensual explícito en `workbench/month_launcher.py` y `MonthStart.qml`:
  conservar procesos ocupados, scope mensual, trabajadores por proceso y firmas.
  DUA usa el rango acotado del coordinador diario; confirmar requestId/configuración
  antes de iniciar. BLs depende del mes/modalidades completos de Conocimientos.
  Cancelación/cierre/respuestas tardías no deben iniciar nuevos trabajos; detener
  solo tareas propias, no productores ya activos observados. No iniciar al abrir.
  Cubrir con `test_month_launcher*.py` y portales locales, sin lotes reales.
- Preferencia explícita del usuario: interfaz sencilla, similar a la clásica.
  Mostrar el flujo principal; evitar tarjetas, textos técnicos y opciones extra
  a la vista. Conservar funciones secundarias en menús, ventanas o secciones plegadas.
- En Resultados mostrar únicamente el CSV con el contrato común de bot/mes/modo,
  sin subcarpetas de UUID. TXT/JSON y diagnósticos son internos en
  `bots/<id>/data/exports/<id>/`; mantener SQLite y recuperación intactos.
- Ajustar la verificación al riesgo. En cambios visuales hacer una comprobación
  breve de carga/captura; no repetir suites completas ni consultas reales.
  Reservar pruebas amplias para cambios sensibles de motor, datos o recuperación.
- Al terminar cambios de código, abrir la app antes de documentar, por petición
  explícita del usuario. Mantener este orden en futuras sesiones.
- Si el usuario está ejecutando consultas, conservar su instancia abierta.
  Verificar en procesos y almacenamiento aislados; no reiniciar repetidamente
  para cada ajuste ni anunciar que puede reanudar mientras faltan cambios.
  Una app ya abierta satisface la preferencia anterior: no interrumpir el trabajo
  activo para abrir otra. El usuario reportó dos interrupciones por esos reinicios.
- Los plazos del motor deben supervisar tareas independientemente de su
  cancelación: `asyncio.timeout`/`wait_for` no bastan si la operación la ignora.
  Mantener `bounded_result`, la limpieza acotada del bucle y la confirmación de
  SQLite solo en el supervisor. Una extracción abandonada no puede guardar tarde.
  Las rondas de reintento usan todos los hilos configurados; probar también
  cancelación ignorada y paso a la siguiente ronda, con almacenamiento aislado.
- Actualizar README, contexto y manual del panel distinguiendo objetivo final,
  funcionalidad implementada y pendientes. La documentación debe servir de
  contexto autosuficiente a una nueva sesión.
- Leer `README.md`, `docs/PLAN_IMPLEMENTACION.md` y `docs/INVENTARIO.md`.
- Los repositorios originales son fuentes de referencia; hacer cambios aquí.
- Motores activos del Workbench: `chc_runtime/`, perfiles y
  `bots/<id>/workbench_worker.py`. Los parsers originales se importan de
  `bots/<id>/src/flows/`; las GUI y motores clásicos copiados son referencia.
  Tránsito, Talón y XMovimientos provienen de `v2/`; no incorporar los `src/`
  antiguos ni crear carpetas por versión.
- Cada módulo mantiene sus imports aislados. No importar varios motores en un
  mismo proceso mientras existan nombres globales `core`, `utils`, `ui`, `flows`.
- Preservar identificadores como texto, ceros iniciales, formatos de salida y
  resultados confirmados. No convertir índices de sesión en prueba de éxito.
- No borrar bases, progreso, entradas ni resultados durante reorganizaciones.
- La entrega inicial conserva las fuentes copiadas byte a byte. Una modificación
  futura del motor debe documentarse: el manifiesto registra la línea base inicial.
- Leer las instrucciones internas de cada módulo antes de cambiar su motor.
- Validar con `py -3.12 tools/verify_import.py` durante la etapa de copia.
  Las fases funcionales requieren pruebas offline por módulo y de recuperación.
- No consultar bases de producción para probar cambios. Las pruebas reales deben
  ser explícitas, acotadas y con una carpeta de salida independiente.
- No asumir que copiar el código demuestra independencia de generadores externos.
- No publicar ni desplegar automáticamente como parte de una revisión local.
- La revisión visible en TICA usa `ManualReview` y un proceso/guardia propios.
  Leer la selección de SQLite en modo solo lectura; nunca crear servicios ni
  recuperar trabajos al inspeccionar. No cerrar el worker de descarga.
  En Windows precargar parsers nativos antes de leer stdin y usar `os.read`
  para la señal de cierre: imports tardíos y lectores buffered bloquearon pruebas.
- El diario conserva `daily_automatic_attempts` entre reinicios y limita a tres
  oportunidades por pendiente; cancelar devuelve la oportunidad. `omitted` no
  se reabre automáticamente ni cambia a `completed` en el calendario. La bitácora
  mensual sí admite omitidos para los bots distintos de Detalles. Solo `retry_month` o
  `retry_day` rearman los pendientes del rango explícito, conservando guardados,
  historial y configuración. El mes actual se limita a días anteriores a hoy.
- SharePoint es opcional y exclusivo para copias CSV: leer `docs/SHAREPOINT.md`.
  Cliente público MSAL/PKCE, único directorio CHC y registro reutilizado
  `077e19a4-ab53-4e55-8286-ec02dc3cf36c`, solicitado por el usuario. Pedir solo
  `Sites.Read.All` y `Files.ReadWrite.All` delegados; no usar `.default`, secretos
  ni permisos de correo/Power BI que también existen en ese registro.
  Caché DPAPI, configuración y cola solo en `runtime/workbench/sharepoint`.
  Los eventos `published` se emiten después del reemplazo atómico local, sin
  importar librerías cloud en bots. Preservar worker online aislado, cola
  durable, cuenta/destino capturados, conflictos de propietario y `eTag`.
  Sin sitio elegido no hacer subidas reales; pruebas aisladas con Graph simulado.
- Todos los CSV públicos comparten carpeta madre local y destino SharePoint único.
  Contrato en `chc_runtime/output_layout.py`: nombres/carpetas en mayúsculas,
  bot/procedimiento, mes/año y modo real donde aplica. Preservar columnas, ceros,
  resultados originales y checkpoints; los auxiliares siguen en almacenamiento interno.
  BLs separa salidas por mes/modo del manifiesto. Nunca iniciar subidas al exportar,
  conectar ni abrir la app: solo `Subir a SharePoint` o reintento explícito, con
  estado completo, al día o cierre manual vigente en la bitácora. Avisos antiguos automáticos
  se conservan sin enviarlos. Reexportar históricos desde SQLite sin consultar TICA.
- Por instrucción del usuario, guardar los cambios en Git al cerrar cada entrega.
  Lo anterior a SharePoint quedó en `main` y `origin/main` en `93ceb44`;
  desarrollar SharePoint en `feature/sharepoint-oauth2` hasta indicación de integrar.
- El usuario autorizó explorar todos los sitios de su cuenta y luego reutilizar
  **OAuth2 par CHC REPORTES**, con lectura y escritura delegadas ya configuradas.
  OAuth y rutas reales Graph verificadas: 7 sitios; el selector Qt recorre
  bibliotecas y carpetas. Escritura real autorizada explícitamente por el usuario:
  archivo de texto en carpeta nueva de pruebas, lectura idéntica y actualización
  con eTag verificadas. No configurar destinos de bots ni subir sus resultados
  durante una prueba de conexión; ver `docs/SHAREPOINT.md` para evidencia.
  Aceptar Bibliotecas/places y FileBrowser/Forms con id/listurl/RootFolder;
  normalizar sitio y validar host sin reenviar tokens fuera de Microsoft Graph.
- En el selector SharePoint ejecutar navegación desde funciones del diálogo;
  cambiar el modelo destruye los delegados de ListView y su contexto de clic.
  Pasar identidad antes del cambio, probar sitio/biblioteca/subcarpeta con
  notificaciones síncronas y permitir elegir carpetas sin subcarpetas.
