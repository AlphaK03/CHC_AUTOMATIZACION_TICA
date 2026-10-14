# BLs conectado a Conocimientos

Implementado el 13/10/2026. BLs utiliza las descargas terminadas de Conocimientos
para preparar su propia base y ejecutar su motor actual. No es necesario generar
un Excel ni seleccionar un archivo intermedio para este recorrido.

## Uso

1. Descargar **Conocimientos asociados** desde Manifiestos y terminar sus pendientes.
   También puede importarse su progreso SQLite original desde Más, sin modificarlo.
2. Entrar en **BLs**, con origen **Desde Conocimientos**.
3. Pulsar **Elegir meses…** y marcar los períodos y modalidades disponibles.
   Pueden seleccionarse meses distintos y Marítimo/Aéreo juntos o por separado.
4. Pulsar **Iniciar consulta**. Se prepara la base Courier=N y luego empieza BLs.

La lista se actualiza al terminar o importar una descarga de Conocimientos y al
abrir el selector. Actualizar lee SQLite; no realiza consultas a TICA. Si todavía
no hay descargas terminadas, se informa y se ofrece ir a Conocimientos.
No se inventan opciones para meses o modalidades sin datos disponibles.

**Archivo externo** conserva la entrada manual Excel/SQLite, la selección de hoja
y los lotes anteriores. La elección manual del generador de bases de Manifiestos
también permanece disponible para sus usos específicos.

## Qué significa disponible

La comprobación lee una instantánea SQLite de Conocimientos; no se basa en CSV,
nombres de archivo, contadores de la interfaz ni el estado resumido del historial.
Se exige selección confirmada, todos sus trabajos Guardado, resultados confirmados,
ninguna página parcial y una ejecución finalizada correctamente.

Se aceptan únicamente Marítimo y Aéreo, descargados con todos los Courier o Courier N.
Se excluyen selecciones limitadas por IDs o cantidad de manifiestos, Courier S,
otros procedimientos, períodos futuros, trabajos pendientes/activos y fuentes sin
control suficiente para acreditar su finalización.

Un intervalo terminado dentro de un mes puede ofrecerse, pero muestra sus días
disponibles. **Mes completo** exige cobertura de todos sus días y que el mes haya
terminado. Se agrupan intervalos finalizados compatibles; no se presupone cobertura
de los días que faltan ni del resto de un mes en curso.

Solo se utilizan los archivos propios del Workbench: descargas/importaciones en
`bots/manifiestos/data/jobs/conocimientos/` y SQLite de la copia clásica en
`bots/manifiestos/datos_app/SQLite/conocimientos/`. No se depende de las carpetas ni
de los procesos de la aplicación original. Para traer resultados antiguos debe
importarse explícitamente su progreso SQLite en Manifiestos.

## Preparación y descarga

Antes de crear la base se verifica nuevamente la disponibilidad. Se obtienen
copias SQLite consistentes mediante backup desde conexiones de solo lectura;
la validación y la copia corresponden a la misma instantánea. Los originales no
se modifican y los temporales se eliminan dentro de su carpeta propia verificada.

El generador original de Manifiestos conserva sus reglas: Courier=N explícito,
texto y ceros iniciales, orden, cinco columnas BLS, eliminación de duplicados
equivalentes y detección de BL contradictorios. La modalidad y fecha viajan en
cada IDManifiesto; el motor BLs mantiene sus fechas y validaciones por entrada.
Si aparecen inválidos o conflictos, este recorrido automático no inicia consultas
y conserva su auditoría para revisión.

Una descarga completa sin conocimientos, o sin ningún BL Courier N, se informa
como selección sin BLs. No se confunde con un fallo ni se inicia el navegador de
BLs. La auditoría registra `completed_empty`; no se simulan consultas exitosas.

Se conserva una base privada verificada por hash para cada versión de los datos.
La misma selección sin cambios reutiliza la preparación y la identidad original
del lote; BLs retoma pendientes y no repite guardados. Se conserva también un lote
manual previo si su entrada normalizada, destino e identidad son equivalentes.
Si los datos cambian, el motor mantiene su regla original de crear otro lote.
Con nombre automático se usan carpetas legibles por meses/modalidades, con sufijo
numérico si hace falta conservar otra versión. Un nombre escrito por el usuario
mantiene las protecciones existentes contra sobrescribir otro lote.

**Detener** sirve tanto al preparar la base como durante las consultas. Un resultado
de preparación que llegue después de detener o cerrar no puede iniciar BLs.
Las descargas de Conocimientos no arrancan automáticamente el bot: actualizan lo
disponible, y el usuario decide su selección e inicio.

## Arquitectura y mantenimiento

- `chc_runtime/knowledge_source.py`: disponibilidad, instantáneas, caché y generación.
- `batch_worker.py --flow bls_source`: proveedor aislado en el entorno de Manifiestos.
- `manifest_service.py`: comandos del proveedor y adaptación de lotes BLs.
- `workbench/batch_bridge.py`: preparación → descarga, cancelación y errores entre procesos.
- `qml/BlsKnowledgeDialog.qml`: meses y modalidades reales; `ManifiestosPage.qml`: origen e inicio.
- `workbench/app.py`: actualización al finalizar/importar Conocimientos.

El proceso BLs conserva `bots/bls/src/core/engine.py`, sus parsers, reservas por
token, reintentos y exportaciones. No importa fuentes de Manifiestos en ese
proceso. El proveedor usa el entorno de Manifiestos y su sesión independiente
`data/workbench/bls_source/`, separada del generador manual `bases`.

Bases verificadas y auditorías: `bots/manifiestos/data/bls_source/`. El JSON junto
a cada base registra selección, fuentes, cobertura, hash y auditoría. Los CSV de
BLs siguen publicados únicamente en `bots/bls/resultados/<nombre de tabla>/`.
No hay pasos de preparación técnicos en esas carpetas públicas.

No se modificaron las fuentes originales de BLs ni de Manifiestos. No requiere
paquetes adicionales a sus entornos ya instalados. Esta incorporación no añade
un calendario diario continuo para BLs.

## Comprobaciones realizadas

Pruebas locales y temporales, sin consultas reales nuevas a TICA:

- Disponibilidad real desde SQLite, separando Marítimo/Aéreo y descartando
  pendientes, ejecuciones activas, selecciones limitadas, Courier S y Terrestre.
- Intervalos parciales identificados; selección conjunta y cambio de mes/modo.
- Base generada → lector/motor BLs original → SQLite/CSV, conservando un BL de
  23 dígitos con ceros y la identidad de cada modalidad.
- Reanudación de la misma entrada con un intento por BL guardado.
- SHA-256 de las fuentes intacto tras preparar y procesar la base.
- Período no disponible rechazado antes de iniciar BLs; selección vacía válida sin consultas.
- Selección desde botones y casillas QML hasta el procesamiento, sin advertencias.
- Compatibilidad del recorrido manual anterior y smoke de las seis vistas.

Pruebas enfocadas: `workbench/tests/test_bls_knowledge.py` y
`test_bls_knowledge_qml.py`. No se ejecutaron lotes de producción como prueba.
