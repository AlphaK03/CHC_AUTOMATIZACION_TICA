# Comparación experimental de manifiestos ya descargados

El usuario solicitó el 23/10/2026 comprobar si manifiestos ya Guardado incorporan
nuevas filas. Autorizó revisar todos los guardados de octubre, únicamente Marítimo,
en Conocimientos y DUAs por manifiesto. No incluye los otros bots DUA, nuevos
manifiestos, pendientes ni excluidos.

El acumulado normal obtiene otra vez el listado pero omite el detalle Guardado.
Ese estado acredita una extracción terminada en ese momento, no la inmutabilidad
posterior del manifiesto. Se implementó una herramienta separada para medir el
problema sin sustituir los resultados vigentes.

## Funcionamiento y límites

`chc_runtime/manifest_refresh_audit.py` consulta el índice de lotes existente sin
crear servicios ni recuperar reservas. Abre cada fuente SQLite con `mode=ro`,
`query_only` y una transacción de lectura consistente para congelar exclusivamente
trabajos Guardado que también tengan confirmación en `manifests`. Comprueba que
filas, contadores y metadatos coincidan. Conserva la identidad `(base, manifiesto)`;
no fusiona lotes históricos.

La referencia experimental guarda la lista exacta, cantidades y firmas SHA-256
de cada versión de fila, comprimidas y con su multiplicidad. Incluye vacíos válidos.
La referencia es de creación exclusiva y no se reemplaza al reanudar. La captura
es consistente por base; no pretende una transacción simultánea entre bases.

La consulta real utiliza un navegador y proceso propios, obtiene enlaces frescos
del listado confirmado y solo pide detalles de las identidades congeladas.
Reutiliza los extractores originales y su validación de identidad, esquema,
contadores, secuencia, offsets y EOF. Lee desde la primera página, sin checkpoints
anteriores. DUAs conserva cliente HTTP independiente y espera ilimitada del motor.
Por defecto permite cuatro consultas simultáneas; un procedimiento sigue al otro.
No se solicita el detalle de los manifiestos nuevos que aparezcan en el listado.

Cada extracción completa se confirma transaccionalmente en el experimento y se
conserva comprimida. Las fuentes, sus estados/intentos y los CSV públicos no se
modifican. No se publica cobertura ni se preparan bases BLs desde el experimento.
No hay exportación CSV ni subida a SharePoint. La app abierta permanece en uso.

Estados de comparación:

| Estado | Significado |
| --- | --- |
| `aumento` | Mayor cantidad de filas confirmadas del mismo manifiesto. |
| `disminucion` | Menor cantidad confirmada. No borra filas del lote original. |
| `cambio` | Igual cantidad, pero existen versiones de filas diferentes. |
| `sin_cambios` | Mismas filas, independientemente del orden y preservando duplicados. |
| `sin_enlace` | La identidad guardada no aparece con enlace en el listado fresco. No equivale a cero. |
| `error` | Falló la consulta o la validación. Sin cantidad fresca confirmada. |
| `pendiente` | Todavía no se comparó, o se interrumpió antes de confirmar. |

`added` y `removed` cuentan versiones completas de filas. Un campo modificado
puede producir una versión añadida y otra retirada sin representar un BL nuevo.
`delta` es la diferencia neta de cantidades; se separa de los cambios de contenido.
La suma fresca y su referencia se comparan solo sobre manifiestos confirmados
en ambos lados; errores y ausencias no se suman como ceros.

## Uso desde el desarrollo local

Ejecutar desde `C:/Proyectos/CHC_AUTOMATIZACION_TICA`, con el Python del módulo:

```powershell
bots/manifiestos/.venv/Scripts/python.exe -m chc_runtime.manifest_refresh_audit freeze --year 2026 --month 10 --mode maritimo --output runtime/experiments/manifest-refresh/20261023-octubre-maritimo/reference.sqlite3
bots/manifiestos/.venv/Scripts/python.exe -u -m chc_runtime.manifest_refresh_audit run runtime/experiments/manifest-refresh/20261023-octubre-maritimo/reference.sqlite3 --workers 4
bots/manifiestos/.venv/Scripts/python.exe -m chc_runtime.manifest_refresh_audit report runtime/experiments/manifest-refresh/20261023-octubre-maritimo/reference.sqlite3
```

`freeze` solo lee datos locales. `run` sí consulta TICA y requiere un alcance
autorizado. Repetir `run` continúa lo que falta y no repite éxitos. `--retry-errors`
reconsidera también errores/ausencias, manteniendo la referencia. Para una nueva
medición completa se crea otra referencia en otra carpeta. `--flow conocimientos`
o `--flow duas` limita el procedimiento al congelar; `--limit N` limita por base.

`differences <reference.sqlite3>` muestra versiones frescas que no estaban
idénticas en la referencia. El experimento mantiene un bloqueo de escritor propio.
La interrupción deja las comparaciones confirmadas y no acredita páginas parciales.
Se conserva toda la información privada bajo `runtime/`, fuera de Git.

No hay todavía botón QML, adopción de resultados ni refresco periódico automático.
La decisión de integrar resultados frescos deberá preservar respaldos, cobertura,
identidades y consumidores BLs; este experimento no los actualiza.

## Verificación

Seis pruebas con bases sintéticas temporales y portal HTTP local cubren selección
Guardado, protección de referencia, firmas de fuentes intactas, páginas completas,
vacíos, duplicados, cambios con igual cantidad, identidad/esquema inválidos,
ausencias/errores sin falsos ceros, reintento, reanudación sin repetir y cancelación
sin confirmar parciales. Nunca se usan los lotes del usuario como pruebas.

La revisión real autorizada tiene su referencia y recibos en
`runtime/experiments/manifest-refresh/20261023-octubre-maritimo/`.
Resultado real del 23–24/10/2026: de 338 Conocimientos se compararon 336
(20.750 → 26.006 filas, +5.256); de 281 DUAs se compararon 279
(64.433 → 96.514, +32.081). Aumentaron 103 y 134 manifiestos respectivamente;
otros 19 Conocimientos cambiaron sin variar la cantidad. Las mismas dos
identidades de cada procedimiento quedaron sin enlace tras una segunda
comprobación, sin contarlas como cero. No hubo errores ni disminuciones.
Las fuentes conservaron SHA-256 idénticos. Última confirmación de la primera
pasada a los 361 segundos desde el inicio, con cuatro consultas simultáneas.
No se extrapola ese tiempo a otros períodos ni a Aéreo.

`INFORME.md`, `report.json`, `differences.json` y `source-checks.json` cercanos
a la referencia contienen el informe, detalles privados y recibos. La referencia
completa de Conocimientos tenía 20.788 filas; las 38 de una identidad ausente
quedaron fuera de ambos lados del cálculo comparable, conservadas en el original.
