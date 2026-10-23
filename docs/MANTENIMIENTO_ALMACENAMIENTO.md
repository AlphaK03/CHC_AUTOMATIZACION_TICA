# Mantenimiento del almacenamiento

El usuario autorizó el 22/10/2026 retirar residuos pesados que no intervienen en
la aplicación y evitar que vuelvan a acumularse en futuras entregas. La regla
persistente está en `AGENTS.md`. No añade un servicio ni un proceso de limpieza
en segundo plano a la aplicación.

## Limpieza residual autorizada y pendiente

La instalación habitual está en
`%LOCALAPPDATA%/Programs/CHC Workbench/20261022-002420-76a546` y sus datos en
`%LOCALAPPDATA%/CHC Consultores/Workbench`. El acceso de Inicio apunta a esa
instalación, fuera de las carpetas seleccionadas. No había procesos ejecutando
código desde los destinos al comprobarlos.

| Destino | Finalidad anterior | Almacenamiento aproximado |
| --- | --- | ---: |
| `C:/CHC_Build`, `C:/CHC_QA`, `C:/CHC_Install_QA` | Construcción y verificación del paquete | 2.878 MB entre las tres |
| `runtime/diagnostics/batch-loading` del repositorio | Copias de bases para investigar carga | 443 MB |
| `%LOCALAPPDATA%/CHC Consultores/Workbench.migracion-20261022-003022` | Copia incompleta anterior a la migración verificada | 219 MB |

Total almacenado medido: **3.539.491.158 bytes (3,54 GB)**. Se consultaron metadatos
de archivos y `GetCompressedFileSizeW`; se descontaron enlaces duros entre Build
y QA para no sumar varias veces el mismo contenido. Los 3,90 GB aparentes de las
tres carpetas de paquetes equivalen a 2,88 GB de contenido único.

**Ninguna de estas cinco carpetas se eliminó.** La revisión automática rechazó
primero el borrado conjunto y después el borrado de la sola carpeta
`runtime/diagnostics/batch-loading`, incluso con ruta literal y comprobación previa.
El único motivo devuelto fue `blocked by policy`; no se proporcionó más detalle.
No se repitió la misma acción mediante otro intérprete para eludir el bloqueo.

Inventario y comprobaciones locales, sin datos de producción consultados en SQL:

- `runtime/diagnostics/storage-audit/inventory.json`
- `runtime/diagnostics/storage-audit/details.json`
- `runtime/diagnostics/storage-audit/reclaimable.json`
- `runtime/diagnostics/storage-audit/physical.json`

El instalador conservado en `runtime/releases/` y el código del repositorio
permiten mantener la entrega sin estas copias de prueba. El instalador anterior
a la corrección de evidencias aún contiene su payload previo; la instalación
activa de C sí tiene la corrección aplicada. No eliminar la instalación activa.

## Cierre de futuras entregas

1. Crear las pruebas y sus copias grandes en almacenamiento temporal con limpieza
   al terminar, incluso cuando fallen. Guardar solo evidencia y métricas acotadas.
2. Revisar los artefactos generados por esa entrega y retirar los intermedios
   que ya no se usen. Verificar límites de rutas, procesos y ausencia de datos únicos.
3. Conservar el entregable final vigente y los respaldos útiles; no tratar bases,
   CSV, progreso, credenciales o entornos de desarrollo como residuos.
4. Informar únicamente lo eliminado y comprobado. Si una herramienta bloquea
   una operación, registrar los destinos pendientes y explicar el motivo recibido.

Los diagnósticos operativos de otros bots y los respaldos SQLite se revisan por
separado: no están incluidos en esta autorización de residuos de pruebas.
