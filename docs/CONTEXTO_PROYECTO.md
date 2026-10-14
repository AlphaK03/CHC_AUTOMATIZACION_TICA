# Contexto de CHC Workbench para una nueva sesión

Inicio mensual conjunto añadido el 13/10/2026. Vista general muestra **Iniciar bots
por mes → Elegir bots…** con mes/año, casillas de los cuatro DUA, cinco procedimientos
de Manifiestos y BLs, trabajadores independientes, modalidades y total. No hay
selección/inicio implícitos al abrir. `workbench/month_launcher.py` coordina únicamente
los bridges; `MonthStart.qml` es el formulario. No importa motores ni sustituye colas.
Meses terminados únicamente. DUA reutiliza daily_run con rango 1–último día y
configuración confirmada por requestId, revalidada antes del envío. Manifiestos
recibe el mes completo y filtros despejados, sin cambiar el procedimiento visible.
Los procesos ocupados se mantienen. BLs espera Conocimientos completo del mes y
modalidades exactos; admite observar una ejecución existente compatible sin detenerla.
Se rechazan bases parciales. El botón Detener cancela la planificación y solo detiene
trabajos propios; respuestas tardías, cambios de configuración, detención desde el
bot y cierre no pueden iniciar otra tarea. Las esperas de preparación tienen límite.
Las elecciones persisten al navegar, pero no son un calendario automático al reiniciar.
Pruebas: once casos de coordinación/errores/cancelación/cierre, una QML (casillas, cantidades,
mes, inicio/cancelación, dos anchos y temas) y dos recorridos con workers originales
aislados. DUA recupera un mes con 29 días vacíos ficticios confirmados y procesa el día
restante de forma local; los cuatro perfiles conservan intentos al repetir. Los cinco
procedimientos locales completos alimentan BLs; segunda ejecución conserva resultados
y la misma SQLite. El fixture negativo permanente también dejó BLs bloqueado correctamente.
El portal positivo se activa exclusivamente con `CHC_MANIFEST_FIXTURE_COMPLETE=1`
en procesos de prueba offline; fuentes y motores originales no se modificaron.
Smoke correcto; sin consultas a TICA ni inicio de un lote real durante verificación.
Se abrió la app en Vista general antes de documentar. Capturas aisladas en
`docs/preview/inicio-mensual*.png`. Uso y límites en el README del Workbench.

Corrección de actividad del 13/10/2026: al emitir `changed`, el QVariantList de
eventos volvía a asignarse a ListView y reiniciaba el scroll. `activity_model.py`
añade un QAbstractListModel estable por bot; inserta/recorta filas sin reiniciar
el modelo. `qml/components/ActivityView.qml` conserva los delegados visibles y
solo sigue novedades si estaba al inicio. Un Timer hijo cancela el seguimiento
al abandonar la página; desplazamiento y barra manual tienen prioridad. Se usa
en DetallesPage (los cuatro DUA) y en las seis vistas demo. Compatibilidad de
`events`, Limpiar vista y límites originales (2.000 reales/30 demo) conservada.
Las pruebas QML verificaron mensaje y offset con textos multilínea, actualizaciones
sin logs, ráfagas, repetidos, recorte del límite/final, seguimiento al inicio y
limpieza, sobre los cuatro DUA y seis demos. Pasaron dos pruebas nuevas, la de
configuración/inicio existente y smoke, con datos en memoria y sin TICA.
La app real estaba descargando en varios módulos: se conservó esa ventana y se
abrió/verificó la versión corregida en QML aislado antes de documentar. El cambio
se cargará al próximo arranque; no interrumpir consultas por un cambio visual.

Bitácora mensual añadida el 13/10/2026 por petición del usuario. Vista general
muestra meses del historial real, seis bots y detalle desplegable de los cinco
procedimientos de Manifiestos. `workbench/monthly_progress.py` utiliza lecturas
SQLite/JSON, sin motores ni cambios en datos; `monthly_bridge.py` actualiza desde
un hilo con refresco al entrar/manual, cada 30 segundos y eventos agrupados a 10 s.
Un mes pasado solo se marca Completado con cobertura mensual y resultados
verificados: calendario/días contra jobs para DUA, Mes original y cobertura de
Conocimientos para BLs, selección/EOF/resultados/finalización para Manifiestos.
Rangos parciales y filtros se distinguen; archivos manuales con nombre mensual
pueden quedar Lote listo, pero no acreditan mes completo. Un lote antiguo listo
no oculta ampliaciones pendientes ni una modalidad terminada oculta otra pendiente.
Fuentes ilegibles se señalan, datos sin mes identificable no se asignan por nombre
aproximado o fecha de creación. Demo excluida. Mes actual nunca se declara completo.
Pasaron nueve pruebas de cobertura/lectura y una QML con actualización asíncrona,
detalle, navegación, dos anchos y temas claro/oscuro, además del smoke existente.
Capturas aisladas en `docs/preview/bitacora-mensual*.png`; sin consultas a TICA.
La inspección de uso real mostró varios bots descargando. Se conservó la ventana
del usuario y sus workers; la versión nueva se abrió de forma aislada antes de
documentar. La bitácora se cargará en esa ventana al próximo arranque, sin detener
consultas para un cambio de interfaz. No se añadieron reinicios ni inicios automáticos.

Preferencia vigente del usuario: mantener la interfaz sencilla y cercana a la
clásica. Detalles abre directamente con Procesamiento y Configuración; Base de
datos se abre aparte. Exportación, actualización y compatibilidad clásica están
en Más; los parámetros técnicos quedan plegados. No repetir pruebas extensas
por cambios visuales: una comprobación breve basta; ampliar solo ante cambios
sensibles de motor, datos o recuperación.

Actualización visual del 13/10: Manifiestos muestra sus cinco procedimientos en
una barra horizontal que reutiliza `NavItem`, con iconos y selección similares a
la barra lateral. Cada procedimiento y BLs ofrecen Procesamiento y Configuración;
los parámetros avanzados quedan plegados. Historial, configuración y consultas
siguen independientes; cambiar de procedimiento no detiene otro. Las páginas
permiten desplazarse en ventanas pequeñas. Se verificaron los cinco accesos y las
dos vistas en temas claro/oscuro con almacenamiento aislado, sin TICA; pasó la
prueba QML existente Conocimientos → base → BLs. App actualizada abierta antes
de documentar. Capturas en `docs/preview/manifiestos-horizontal.png` y
`docs/preview/manifiestos-configuracion.png`.

Nombres automáticos de Manifiestos, 13/10: los cinco procedimientos generan
`mesYY` (por ejemplo `octubre26`, `enero27`) y muestran Tabla como solo lectura.
`chc_runtime/manifest_names.py` comparte selección y nombres entre Qt y worker,
sin cargar motores en la GUI. Las variantes llevan sufijos por modalidades,
intervalo, Courier, límite o IDs; nunca se publican selecciones diferentes encima
de otra. La misma selección/carpeta reutiliza el lote, incluso si cambian nombre,
hilos u orden de modalidades. Lotes históricos conservan identidad, rutas, nombre
y SQLite; no se fusionan ni migran resultados. BLs conserva sus nombres porque
puede reunir varios períodos. Pasaron tres pruebas offline de nombres/recuperación,
la prueba QML con Octubre 2026 → Enero 2027, las tres pruebas de integración de
Manifiestos y el smoke QML. App actualizada abierta antes de documentar.

Revisión BLs del 13/10: el panel recuperado mostraba hashes internos en la columna
Manifiesto/BL y los contadores pasaban a cero durante la preparación. El lote real
conservaba 18 BL Guardado con un intento y 34.835 pendientes; las dos entradas
preparadas compartían firma y SQLite. Los reintentos observados eran pendientes
por timeout, no BL confirmados repetidos. La revisión fue de solo lectura.
Se corrigieron `manifest_service.py` y QML: identidades originales desde payload,
fila de entrada, búsqueda por BL/manifiesto, eventos unificados por ordinal,
prioridad a trabajos en curso y contadores conservados durante prepare. El botón
muestra Continuar pendientes al retomar la misma selección. Ocho pruebas locales
pasaron: dos nuevas de presentación/reapertura parcial, tres BLs–Conocimientos y
tres de Manifiestos. Originales y datos operativos intactos; sin TICA. Se reabrió
una vez la app detenida, mediante cierre ordenado, en BLs antes de documentar.

Ampliación BLs del 13/10: el usuario pidió página, filas acumuladas por BL y
retomar el punto de interrupción. Implementado en `chc_runtime/bls_session.py`
y `bls_pages.py`, adaptadores sobre el motor original intacto. Página verificada
se persiste junto a `bls.sqlite3` en `bls_pages.sqlite3`, con la misma firma,
offset, EOF, filas y hash. Se conserva la reserva y se comprueba Detener antes
de guardar/confirmar. Reanudación por primera/última páginas verificadas y salto
al offset ancla; solo entonces sigue la siguiente. Cambios de contenido o de
paginación conservan el avance y dejan el BL pendiente para revisión. EOF lleno
repetido se verifica; parciales nunca entran al CSV confirmado. Datos/namespaces
y concurrencia por trabajador permanecen separados.
QML muestra Página y acumulación por BL; el total general indica filas confirmadas.
Recuperación se activa con Continuar pendientes, sin inicio automático al abrir.
Legacy Guardado sigue intacto; Página «—» cuando nunca se guardó por páginas.
Pasaron nueve pruebas del portal local, una de presentación y cuatro de conexión
BLs/reapertura; captura aislada `docs/preview/bls-paginas.png` sin advertencias.
Sin TICA nuevo; más variantes reales siguen pendientes. Se reabrió una sola vez
la app detenida en BLs antes de documentar, mediante cierre ordenado.

Objetivo del usuario, decisiones aceptadas y estado efectivo del repositorio.
Corrección adicional del 13/10: el usuario autorizó revisar en TICA los BLs
pendientes con timeout y reiniciar después de aplicar cambios. Diagnósticos
acotados y privados de las filas 19/20/22 verificaron una línea completa por BL.
TICA enviaba también GET al perder foco; el código esperaba solamente POST y
podía ignorar una coincidencia ya recibida. El adaptador registra antes de llenar,
acepta GET/POST validados y normaliza las propiedades GeneXus en `bls_search.py`;
conserva filtros, identidad, secuencia, esquema y mensajes como requisitos.
Pasaron 13 pruebas locales de búsqueda/páginas y cuatro de panel/conexión/reanudación.
También se validó con el nuevo parser la respuesta GET capturada en un timeout real.
Con la app detenida se respaldaron SQLite/checkpoints, sesión y CSV, y se confirmaron
solo esos tres diagnósticos completos mediante las reservas originales. El lote
`d0b9c747860c67b266dd488f` pasó de 45 BL/83 filas a 48 BL/86 filas; quedan 34.805
pendientes. Se verificó que todos los Guardado anteriores y sus filas quedaron
idénticos. Respaldo local: `bots/bls/data/backups/recuperacion-20261013-205135/`.
CSV interno/público actualizado; una única reapertura ordenada en BLs, sin lanzar
el lote completo. Diagnósticos bajo `bots/bls/data/diagnostics/`, sin publicarlos.
Fuentes originales verificadas intactas; adaptadores sin cambios en `bots/bls/src`.

Estado vigente al 13/10/2026: Detalles, Tránsito, Talón y XMovimientos están
integrados con el mismo soporte Python/SQLite y panel QML. También se integraron
BLs y Manifiestos: cinco procedimientos, creación local de bases BLs, importación
de progreso y una única instancia interactiva. Leer `INTEGRACION_MANIFIESTOS.md`.
La entrega nueva se comprobó con un portal local, sin nuevas consultas reales.
Talón y XMovimientos usan sus parsers v2 y la selección de cuatro regímenes de
`Total_DUAS - Importacion.xlsx`; reutilizan una caché común verificada, con
progreso independiente. Leer `INTEGRACION_IMPORTACION.md`: columnas originales,
paginación, agrupación de movimientos, comprobaciones y alcance real.
Incidente del 13/10: Detalles quedó con una reserva `005-2026-685571` activa por
horas y un worker huérfano bloqueando otra ventana. Se respaldó y recuperó el lote;
se añadieron límites del intento y limpieza, cierre de hilos acotado y protección
Windows de procesos hijos. Ver `INTEGRACION_DETALLES.md` para evidencia y límites.
Refuerzo posterior: otra reserva `001-2026-079444` impedía pasar a la segunda
ronda; la cancelación cooperativa anterior no liberó el intento. El supervisor
ahora usa esperas independientes (`bounded_result`) y solo él confirma SQLite;
acota también tareas residuales y cierre del driver. Todas las rondas usan los
hilos configurados. Se mantuvo la GUI y se reconectó solo Detalles: el DUA se guardó
y se observaron seis consultas simultáneas al retomar la ejecución del usuario.
Conservar la instancia del usuario mientras procesa: no repetir reinicios durante
verificaciones ni anunciar que puede reanudar antes de terminar los cambios.
Corrección posterior de Tránsito: la base real del 1 de octubre tiene 583 DUAs
TRANSITO verificados y formato equivalente al Excel original. Se corrigieron la
inicialización de atributos al entrar en la navegación común y la espera de LINEAS.
Un DUA real antes fallido guardó 3 líneas / 8 columnas en una salida de prueba
independiente; los 583 DUAs operativos se conservaron pendientes para el usuario.
Ver el incidente y su evidencia en `INTEGRACION_TRANSITO.md`.
Caso adicional confirmado: `001-2026-078194` termina en exactamente 50 líneas.
TICA repite esa última página con EOF confirmado; se corrigió la paginación para
aceptarla solo con identidad, contadores, filas y mensajes del servidor coherentes.
Reproducción real aislada y validación offline de su respuesta documentadas allí.
Contrato de salida vigente: Resultados contiene únicamente el CSV, dentro de una
carpeta con el nombre actual de la tabla. Sin UUID ni subcarpetas técnicas visibles.
Los TXT/JSON y diagnósticos se conservan internamente en `bots/detalles/data/exports/`.
Leer junto con `AGENTS.md` antes de continuar. Fecha: 13 de octubre de 2026.

## 1. Qué quiere lograr el usuario

El usuario utiliza varios bots para consultar el portal TICA. Quiere unificarlos
en **CHC Workbench**, una plataforma modular con interfaz moderna y panel lateral
expandible para acceder a cada bot de manera independiente. La plataforma y los
bots deben vivir en `D:/CHC_CONSULTORES/Repositorios/CHC_AUTOMATIZACION_TICA`.

Las metas finales son:

1. **Una aplicación de trabajo:** acceso a módulos, bases, lotes, estados,
   resultados y configuración desde el mismo Workbench.
2. **Un repositorio mantenible:** código organizado por responsabilidades,
   módulos independientes y servicios comunes donde hay compatibilidad real.
3. **Crecimiento modular:** añadir bots, scripts o herramientas mediante registros
   y contratos, sin rediseñar el núcleo ni copiar interfaces enteras.
4. **Independencia de aplicaciones auxiliares:** integrar generadores de bases
   y preparación para dejar de abrir otros programas y transferir Excel manualmente.
   Generar una base y consumirla desde uno o varios módulos dentro de la plataforma.
5. **Operación fiable:** preservar validaciones, datos como texto, ceros iniciales,
   resultados confirmados, reanudación y compatibilidad de exportaciones.
6. **Distribución propia:** instalación trasladable sin rutas, entornos virtuales
   ni repositorios de las aplicaciones originales.

No se busca solamente juntar accesos directos. Abrir interfaces existentes en
procesos separados puede ser una transición; el destino es una experiencia común
que utilice motores desacoplados de sus GUI anteriores.

## 2. Módulos iniciales y versiones correctas

| Módulo | Origen | Versión elegida | Destino |
| --- | --- | --- | --- |
| BLs | `BLs_BOT` | Código actual de la raíz | `bots/bls/` |
| Detalles | `Detalles_BOT` | Código actual de la raíz | `bots/detalles/` |
| DUAs Tránsito | `DuasTransito BOT` | Exclusivamente `v2/` | `bots/duas_transito/` |
| Talón | `Talon_BOT` | Exclusivamente `v2/` | `bots/talon/` |
| XMovimientos | `XMovimientos_BOT` | Exclusivamente `v2/` | `bots/xmovimientos/` |

Los orígenes están bajo `D:/CHC_CONSULTORES/Repositorios`. El nombre físico de
Tránsito tiene un espacio. El usuario aclaró expresamente que `v2/`, cuando
existe, contiene la versión requerida. Se aplanó solo ese nivel externo: su
`src/` pasa a la raíz del nuevo módulo. No recuperar los `src/` antiguos externos.

Se copió el estado actual en disco, incluidos cambios sin confirmar, no solo
HEAD. La evidencia queda en `docs/migration/`. Los originales se mantienen
intactos como referencia y operación existente.

## 3. Generadores de bases para integración posterior

Origen indicado: **`D:/PortafolioDesarrollador/DUAS_SCRAPPING`**.

Se revisó y después se copió/conectó para el piloto diario de Detalles. Guarda consultas verificadas
en SQLite y produce las listas Total, Tránsito e Importación con `NroDUA`. Debe
integrarse como proveedor de datasets con período, régimen, procedencia y cobertura.

El usuario confirmó la correspondencia exacta: `Total_DUAS.xlsx` alimenta
**Detalles**, `Total_DUAS - Transito.xlsx` alimenta **DUAs Tránsito**, y
`Total_DUAS - Importacion.xlsx` alimenta **XMovimientos y Talón**. Actualmente
genera estas bases de un mes terminado mediante una ejecución manual del generador.

La independencia solicitada incluye obtener las bases automáticamente desde cada
bot, sin selección de Excel, en modo mensual o por días ya pasados. En modo diario:
descargar ayer, procesar hasta terminar y esperar a las 00:01 del siguiente día
local (`America/Costa_Rica`); si al acabar hay otra fecha pasada elegible, continuar.
Recuperar días atrasados sin omitirlos, guardar progreso persistente y acumular
resultados en la tabla/CSV del mes consultado, sin duplicar ni sobrescribir éxitos.
El cambio de mes se determina por la fecha de los datos, no por cuándo acaba el bot.
Requisito completo, ejemplos y límites: [AUTOMATIZACION_DIARIA.md](AUTOMATIZACION_DIARIA.md).
Detalles tiene un piloto en `feature/detalles-base-diaria-calendario`: base propia
diaria, calendario, espera de 00:01 y acumulación mensual. No inicia al abrir;
requiere Iniciar automático. Leer `PILOTO_DETALLES_DIARIO.md`. Posteriormente se
integraron Tránsito, Talón y XMovimientos con el mismo coordinador y contratos.

Alcance posterior: el usuario pidió adaptar DUAs Tránsito con la tecnología y
estructura de Detalles. Ambos usan ahora `chc_runtime/`, workers aislados y el
mismo puente/componente QML. Tránsito conserva el parser de v2, ocho columnas y
varias líneas por DUA; guarda todas las páginas juntas en SQLite y exporta sus
líneas al CSV mensual. El proveedor recibe selección TRANSITO para este módulo,
no los nueve regímenes de Detalles. Datos y ajustes quedan separados por bot.
Leer `INTEGRACION_TRANSITO.md`: archivos, uso, compatibilidad, pruebas y límites.
Su validación inicial fue offline; los incidentes reales posteriores y sus
correcciones están registrados en `INTEGRACION_TRANSITO.md`.

Talón y XMovimientos también comparten `chc_runtime/`, con parsers propios:
Talón usa LIQDUA y el resumen de siete columnas Sftributos1; XMovimientos usa
MANAERMAR y agrupa/suma bultos en seis columnas. La base automática común vive en
`integrations/duas_source/data/importacion/bases.sqlite3`; el bloqueo del proveedor
evita descargas duplicadas. Cada bot conserva su calendario, cola SQLite,
configuración, proceso y CSV mensual. Los cuatro bots heredan el supervisor que
libera intentos bloqueados sin esperar indefinidamente su cancelación.

El usuario autorizó revisar EXPORTACION TEMPORAL únicamente del 11/10/2026.
TICA confirmó cero registros. Se corrigió la copia del proveedor para acreditar
vacíos mediante la respuesta de Confirmar, con CAPTCHA aceptado, fechas/régimen,
contadores y ausencia de errores verificados. Aplica a los nueve regímenes:
uno vacío no impide crear la base con los demás; todos vacíos confirmados también
acreditan el día. Un error nunca cuenta como vacío. Ver los criterios y pruebas
en `PILOTO_DETALLES_DIARIO.md`; la diferencia en el extractor respecto de su
manifiesto inicial es intencional. El generador original no se modificó.

BLs necesita la base BLS de Conocimientos/Manifiestos. Es distinta de las listas
DUA: cinco columnas de texto descritas en `docs/INVENTARIO.md`. La ruta de ese
proveedor y los demás scripts aún deben inventariarse; DUAS_SCRAPPING no resuelve
todas las entradas por sí solo.

Los motores deberán consumir datasets internos o SQLite directamente. Excel/CSV
permanecerán como formatos de compatibilidad, sin ser el paso obligatorio de
coordinación entre aplicaciones. La dependencia de TICA y un navegador permanece.

## 4. Decisión tecnológica de la interfaz

- **Python:** lógica de aplicación, automatización y motores existentes.
- **PySide6:** conexión entre objetos Python y Qt.
- **Qt Quick/QML:** pantallas, navegación, layouts, controles y transiciones.
- **SQLite:** persistencia local prevista; BLs/Detalles ya la usan.
- **Playwright:** motor activo de los cinco bots copiados. DUAS_SCRAPPING mantiene
  Selenium/Edge y requerirá su propia decisión de migración.

Aplicación de escritorio para Windows local, sin servidor web o frontend React.
No introducirlos por defecto. Si el usuario cambia a acceso multiusuario desde
navegador, revisar esa decisión con el nuevo alcance.

El panel tiene un entorno propio `workbench/.venv/` y requiere
`PySide6-Essentials==6.12.0`. No reutilizar entornos de otras aplicaciones ni
mezclar requisitos de todos los motores sin validarlos.

## 5. Estado real implementado

**Completado:**

- Plan de implementación y arquitectura futura.
- Cinco módulos: 127 archivos copiados, más once ejemplos/requisitos nuevos;
  138 archivos de módulos en la línea base SHA256.
- Registro `workbench/modules.json` con IDs y rutas relativas.
- Herramientas de importación y comprobación de integridad.
- Panel QML con barra expandible, búsqueda y temas claro/oscuro.
- Vista general y cinco espacios de prueba independientes.
- Backend sintético en memoria con carga de ejemplo, simulación, pausa,
  continuación, reinicio, progreso, resultados de muestra y actividad.
- Instalación/apertura mediante BAT y modos de verificación/captura.
- **Detalles integrado:** panel QML operativo y worker con entorno propio,
  importación/append, catálogo SQLite, consultas, detención, configuración,
  filtros, gestión con respaldos, 38 columnas y exportación recuperable.
- Preferencia de tema persistente y sesión del módulo conservada.
- Interfaz clásica de la copia como compatibilidad temporal, usando los mismos datos.
- 50 pruebas existentes y cinco de integración Qt/proceso/SQLite satisfactorias.
- Prueba real de dos DUAs originales: 38 columnas idénticas, sin repetir guardados.
  Tabla de validación instalada en el módulo nuevo; originales intactos.

Detalles de funciones, límites y evidencia: `docs/INTEGRACION_DETALLES.md`.

**Todavía pendiente:**

- Ampliar opciones avanzadas de BLs cuando se necesiten; su motor ya está integrado.
- Ampliar generación mensual desde el Workbench y validar más variantes reales
  del portal para los cuatro consumidores DUA ya integrados.
- Coordinar procesos, eventos, lotes, errores y concurrencia global.
- Desacoplar GUI antiguas y convertir imports a namespaces propios.
- Integrar los otros generadores/separadores y ampliar la caché compartida.
- Validar distribución de los cuatro motores integrados en un equipo limpio.
- Empaquetar la plataforma y comprobarla en un equipo limpio.

`docs/ESTADO_INICIAL.md` es la entrega histórica de copia. La situación actual del
panel está aquí y en `workbench/README.md`. Una simulación o pantalla terminada
no demuestra integración, instalación o comportamiento real del portal.

## 6. Alcance vigente y autorizaciones

La restricción inicial de trabajar solo en el prototipo fue ampliada por el usuario:
**conectar y hacer funcionar Detalles**, sin olvidar ninguna función del bot actual,
incluso mediante compatibilidad temporal. También autorizó usar sus bases originales
como prueba. Estas instrucciones posteriores prevalecen sobre la etapa de demo.

- La integración autorizada incluye Detalles, DUAs Tránsito, Talón, XMovimientos,
  BLs y los cinco procedimientos de Manifiestos con su generador de bases.
  BLs ya tiene un adaptador independiente. Los parsers v2 copiados permanecen intactos;
  el motor del Workbench utiliza los perfiles y servicios comunes.
- El usuario autorizó subir el estado actual a Git y crear la rama del piloto diario
  con proveedor propio y calendario. Datos, ajustes personales, entornos virtuales
  y binarios permanecen fuera de Git; las comprobaciones nuevas fueron offline.
- Los originales se leen como referencia, sin modificar fuentes, datos o entornos.
- La prueba real de esta entrega se limitó a dos DUAs, una ronda y un trabajador,
  en almacenamiento propio. Ambos resultados coinciden con el original.
- No se migró ni ejecutó la base completa de 72.290 DUAs. Una prueba pequeña no
  autoriza una descarga masiva automática como parte de validaciones rutinarias.
- El motor sigue aislado en un proceso; el backend de demo no importa `bots/`.
- Diferenciar siempre Detalles operativo de las cuatro demostraciones.
- Conservar motor, esquema y formatos actuales hasta que se autorice su refactorización.
- Las comprobaciones rutinarias de interfaz/proceso deben usar HTML local sin red.

No pedir de nuevo permiso para acciones ya autorizadas de la integración; progresar
con ese alcance y documentar comportamiento, pruebas y limitaciones reales.

## 7. Invariantes para integrar después

- BL, secuencia y DUA como texto, con ceros iniciales.
- Nombres, orden, esquema y clasificación de exportaciones compatibles.
- Resultado y éxito confirmados juntos. Un fallo no equivale a vacío validado.
- Índices de sesión o TXT históricos no demuestran resultados correctos.
- Importar o cambiar rutas no debe borrar ni sobrescribir progreso o resultados.
- Aislar módulos: hoy comparten nombres globales `core`, `utils`, `flows`, `ui`.
  No cargarlos juntos en un proceso hasta resolver sus namespaces.
- Tránsito/Talón/XMovimientos ya usan persistencia transaccional en el Workbench;
  no convertir sus índices/CSV históricos en prueba de éxito completo.
- Actualizar QML mediante eventos; no bloquear la interfaz con trabajos.
- Definir concurrencia global y conservar perfiles/cookies aislados.
- Los specs archivados de v2 contienen rutas antiguas: adaptar y validar antes
  de usar como compilación del monorepo.

## Incorporación de Manifiestos, BLs e instancia única — 13/10/2026

El usuario autorizó integrar `D:/PortafolioDesarrollador/Manifiestos_Bot2` manteniendo
su funcionamiento. También pidió una única instancia del Workbench. Implementado:
Manifiestos, Conocimientos, DUAs por manifiesto, Movimientos y Contenedores, con
configuración e historial independientes; generador de bases BLs y envío directo al
módulo BLs, cuyo motor pasa de demo a operativo. Tabla/Contenedores añaden SQLite;
los otros tres mantienen sus colas originales y sus excepciones. Los 28 archivos
Python copiados están intactos; la documentación original está en `docs/reference/`.

La GUI sigue siendo QML sencilla. Motores por proceso y protocolo JSONL en
`chc_runtime/batch_worker.py`, adaptación en `manifest_service.py`/`manifest_adapters.py`,
puente en `workbench/batch_bridge.py`. La interfaz no importa fuentes ni entornos de bots.
No usar el perfil DUA para estos procedimientos ni mezclar Movimientos con XMovimientos.

Pruebas locales enfocadas: cinco procedimientos, reanudación, vacíos y errores,
exclusiones, cancelación, copia de progreso intacta, CSV ajenos protegidos,
generación de base y procesamiento BLs mediante botones QML. No se hicieron nuevas
consultas reales a TICA. Se abrió la versión integrada antes de documentar y se
comprobó que una segunda apertura conserva la misma ventana.

Leer `INTEGRACION_MANIFIESTOS.md` y `bots/manifiestos/AGENTS.md` antes de cambios.
Pendiente: automatización diaria continua y calendario de Manifiestos/BLs, pruebas
reales acotadas de esta integración y ampliación de opciones avanzadas de BLs si se
necesitan. Los calendarios de los cuatro bots DUA permanecen operativos.

## 8. Cómo continuar desde otra sesión

Ampliación BLs del 13/10/2026: el usuario confirmó que la base generada desde
Conocimientos es su entrada y pidió usar meses/modalidades disponibles directamente.
Implementado **BLs → Desde Conocimientos → Elegir meses → Iniciar**: proveedor
aislado `bls_source`, disponibilidad verificada con SQLite y preparación automática
Courier=N antes de llamar al motor BLs original. Solo Marítimo/Aéreo; pendientes,
activos y selecciones limitadas no se ofrecen. Los rangos terminados se etiquetan
por sus días; no se presentan como meses completos. No hay inicio automático al
terminar Conocimientos: se actualiza el selector. Entrada manual y progreso previo
se conservan. Nuevas pruebas locales sin TICA, y versión actualizada abierta antes
de documentar. Leer `BLS_DESDE_CONOCIMIENTOS.md` para invariantes, rutas y alcance.

1. Leer este documento, `AGENTS.md`, README principal y manual del panel.
2. Revisar la nueva instrucción del usuario: pedir cambios visuales no autoriza
   automáticamente integrar o refactorizar motores.
3. Abrir `Abrir_Workbench.bat` o ejecutar la app con su entorno.
4. Continuar diseño desde `workbench/qml/` y `workbench/demo.py`.
   Detalles operativo usa `workbench/details_bridge.py`, `qml/DetallesPage.qml` y
   `bots/detalles/workbench_worker.py`; leer su matriz de funciones antes de cambiarlo.
5. Si se autoriza integrar, leer inventario e instrucciones del módulo elegido;
   definir contratos antes de cambiar el motor.
6. Registrar avances efectivos y limitaciones, sin confundirlos con el destino.

Comprobaciones disponibles sin bots:

```powershell
.\workbench\.venv\Scripts\python.exe workbench/app.py --smoke-test
.\workbench\.venv\Scripts\python.exe -m unittest discover -s workbench/tests -v
py -3.12 tools/verify_import.py --check-sources
```

La comprobación de copia compara la línea base inicial. Si una fase posterior
cambia motores de forma autorizada, documentar cambios y distinguirlos al verificar.
No reemplazar el manifiesto histórico para esconder diferencias. En esta integración
se agregaron adaptadores y archivos nuevos; las 138 fuentes/ejemplos iniciales
siguen coincidiendo con sus hashes y los originales siguen intactos.

## XMovimientos: vacíos y trabajo activo — 14/10/2026

A petición del usuario se consultaron tres pendientes de `octubre26`, una vez
cada uno y en almacenamiento aislado: `001-2026-078121`, `001-2026-078143`
y `002-2026-088749` (los dos primeros con NoMovimientosError; el tercero con
timeout). Los tres existen y devolvieron cero movimientos, identidad correcta,
sin paginación ni errores. Esta revisión no modificó la cola. Evidencia privada
en `runtime/xmovimientos_revision/20261014-001202/`.

El usuario después pidió registrar vacíos aparte de errores y admitir reconsultas.
Implementado en `chc_runtime/movement_empty.py`/`MovementsJobStore`: estado `empty`
con fecha/evidencia, cero filas CSV, historial conservado y sin reintentos automáticos
en cada ronda. Se verifican identidad, encabezado, cero filas y ausencia de mensajes
o paginación. Colas antiguas se amplían con respaldo/transacción y se reclasifican
solo desde HTML válido; no desde el tipo de excepción. **Base de datos → Reintentar
vacíos** consulta únicamente los elegidos o todos si no se seleccionan filas.
Incluye vacíos antiguos aún por verificar. Los días correspondientes se reabren;
el resultado nuevo pasa a Guardado/Vacío/Error según lo recibido. Los vacíos
confirmados permiten avanzar calendario y bitácora, contándose aparte de guardados.

Aplicación local: 679 vacíos clasificados, 881 DUAs y 2.028 filas confirmadas intactas;
todo el historial/cantidad de intentos permanece idéntico. Dos casos sin HTML se
presentan «Vacío por verificar», fuera de Errores; los otros errores y DUAs aún sin
consultar se conservan. Respaldo/comparación en `runtime/xmovimientos_revision/
migracion-vacios/`. No se volvió a consultar el lote real completo.

El usuario también pidió ver progreso BLs y priorizar trabajo activo. Los cuatro
bots DUA muestran DUAs en curso sobre Actividad sin mover el scroll del historial;
todos los procedimientos por manifiesto/BL muestran «Descargando ahora» y ordenan
Descargando antes del límite de 200 filas. BLs anuncia página 1 antes de esperar
la respuesta y muestra filas acumuladas/checkpoint. Los cambios simultáneos de
trabajador se emiten sin descartarlos por el límite temporal de notificaciones.

BLs conservaba 2.641 BL guardados y 4.578 filas. Se consultó aparte únicamente el
BL interrumpido `26560432` de `1-0-26360645-P036-02/09/26`: obtuvo una fila. Evidencia
en `runtime/bls_revision/20261014-011605/`, sin importarla al lote. No se reprodujo
ni se identificó la causa exacta de aquella parada: el log anterior no la guardó.
Ahora excepciones/motivo quedan persistentes en `bots/bls/data/logs/bls.log` e
historial; un error de acceso al JSON auxiliar en una notificación no aborta SQLite.
Se solicitó al usuario el mensaje de esa parada; no hubo respuesta durante el trabajo.

Validación: almacenamiento/migración/reconsulta/calendario, integración con portales
locales de Talón/XMovimientos, bitácora, QML de trabajo activo, scroll de Actividad,
BLs búsqueda/paginación/reanudación e inicio mensual. Smoke QML e integridad de
fuentes satisfactorios; parsers/copias originales intactos. App final abierta en
XMovimientos tras cierre ordenado sin consultas activas. Leer
`INTEGRACION_IMPORTACION.md` y `BLS_DESDE_CONOCIMIENTOS.md` antes de continuar.

### 14 de octubre de 2026: revisión visible y pendientes mensuales

Implementados `manual_review_data.py`, `chc_runtime/manual_review.py` y el
adaptador Qt `workbench/manual_review.py`: TICA en las filas sin guardar abre el
formulario nativo correspondiente al DUA, BL o consulta de Manifiestos. Proceso
aislado, navegador visible y cierre independiente; página conservada ante errores.
Lee SQLite sin mutar datos y guarda únicamente diagnósticos en
`data/manual_reviews`. No confirma descargas ni recorre todas las páginas.
La selección de detalle de BLs se comparte mediante `bls_search.py`; las utilidades
asíncronas comunes se extrajeron a `async_operations.py` sin importar parsers ajenos.

El modo diario de los cuatro bots de DUA limita a tres oportunidades persistentes
por pendiente, devuelve la oportunidad al cancelar y deja el día `omitted` cuando
se agota. También limita a tres las recuperaciones de una base pendiente. Sigue
al día siguiente y mantiene omitidos al reiniciar. `retry_month`/`retry_day`
rearman expresamente solo los pendientes del período, sin repetir guardados ni
alterar configuración. Calendario, filtro de omitidos y bitácora distinguen esos
casos; los días sin base también impiden una falsa finalización mensual.

Validación con portales locales y almacenamiento aislado: revisión de los cuatro
DUA, BLs y cuatro consultas de Manifiestos; identidad y ausencia de mutaciones;
presupuesto persistente, cancelación, avance al siguiente día y reintento mensual
real de Talón; botones QML durante descarga; bitácora, búsqueda/paginación BLs,
supervisión, calendario, estados vacíos, scroll y smoke QML. Sin consultas reales
nuevas ni cambios de prueba sobre bases de producción.

Esta entrega está en disco. La instancia abierta y sus workers siguen ejecutando
la versión anterior para conservar las descargas activas. Las nuevas opciones se
cargan al reabrir la aplicación; no se reinició la sesión del usuario.

Ampliación de revisión: **TICA / Abrir en TICA** también está disponible en las
filas guardadas de DUA, BLs y Manifiestos, y en el detalle del DUA. Solo se quitaron
las restricciones de visibilidad por estado: se conserva el mismo inspector de
solo lectura, sin extraer resultados a la base/CSV ni cambiar progreso.

### SharePoint opcional y respaldo Git

Por instrucción explícita se consolidó todo el trabajo anterior en `93ceb44`,
se avanzó `main` mediante fast-forward en su worktree limpio y se subió a
`origin/main`. Se creó `feature/sharepoint-oauth2` desde esa principal.

Implementado `chc_cloud/`, proceso `sharepoint_bridge.py` y diálogo **Cuenta y
SharePoint**: OAuth2/PKCE con MSAL, caché DPAPI, selección de sitio/biblioteca/
carpeta por bot o flujo y copia opcional de CSV. Eventos `published` tras exportar
localmente; outbox y cola SQLite durables, deduplicación, cuenta/destino capturados,
conflictos y actualizaciones condicionadas por `eTag`. Fallos cloud no modifican
descargas, SQLite de bots, calendario ni resultados locales. La app puede operar
sin cuenta y no inicia sesión automáticamente.

En la pestaña Entra abierta por el usuario se creó **CHC Workbench · Resultados
SharePoint**: cliente `da7ff4b7-8a2e-4c49-9338-17975a058a99`, directorio CHC
`f7015bc9-c229-413a-ab08-e1e5a76a09f1`, solo inquilino CHC, escritorio con retorno
`http://localhost`. Único permiso Graph `Sites.Selected` delegado, User.Read
predeterminado retirado, ningún secreto ni permiso de aplicación. Ver
`docs/SHAREPOINT.md` para asignar acceso `write` cuando se elija el sitio.

El usuario indicó que elegirá los destinos después. No se hizo login OAuth ni
subida real: falta autorización explícita al sitio y selección de carpeta.
Validación: 12 pruebas cloud, dos Qt/worker/DPAPI, dos integraciones Talón/XMov,
tres de Manifiestos (incluye cinco procedimientos y BLs), smoke QML y diff limpio.
La instancia anterior había sido cerrada por el usuario; app nueva abierta en
Vista general antes de documentar. Dependencias cloud instaladas solo en el
entorno Workbench; bots originales/copias preservados.

### Exploración de sitios y consentimiento de lectura

El usuario proporcionó la página **Bibliotecas** de CHC y autorizó expresamente
explorar todos los sitios a los que tenga acceso su cuenta. Se agregó
`Sites.Read.All` delegado a los ámbitos de la app, conservando `Sites.Selected`
para escritura. El usuario lo agregó manualmente en Entra; el botón de
consentimiento administrativo estaba deshabilitado.

Implementados catálogo Graph `/sites?search=...`, paginación, filtro al host CHC,
búsqueda por nombre y selección de sitio/biblioteca/carpeta. La URL
`/_layouts/15/sharepoint.aspx/onedrive/places` abre el catálogo; los enlaces
FileBrowser con id/listurl y Forms con RootFolder se normalizan al sitio real.
Se comprobaron en Edge seis entradas y sus URL, conservadas solo en runtime.

La sesión OAuth inicial del usuario está conectada; prueba real de lectura raíz
con `Sites.Selected` devolvió 403. Se renovó la conexión desde la app nueva y
Microsoft mostró **Se necesita la aprobación del administrador** para el ámbito
nuevo. Falta esa aprobación para comprobar sitios/bibliotecas/carpetas reales
por Graph. No subir resultados ni configurar destinos como parte de esta prueba.
15 pruebas cloud y dos Qt/worker/DPAPI, más smoke QML, pasaron. Se reabrió la app
una vez tras confirmar que sus procesos no tenían navegadores de bots activos.

### Registro reutilizado y comprobaciones reales satisfactorias

El usuario propuso usar **OAuth2 par CHC REPORTES**, cliente
`077e19a4-ab53-4e55-8286-ec02dc3cf36c`, y dejó su pestaña de permisos abierta.
Se comprobaron `Sites.Read.All` y `Files.ReadWrite.All` delegados y retornos de
escritorio existentes `http://localhost:62190/` y `http://localhost:5000`.
No se modificó ese registro. Workbench cambió al cliente existente y solicita
solo los dos ámbitos anteriores; no usa secretos ni permisos de correo/Power BI.
La conexión OAuth con la cuenta CHC fue satisfactoria. El bloqueo administrativo
del registro nuevo ya no aplica al cliente usado por la app.

Graph devolvió 7 sitios. Se leyeron bibliotecas y carpetas de Automatización TIC@
(Documentos, 15 carpetas originales) y TIC@_DUASxREGIMEN (Documents, 8). Se verificó
también el selector de la app con esos 7 sitios y Automatización TIC@ / Documentos.
El usuario autorizó expresamente una prueba de escritura con un archivo cualquiera:
se creó `CHC_Workbench_Prueba_20261014_163132/prueba_conexion.txt` en Automatización
TIC@ / Documentos, se subió y descargó idéntico; después se actualizó con eTag y se
comparó otra vez. Se conserva en SharePoint para revisión; informe privado en
`runtime/sharepoint-write-test/report.json`, enlace en `docs/SHAREPOINT.md`.

No se configuraron rutas de bots ni se enviaron CSV de producción. Se mantiene
la sesión conectada y la app abierta en el selector de esa biblioteca. 15 pruebas
cloud, dos Qt/worker/DPAPI y smoke pasaron; el registro nuevo inicial se conserva.

### Carpeta común, nombres estandarizados y subida exclusivamente manual

Alcance final solicitado: una sola carpeta madre local y una sola de SharePoint
para todos los bots, solo CSV públicos, nombres en mayúsculas con bot, mes/año y
modo cuando aplica. `chc_runtime/output_layout.py` define el contrato y registro
local común; `RESULTADOS/` es el valor predeterminado y queda fuera de Git.
Auxiliares y progreso permanecen internos. BLs separa sus filas por mes/modo real
del manifiesto. Selecciones parciales y lotes manuales conservan sufijos distintos.
Los históricos originales se conservan: **Exportar** los regenera desde SQLite
en la estructura común sin consultar TICA. Cambiar carpeta no mueve archivos.

La pantalla **Cuenta y resultados** reúne cuenta, carpeta local, carpeta online
y selector de mes. Elegir una carpeta no publica archivos. **Subir a SharePoint**
solo envía los CSV registrados de bots/procedimientos con ese mes cerrado y
completo verificado por `MonthlyReader`. No hay temporizador ni conexión de
eventos de exportación a subidas. Envíos fallidos requieren reintento explícito;
rutas por bot y avisos automáticos antiguos se conservan sin enviarlos.

Verificado: 18 pruebas cloud, dos Qt/DPAPI, cuatro del contrato de nombres y
12 integraciones de Detalles, Tránsito, Talón, XMovimientos, calendario diario,
cinco procedimientos de Manifiestos y BLs; smoke QML. La app actualizada quedó
abierta, con cuenta CHC conectada y destino común pendiente de elegir por el
usuario. No se subieron CSV de producción. README y `docs/SHAREPOINT.md` describen
el comportamiento vigente; los apartados anteriores registran su evolución.

Última aclaración del usuario: solo Detalles exige 100 % de DUAs guardados.
Los demás pueden completar excluyendo omitidos del resultado final, conservando
pendientes/páginas parciales para reintento. La bitácora incluye días omitidos
(y bases omitidas) para Tránsito/Talón/XMovimientos; Manifiestos y BLs admiten
exclusiones/intentos agotados en ejecuciones finalizadas, sin confundir una parada
con finalización. Mes actual pasa a **Al día** al cubrir hasta la última fecha
consultable, respetando 00:01 Costa Rica, y vuelve a comprobarse al avanzar fecha.

**Cierre manual…** en cada mes permite elegir bot/procedimiento y marcar completo
o restablecer comprobación automática. Metadatos separados en
`runtime/workbench/monthly_overrides.json`; no escribe en SQLite de bots.
Marca ligada a cobertura, contadores y revisión de intentos, invalidada al cambiar
datos. Detalles no permite cierre con DUAs sin guardar. SharePoint acepta estados
completos, al día y cierres manuales vigentes, solo mediante acción del usuario;
subir un mes no envía pendientes de otro mes. 19 pruebas cloud y 18 de bitácora/Qt
verifican las reglas vigentes, además de las integraciones de exportación anteriores.
