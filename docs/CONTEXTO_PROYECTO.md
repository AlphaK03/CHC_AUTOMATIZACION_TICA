# Contexto de CHC Workbench para una nueva sesión

Preferencia vigente del usuario: mantener la interfaz sencilla y cercana a la
clásica. Detalles abre directamente con Procesamiento y Configuración; Base de
datos se abre aparte. Exportación, actualización y compatibilidad clásica están
en Más; los parámetros técnicos quedan plegados. No repetir pruebas extensas
por cambios visuales: una comprobación breve basta; ampliar solo ante cambios
sensibles de motor, datos o recuperación.

Objetivo del usuario, decisiones aceptadas y estado efectivo del repositorio.
Contrato de salida vigente: Resultados contiene únicamente el CSV, dentro de una
carpeta con el nombre actual de la tabla. Sin UUID ni subcarpetas técnicas visibles.
Los TXT/JSON y diagnósticos se conservan internamente en `bots/detalles/data/exports/`.
Leer junto con `AGENTS.md` antes de continuar. Fecha: 12 de octubre de 2026.

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
requiere Iniciar automático. Leer `PILOTO_DETALLES_DIARIO.md`. Los otros tres
consumidores DUA siguen pendientes en la entrega inicial; Tránsito se integró después,
como se describe a continuación.

Alcance posterior: el usuario pidió adaptar DUAs Tránsito con la tecnología y
estructura de Detalles. Ambos usan ahora `chc_runtime/`, workers aislados y el
mismo puente/componente QML. Tránsito conserva el parser de v2, ocho columnas y
varias líneas por DUA; guarda todas las páginas juntas en SQLite y exporta sus
líneas al CSV mensual. El proveedor recibe selección TRANSITO para este módulo,
no los nueve regímenes de Detalles. Datos y ajustes quedan separados por bot.
Leer `INTEGRACION_TRANSITO.md`: archivos, uso, compatibilidad, pruebas y límites.
Se validó offline y se abrió la app antes de documentar, siguiendo la preferencia
del usuario. No se hicieron consultas reales de extracción de Tránsito.

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

- Integrar BLs, Talón y XMovimientos; sus pantallas siguen siendo demos.
- Extender a los otros tres consumidores la autonomía diaria ya implementada en
  Detalles y ampliar generación mensual desde el Workbench.
- Coordinar procesos, eventos, lotes, errores y concurrencia global.
- Desacoplar GUI antiguas y convertir imports a namespaces propios.
- Completar las otras selecciones de DUAS_SCRAPPING y otros generadores/separadores.
- Validar instalaciones de los otros cuatro motores en su nueva ubicación.
- Empaquetar la plataforma y comprobarla en un equipo limpio.

`docs/ESTADO_INICIAL.md` es la entrega histórica de copia. La situación actual del
panel está aquí y en `workbench/README.md`. Una simulación o pantalla terminada
no demuestra integración, instalación o comportamiento real del portal.

## 6. Alcance vigente y autorizaciones

La restricción inicial de trabajar solo en el prototipo fue ampliada por el usuario:
**conectar y hacer funcionar Detalles**, sin olvidar ninguna función del bot actual,
incluso mediante compatibilidad temporal. También autorizó usar sus bases originales
como prueba. Estas instrucciones posteriores prevalecen sobre la etapa de demo.

- La integración autorizada incluye Detalles y DUAs Tránsito. BLs, Talón y
  XMovimientos siguen pendientes; no se modifican sus motores.
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
- Tránsito/Talón/XMovimientos necesitan persistencia más fiable que sus índices
  antes de ofrecer las garantías actuales de BLs/Detalles.
- Actualizar QML mediante eventos; no bloquear la interfaz con trabajos.
- Definir concurrencia global y conservar perfiles/cookies aislados.
- Los specs archivados de v2 contienen rutas antiguas: adaptar y validar antes
  de usar como compilación del monorepo.

## 8. Cómo continuar desde otra sesión

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
