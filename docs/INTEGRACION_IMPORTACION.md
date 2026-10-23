# Talón y XMovimientos en CHC Workbench

Actualización del 14 de octubre: ambos bots aplican tres intentos automáticos
persistentes por pendiente en modo diario. Al agotarlos dejan el día **Omitido**
y continúan; solo **Reintentar mes/día** reactiva los pendientes del período.
La lista ofrece **Abrir en TICA**, una consulta visible independiente que no
guarda ni cambia estados. En Talón una consulta sin tributos sigue pendiente de
revisión; no se convirtió automáticamente al estado **Vacío** de XMovimientos.
Véase [Workbench](../workbench/README.md#revisión-en-tica-y-recuperación-de-pendientes).

Integración del 13 de octubre de 2026, autorizada para ambos bots con la estructura
de Detalles y Tránsito. Se utilizan los parsers de **v2**, conservados sin cambios
en `bots/talon/src/flows/talon_flow.py` y
`bots/xmovimientos/src/flows/xmovimientos_flow.py`. Los 138 archivos de la línea
base inicial mantienen sus SHA256. BLs es el único módulo que continúa en demo.

## Uso

1. Seleccionar **Talón** o **XMovimientos** en la barra lateral.
2. En Manual, importar `Total_DUAS - Importacion.xlsx`, elegir hoja y tabla. Ambos
   aceptan la misma columna `NroDUA` como texto `NNN-YYYY-NNNNNN`; importar no consulta TICA.
3. En Diario automático, elegir Desde y, opcionalmente, Hasta en Calendario.
   El propio bot obtiene la base, procesa cada día y acumula sus resultados en el mes.
4. Elegir Guardar en, revisar Configuración y pulsar Iniciar. Los modos no arrancan
   consultas al abrir la app. El rango avanza con el progreso: continúa después de
   los días elegidos y espera hasta las 00:01 de Costa Rica cuando queda al día.
   Al reabrir basta Iniciar; los días completados u omitidos no se repiten.
5. Detener conserva los éxitos y pendientes. El visor de Base de datos permite
   seleccionar cada tributo o movimiento de un DUA, con su historial y evidencia.
6. Resultados contiene solo el CSV final, dentro de la carpeta del nombre de tabla.
   Los archivos auxiliares y diagnósticos quedan en el almacenamiento interno del bot.

Instalación: `Instalar_Workbench.bat`, `Instalar_Talon.bat`,
`Instalar_XMovimientos.bat` e `Instalar_Base_Diaria.bat`. Cada módulo tiene su
propio `.venv`, lockfile y catálogo CAPTCHA generado de su propia copia de
`Names_TicaPortal.xlsx` (191 entradas). No necesita abrir ni instalar los
repositorios originales o el bot de Detalles.

## Base compartida, progreso independiente

La selección es exactamente la que construye `Total_DUAS - Importacion.xlsx`:

- IMPORTACION DEFINITIVA
- IMPORTACION TEMPORAL
- REIMPORTACION
- REIMPORTACION PERFECCIONAMIENTO PASIVO

En uso normal ambos reutilizan
`integrations/duas_source/data/importacion/bases.sqlite3`. El proveedor serializa
el acceso mediante un bloqueo independiente `.proveedor.lock` y consulta solo
rangos sin cobertura verificada. Si ambos solicitan el mismo día, uno espera y
después lee la base ya guardada: no descarga otra vez los cuatro regímenes.
La espera se puede cancelar. Si el primero se detiene, el otro puede continuar
las partes pendientes. No se reutilizan vacíos sin confirmación de TICA.

Cada bot conserva en su propia raíz `config/`, `data/queues/`,
`data/daily/calendar.sqlite3`, `data/exports/` y `logs/`. Terminar Talón no marca
completado XMovimientos. Sus procesos, sesiones, resultados y bloqueos de ejecución
son independientes. El almacenamiento aislado y la fixture usan una base propia
para no mezclar datos de pruebas con la caché compartida de operación.

## Extracción y formato conservados

| Bot | Navegación y tabla original | Columnas, en orden de CSV |
| --- | --- | --- |
| Talón | DETALLE → LIQDUA → Sftributos1ContainerTbl | Codigo_Aduana, Año, Numero, Tributo, Descripcion_tributo, Valor_MN, numero_del_dua |
| XMovimientos | MANAERMAR → SubstkContainerTbl | Deposito, Año, Movimiento, Tipo_de_Movimiento, numero_del_dua, Cantidad_de_Bultos_asociada |

Talón conserva una fila por tributo y la limpieza original del texto e importes;
no sustituye el resumen por el desglose por artículo. Una página real de LIQDUA
mostró nueve tributos en el grid `Sftributos1` (gxgridid 42) y 97 filas en
`Sftributos` (gxgridid 19). Su botón SIGUIENTE controla el segundo: ahora se
comprueba la asociación al grid para no paginar la tabla equivocada.

XMovimientos conserva la conversión original de comas como separador de miles y
la suma por Deposito/Año/Movimiento/Tipo_de_Movimiento/DUA. Si hay páginas,
se reúnen sus filas antes de aplicar una sola vez el groupby original: las
combinaciones repetidas entre páginas también se suman. Se rechazan cantidades
no finitas y resultados con identidad incorrecta.

La paginación del grid pertinente se extrae completa. Una respuesta repetida
solo puede acreditar fin si EOF, identidad, contadores y valores de TICA lo
confirman; un error HTTP, una fila incompleta o una repetición sin confirmar
deja pendiente el DUA completo. No se guarda solo la primera página.

`MultiRowJobStore`, compartido también con Tránsito, confirma todas las filas
y el éxito del DUA en una transacción SQLite. Los CSV mensuales se reconstruyen
desde esos resultados y conservan las filas archivadas al limpiar la tabla.
Nombres: `Talon_DUAS_<tabla>.csv` y `xMovimiento_DUAS_<tabla>.csv`, UTF-8 con BOM.
Los TXT, índices y CSV antiguos permanecen como referencia; no se convierten
automáticamente en prueba de extracción completa.

Un DUA de Talón sin tributos queda pendiente y aparece en `sin_filas.txt`.
Desde el 14/10/2026, XMovimientos registra **Vacío** cuando se verifica la identidad,
el encabezado de Substk, cero filas y ausencia de errores/paginación. Es una consulta
completada sin movimientos por ahora, distinta de Guardado y de Error. No produce
filas CSV; conserva fecha/evidencia en `empty_observations`, `sin_filas.txt` y
`vacios.json` internos. El calendario y la bitácora cuentan guardados y vacíos por
separado; ambos permiten avanzar si todo el día está consultado. Los vacíos no se
repiten en cada ronda: **Base de datos → Reintentar vacíos** consulta los elegidos,
o todos si no hay selección. Reabre los días correspondientes; una respuesta nueva
con datos pasa a Guardado y un fallo real queda pendiente con su error.
La actualización de colas antiguas crea respaldo y amplía el CHECK de estado en
una transacción, conservando rowid, referencias, resultados e intentos. Solo reclasifica
NoMovimientosError con HTML válido; los que carecen de evidencia se muestran como
**Vacío por verificar**, fuera del filtro Errores, y también admiten reconsulta.
Esto es distinto de un régimen diario sin DUAs, cuyo vacío verificado sí permite
completar la base. Ambos módulos heredan el supervisor corregido, todos los hilos
en cada ronda, protección de procesos y cancelación. El plazo se renueva al
confirmar una página para permitir consultas extensas que siguen avanzando.

## Evidencia resumida de XMovimientos

Cambio del 22/10/2026 en el runtime del repositorio. Solo XMovimientos sustituye
la página completa por una ficha HTML de hasta 32 KiB con JSON legible embebido:
DUA solicitado/observado, fecha UTC, encabezados y conteos de Substk, mensajes,
paginación y hasta tres filas de muestra. Incluye tamaño y SHA-256 de la respuesta
original e identidades del formulario/envío cuando existen. Textos y muestras
tienen límites. Excluye GXState, tablas ajenas, CAPTCHA, sesiones y parámetros de
URL. No permite reconstruir la página completa; SQLite conserva error e historial.

La decisión de Vacío exige la misma identidad correcta, una sola fila con al
menos cinco encabezados, cero datos/errores y ningún SIGUIENTE habilitado.
El lector admite HTML antiguo y resúmenes con versión y comprobaciones válidas.
Formato desconocido, JSON corrupto o conteos contradictorios no acreditan vacíos.
El supervisor valida antes del COMMIT; no se cambian parsers, CSV ni calendarios.
Talón, Tránsito y Detalles conservan sus diagnósticos originales.

`Resumir_Evidencias_XMovimientos.bat` muestra el destino, revisa cinco ejemplos
sin cambios y pide `BORRAR` exacto para convertir todos los diagnósticos de esa raíz.
Prefiere `%LOCALAPPDATA%/CHC Consultores/Workbench/bots/xmovimientos` si existe;
en otro caso usa los datos del repositorio. No recorre automáticamente respaldos
ni otras copias. Uso por consola desde la raíz del repositorio:

```powershell
# Revisión sin modificar diagnósticos (limit opcional para una muestra).
.\bots\xmovimientos\.venv\Scripts\python.exe tools/compact_movement_evidence.py --root "$env:LOCALAPPDATA/CHC Consultores/Workbench/bots/xmovimientos" --limit 5
# Sustitución de todos los diagnósticos del destino, con confirmación exacta.
.\bots\xmovimientos\.venv\Scripts\python.exe tools/compact_movement_evidence.py --root "$env:LOCALAPPDATA/CHC Consultores/Workbench/bots/xmovimientos" --apply --confirm BORRAR
```

Procesa solo HTML con nombre DUA en `data/exports/**/diagnosticos` y sus JSON
de formulario. Conserva nombre/ruta/fecha para mantener las referencias, comprueba
la relectura y reemplaza atómicamente solo cuando ahorra espacio. Preserva archivos
inválidos o cambiados durante la operación. Toma los mismos bloqueos de las colas
sin abrir SQLite; un lote ocupado impide la conversión sin detener el motor.
Registra un diario durable en `data/evidence_compaction/` con hashes y tamaños,
antes y después de cada reemplazo. Puede interrumpirse y repetirse sin envolver
los resúmenes. Confirmar descarta el HTML completo; el diario no es su respaldo.
No toca SQLite, CSV, estados ni publicaciones.

Pasaron 13 pruebas de evidencia/vacíos y 21 de puentes Talón/XMovimientos y bitácora,
más smoke QML de seis vistas. Cubren tamaño, escape HTML, formato inválido,
migración antigua, reconsulta, bloqueo, cambios concurrentes, fechas/rutas,
idempotencia y resultados intactos sobre almacenamiento temporal. En ejemplos
existentes, sin modificarlos: cinco HTML/JSON pasan de 527.238 a 12.227 bytes;
el HTML mayor pasa de 14.145.681 a 1.746 bytes con la misma comprobación de vacío.
No es una medición de la conversión completa. Evidencia local en
`runtime/diagnostics/movement-evidence/`.

El usuario descartó convertir los históricos por costo/tiempo y autorizó eliminar
solo sus evidencias. Se retiraron 31.242 HTML/JSON (10.753.741.896 bytes) del
`daily-2026-10/diagnosticos` instalado en C; carpeta vacía y cero errores.
Los SHA-256 de SQLite/CSV son idénticos antes/después, con bloqueos compatibles.
No se cambió progreso ni se reconsultó TICA. Las evidencias eliminadas dejan de
estar disponibles en Abrir evidencia, sin reabrir los DUAs confirmados para
regenerarlas. Otras copias/respaldos intactos. Recibo en
`runtime/diagnostics/movement-evidence/deleted-20261023T003540.json` (UTC).
La instalación local de C ya incorpora la corrección: cuatro módulos de runtime,
con respaldo previo y actualización de metadatos/hashes. Con su Python instalado,
una respuesta sintética de 2.000.268 bytes quedó en 1.779 bytes y conservó Vacío
al reabrir SQLite temporal. Smoke del EXE correcto, sin consultas TICA. La app
instalada se abrió antes de documentar; el acceso directo habitual usa la mejora.
El instalador anterior en `runtime/releases/` no se reempaquetó y conserva su
payload previo; reinstalarlo requerirá volver a aplicar la corrección.

## Evidencia y alcance de las comprobaciones

- Dos integraciones Qt → proceso → navegador local, una por bot: envío con
  CAPTCHA y botón propios, múltiples filas, 52 filas en dos páginas, fallo HTTP
  en la segunda sin resultado parcial y ausencia de filas pendiente en Talón,
  registrada como Vacío en XMovimientos.
- Agrupación de bultos y ceros iniciales; CSV con las columnas originales; visor
  completo y limpieza que conserva las 54 filas confirmadas del ejemplo.
- Dos días por bot, cuatro regímenes por día, calendario 4/4 completado por día,
  reanudación sin nuevas descargas y sin consultar pendientes de otras tablas.
- Dos proveedores simultáneos sobre una caché: cuatro consultas totales, un
  intento por régimen y listas idénticas. Cancelar durante la espera no consulta.
- Integración existente de Tránsito y eventos QML satisfactorios. Capturas de
  ambas pantallas con cero advertencias y módulos listos.
- Dos consultas reales acotadas, una por bot, con un trabajador y una ronda:
  Talón `001-2026-078119` obtuvo el HTML de nueve tributos. La primera versión
  esperó equivocadamente SIGUIENTE del otro grid; se corrigió y se reprodujo
  ese HTML sin red, confirmando los nueve tributos idénticos al parser original
  en SQLite y CSV. No se hizo otra consulta real tras ese ajuste.
- XMovimientos `001-2026-078121` devolvió identidad correcta y tabla sin filas,
  sin mensaje de error ni paginadores. Se conservó pendiente; esta consulta no
  acredita una extracción positiva real de movimientos. Su agrupación positiva
  se comprobó con el portal local, sin presentar esos datos como resultados reales.

Evidencia local, excluida de Git: `runtime/integracion-importacion/`. No se
importaron resultados de prueba a las tablas operativas. Se abrió una ventana
nueva con ambos módulos y se mantuvo la instancia de Detalles que estaba
procesando, sin cerrar ni reiniciar esa ejecución. No hay servicio de Windows:
para el modo continuo deben permanecer abiertos la app y el equipo.

Revisión del 14/10/2026: tres consultas explícitas aisladas (`001-2026-078121`,
`001-2026-078143`, `002-2026-088749`) confirmaron tablas vacías. La migración posterior
clasificó 679 vacíos desde HTML existente y la revisión, conservando idénticos los
881 DUAs/2.028 filas confirmadas y todos los intentos. Otros dos carecían de evidencia.
Respaldos y comparación privados en `runtime/xmovimientos_revision/`. Cinco pruebas
de almacenamiento/migración/reconsulta/calendario, integración real de workers con
portal local y prueba mensual comprueban el nuevo contrato sin descargar más DUAs.
