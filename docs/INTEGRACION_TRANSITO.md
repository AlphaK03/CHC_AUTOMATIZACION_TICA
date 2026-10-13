# DUAs Tránsito integrado en CHC Workbench

El usuario amplió el alcance para integrar DUAs Tránsito con la tecnología,
estructura y experiencia de Detalles. Se utiliza exclusivamente el código de
`DuasTransito BOT/v2`, ya copiado en `bots/duas_transito/`. Los originales y los
138 archivos de la línea base inicial permanecen intactos.

## Uso

1. Abrir el Workbench y seleccionar **DUAs Tránsito** en la barra lateral.
2. En **Manual**, elegir la base `Total_DUAS - Transito.xlsx`, su hoja y el nombre
   de tabla. La importación guarda DUAs en SQLite y no consulta el portal.
3. En **Diario automático**, elegir Desde y, opcionalmente, Hasta en Calendario.
   Descarga solo TRANSITO del día, procesa sus DUAs y continúa por orden de fecha.
   Un rango termina al completar Hasta; sin Hasta espera hasta las 00:01 de Costa Rica.
4. Elegir la carpeta de resultados, revisar Configuración y pulsar Iniciar.
5. Detener o cerrar conserva resultados, intentos, bases y calendario. Para
   continuar, abrir la tabla o iniciar de nuevo el ciclo diario.
6. En Base de datos, seleccionar un DUA y abrir su resultado. Si tiene varias
   líneas, el selector permite revisar cada una de ellas.

En un equipo nuevo ejecutar `Instalar_Workbench.bat`, `Instalar_Transito.bat` y
`Instalar_Base_Diaria.bat`. Python 3.12, Chromium y Edge WebDriver son necesarios
para extracción y descarga respectivamente. El módulo tiene `.venv/` propio,
con las mismas versiones fijadas y verificadas que Detalles. No utiliza el
entorno de Detalles ni exige instalar los repositorios originales.

```powershell
.\workbench\.venv\Scripts\python.exe workbench/app.py --page duas_transito
```

Agregar `--daily` muestra el modo diario sin iniciar consultas. Tránsito y
Detalles funcionan en procesos separados; cambiar de página no detiene los motores.

## Infraestructura compartida

`chc_runtime/` deriva de los componentes probados de Detalles y centraliza el
catálogo, la cola, normalización, CAPTCHA, formulario, navegación, reintentos,
exportación, mensajes, coordinador diario y protocolo JSONL. Los imports internos
usan el namespace `chc_runtime`, evitando conflictos con los `core` originales.

Los workers de ambos bots son entradas pequeñas que eligen un perfil. Los
perfiles en `chc_runtime/profiles.py` indican extracción, columnas, persistencia
del resultado, selección de base y nombres de CSV. La GUI usa el mismo puente
Qt, `DetallesPage.qml` y `DailyCalendar.qml`, con una instancia por módulo.

Detalles mantiene su esquema de 38 columnas y sus bases existentes. Su motor
Workbench usa ahora el componente común derivado del original; la copia de su
motor y la interfaz clásica permanecen intactas y compatibles con la misma cola.
La integración de Tránsito no necesita importar el código ni los datos de Detalles.

Las configuraciones, sesiones, colas, resultados y calendarios se separan por
`bots/<id>/`. El proveedor recibe `--selection total` para Detalles y
`--selection transito` para Tránsito. Este último consulta únicamente TRANSITO:
la ausencia de los otros ocho regímenes no impide validar su base.

## Extracción y resultados de Tránsito

Se reutiliza el parser original `src/flows/transito_flow.py`, sin modificar su
selección de columnas, orden, limpieza o recurso histórico. La extracción conserva:

| Campo | Origen |
| --- | --- |
| Item | Primera celda de cada línea |
| Partida | Segunda celda; texto y ceros iniciales |
| Descripción_Comercial | Cuarta celda |
| Bultos | Quinta celda |
| Tipo_de_Bulto | Sexta celda |
| Nombre_del_consignatario | Séptima celda |
| Declaración_de_origen_de_China | Decimotercera celda |
| numero_del_dua | Identidad de las tres etiquetas del DUA |

El flujo conserva DETALLE → LINEAS → `SeriesContainerTbl` y SIGUIENTE al alcanzar
50 filas. Continúa por las páginas adicionales disponibles, verificando identidad,
cantidad de filas, campos e ítems únicos. Un fallo, página repetida, línea truncada
o DUA diferente deja el trabajo pendiente; no publica solo las primeras 50 filas.

Una fila de `jobs` representa un DUA; su JSON de resultado contiene todas las
líneas en `rows`. El estado succeeded y el conjunto completo se guardan en una
transacción. El CSV aplana esas líneas, con los ocho campos originales, UTF-8 BOM
y reemplazo atómico. El contador del panel cuenta DUAs; el CSV puede tener muchas
más filas. Limpiar completados conserva sus conjuntos de líneas en retained_results.

Un DUA sin líneas sigue pendiente para revisión/reintento y aparece en el reporte
interno sin_filas. No confundirlo con una descarga diaria TRANSITO vacía: si TICA
confirma cero DUAs para el régimen y fecha, la base vacía y ese día sí son válidos.
Los criterios de confirmación del proveedor están en `PILOTO_DETALLES_DIARIO.md`.

El recurso original `Names_TicaPortal.xlsx` se conserva. El camino activo usa
`config/captcha_lookup.json`, convertido de sus 191 entradas, sin leer Excel en
cada consulta ni depender del catálogo de otro bot.

## Datos y compatibilidad

| Ruta dentro de bots/duas_transito | Contenido |
| --- | --- |
| config/machine.json y session.json | Ajustes y última tabla de este módulo |
| data/queues/ | Catálogo SQLite, DUAs, resultados completos e intentos |
| data/queues/backups/ | Respaldos antes de retirar filas o tablas |
| data/daily/bases.sqlite3 | Consultas de TRANSITO por día |
| data/daily/calendar.sqlite3 | Días, DUAs y tablas mensuales |
| data/exports/&lt;id&gt;/ | Procesados, pendientes, sin_filas y diagnósticos |
| logs/ | Registros técnicos del worker y proveedor |

La carpeta pública elegida contiene solo `<tabla>/Transito_DUAS_<tabla>.csv`.
Los resultados de cada día se acumulan en su mes. `DailyJobStore` restringe las
reservas a los DUAs del día para no consultar otros pendientes de la tabla mensual.

La sesión antigua por índice y los TXT no acreditan resultados completos. No se
importan automáticamente como éxitos ni se migran CSV antiguos cuyo contenido
pueda estar limitado a dos páginas. Las fuentes de la interfaz clásica siguen
disponibles como referencia; ese modo anterior tiene su propia persistencia y
no se ofrece como un acceso que comparta las tablas SQLite nuevas.

## Verificación y límites

- Integración Qt → worker → Chromium local: 52 líneas en dos páginas, CSV y
  visor completo; error HTTP en la segunda página conserva el DUA pendiente.
- Dos días de base simulada: solo TRANSITO, un DUA por día, calendario completo,
  rango detenido al final, reanudación sin descargas duplicadas y sin procesar
  otro pendiente del mes. Limpieza conserva 156 líneas en el caso del mismo mes.
- QML: guardar/iniciar, seleccionar rangos anteriores y dirigir las órdenes de
  Tránsito a su propio puente sin enviar órdenes a Detalles.
- Cinco pruebas de integración existentes de Detalles y cuatro de calendario:
  satisfactorias tras extraer la infraestructura común.
- Captura operativa `preview/transito-integrado.png`: módulo listo, cero advertencias.
- Verificación SHA256: los 138 archivos de la línea base inicial siguen intactos.

Estas comprobaciones no consultaron TICA ni importaron bases de producción como
pruebas. La navegación real de Tránsito todavía requiere una ejecución del usuario;
no se presenta la fixture como extracción real. Cerrar la app detiene ambos
coordinadores: no hay un servicio de Windows que siga ejecutándose sin la ventana.
