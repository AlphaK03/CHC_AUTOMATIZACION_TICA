# Desarrollo local fuera de OneDrive

Ubicación vigente: `C:/Proyectos/CHC_AUTOMATIZACION_TICA`.
Abrir con `Abrir_Workbench.bat` o con el acceso de Inicio
**CHC Workbench - Desarrollo local**. El acceso habitual de la instalación
empaquetada sigue siendo independiente y usa otros datos.

El 23/10/2026 se publicaron los 36 commits pendientes de la rama
`feature/sharepoint-oauth2` y se creó un clon limpio del remoto, incluyendo la
regla de confirmar y subir cada entrega (`ea1cacf`). Los datos privados,
credenciales y entornos permanecen fuera de Git.

Se trasladaron 6.839 archivos operativos (2.481.075.770 bytes), comprobados
por SHA-256 contra el original. Las 54 bases SQLite comprobadas pasaron
`PRAGMA quick_check`. Se conservaron calendarios, colas, estados, resultados,
configuraciones, metadatos, cachés de bases y respaldos. Los SQLite de los bots
quedaron idénticos byte a byte tras ajustar las rutas de los metadatos.
Los datos de desarrollo se conservaron como estaban; no se sustituyeron por
los datos distintos de la instalación empaquetada.

Los siete entornos Python se reconstruyeron con las mismas versiones de
paquetes. Se comprobó que los dos Chromium requeridos están en almacenamiento
local y se regeneró Edge WebDriver 155.0.4283.62. Se ajustaron las rutas
operativas antiguas hacia C, preservando firmas e identidad de los lotes.

La revisión final encontró 62.576 archivos (4.476.807.807 bytes) en el proyecto
local, sin placeholders de nube, archivos offline, enlaces simbólicos ni
junctions. El proyecto activo no depende de archivos de OneDrive.

Comprobación de carga desde el nuevo código: seis módulos listos en 10,516 s,
sin errores ni avisos QML, usando copias temporales de los datos de desarrollo.
BLs octubre mostró 27.884 guardados y 47.839 filas; XMovimientos mostró
23.578 guardados y 14.051 vacíos verificados. No se consultó TICA, inició
un calendario, exportó CSV ni subió resultados durante la comprobación.
La aplicación de desarrollo local se abrió antes de documentar; el usuario
la cerró después para retirar la carpeta anterior.

Evidencia, respaldo de metadatos y rescate local en
`C:/Proyectos/CHC_migracion_20261023`. `datos-hashes.json`,
`datos-verificados.json`, `rutas-ajustadas.json`, `entornos-reconstruidos.json`
y `prueba-carga/full.json` registran la verificación. `rescate/` conserva el
material recuperado de la carpeta anterior, incluidos CSV y el instalador,
que no se incorporaron al clon limpio como artefactos de trabajo.

El borrado de entornos/cachés y, posteriormente, de la carpeta original
fue rechazado antes de ejecutarse con `blocked by policy`, sin más motivo.
La alternativa de mover el original a un respaldo local encontró un bloqueo
de archivo en uso. Microsoft Sysinternals Handle identificó la carpeta abierta
en los dos procesos OneDrive (PID 3408 y 2036), sin procesos de bots en esa ruta.
Por autorización expresa del usuario, ambos procesos OneDrive se cerraron para
liberar la carpeta durante el borrado manual. OneDrive deberá reiniciarse para
sincronizar la eliminación con la nube.
El 23/10/2026 el usuario confirmó que eliminó el proyecto de OneDrive y que
el trabajo continúa en C local. Se registra su confirmación como cierre de
la retirada manual del proyecto; no se inspeccionaron la papelera web ni el
estado de sincronización de OneDrive. La ubicación vigente sigue siendo
`C:/Proyectos/CHC_AUTOMATIZACION_TICA`.
