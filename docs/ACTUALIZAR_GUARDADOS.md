# Actualizar manifiestos guardados manualmente

Implementado el 24/10/2026 en desarrollo, por petición del usuario tras comprobar
filas nuevas en manifiestos ya Guardado. El usuario eligió control manual para
medirlo y pidió un botón visible púrpura o celeste. Se añadió **Actualizar guardados**,
púrpura y fuera de menús, en Conocimientos y DUAs por manifiesto.

No hay tarea al cambiar de fecha ni al abrir la app. **Iniciar consulta** mantiene
la acumulación normal de nuevos/pendientes. Esta acción permite revisar guardados
varias veces el mismo día, porque TICA puede modificarlos a cualquier hora.

## Uso

1. Entrar en Manifiestos → Conocimientos o DUAs y seleccionar la ejecución guardada.
2. Mantener el año/mes de esa ejecución y marcar las modalidades que se revisarán.
   Para repetir la medición corta, elegir octubre de 2026 y solo Marítimo.
3. Pulsar **Actualizar guardados**, debajo de los botones de consulta.
4. Se muestran revisados/total, etapa y tiempo transcurrido; al terminar se informa
   cantidad con cambios, sin cambios, sin actualizar y duración total.
5. **Detener** cancela el refresco. Las confirmaciones ya aplicadas se conservan.
6. Si se necesita CSV, generarlo después desde Más, de forma manual.

El botón se habilita cuando la ejecución tiene guardados y no está ocupada ni en
revisión visible de TICA. Puede cambiarse de procedimiento sin detener otro.
El worker valida la identidad de la ejecución, período y bases existentes; una
respuesta tardía o selección obsoleta no inicia otro lote.

Revisa únicamente las bases de la ejecución elegida y las modalidades marcadas.
Dentro de cada una, la cohorte son todos los Guardado confirmados existentes al
comenzar, incluidos los vacíos válidos. No incluye pendientes/excluidos ni añade
el detalle de manifiestos nuevos del listado. Se obtiene el listado del mes para
reencontrar la cohorte completa, aunque la última consulta normal fue un subrango.
Conserva la selección Courier de cada SQLite. Los otros tres procedimientos no
incorporan esta acción.

## Conservación y confirmación

`manifest_manual_refresh.py` coordina el trabajo dentro del worker del procedimiento,
sin importar motores en Qt. Adquiere todos los bloqueos de las fuentes antes de
congelar la referencia. `manifest_refresh_audit.py` aporta la cohorte de solo lectura,
firmas con multiplicidad y extracción completa desde la primera página, con hasta
cuatro consultas simultáneas. DUAs mantiene cliente independiente y espera ilimitada.
La consulta no reutiliza checkpoints antiguos ni cambia las fuentes durante esa fase.

Antes de aplicar, se crea una copia SQLite consistente por fuente, fuera de jobs:
`bots/manifiestos/data/backups/refresh_saved/<operación>/<procedimiento>/`.
Se exige `quick_check=ok`. La identidad de fuente permanece `(base, manifiesto)`.

Cada reemplazo exige que el trabajo siga Guardado, exista su confirmación y las
filas originales mantengan la firma congelada. Se vuelven a validar identidad,
columnas y cantidades frescas. El DELETE/INSERT, estadísticas, contador de intento,
fecha y registro del intento se confirman en una sola transacción. Un error de
inserción revierte todas las filas anteriores. Si la extracción completa confirma
menos filas, se aplica ese resultado completo y se conserva el anterior en respaldo.

Se reemplazan tanto aumentos como cambios con igual cantidad; no se anexan filas
indiscriminadamente. Se conservan texto, ceros, duplicados legítimos y estados de
los trabajos ajenos a la cohorte. Las respuestas inválidas, ausencia de enlace o
fallos de referencia conservan las filas y el estado Guardado anteriores. No se
convierten en cero ni en exclusiones nuevas. Los detalles quedan en Actividad y
en el registro de aplicaciones del experimento.

Cancelar durante la extracción deja las fuentes intactas. Si ocurre durante la
aplicación, quedan únicamente reemplazos completos ya confirmados; el resto sigue
anterior. La ejecución auxiliar queda interrumpida y no se ofrece como terminada
al proveedor BLs. Los intentos/fechas actualizados invalidan cierres manuales que
dependían de la revisión anterior. No se modifica la cobertura histórica ni se
declara cobertura nueva por esta acción.

Cada operación conserva referencia, extracción comprimida, observaciones y estado
de aplicación bajo `data/refresh_saved/<procedimiento>/<operación>/`; `receipt.json`
resume el resultado cuando termina. La duración incluye preparación, consulta,
respaldo y aplicación. El estado resumido se conserva en el índice de la ejecución.
CSV y SharePoint requieren sus acciones explícitas; no hay publicación automática.
BLs no se ejecuta ni recibe una base nueva automáticamente.

## Verificación y entrega

Se completaron 21 pruebas distintas: 19 de auditoría, actualización transaccional
y acumulación; una del botón QML real → worker → portal local en ambos procedimientos;
y la auditoría global de geometría en 1280×774, 1000×680 y 1000×600. Incluyen filas
nuevas/campos modificados, repetición sin duplicar, conservación de pendientes,
CSV intactos, respaldo válido, fallo de extracción, selección obsoleta, cancelación
y rollback tras un fallo posterior al DELETE. Un recibo auxiliar bloqueado tampoco
aborta actualizaciones confirmadas en SQLite. Cero avisos QML.

Pruebas con SQLite sintéticos temporales y portales locales, sin consultar TICA ni
actualizar las bases del usuario. Los SHA-256 de las dos fuentes marítimas reales
siguen iguales a los recibos del experimento anterior. Capturas y auditoría pequeñas
en `runtime/diagnostics/manual-manifest-refresh/layout/`; temporales de esta entrega
limpiados por sus context managers.

No había instancia interactiva al comprobar procesos; se abrió una sola vez la app
de desarrollo local antes de documentar, sin iniciar consultas. La distribución
empaquetada no se actualizó. El usuario realizará su propia medición desde el botón.
