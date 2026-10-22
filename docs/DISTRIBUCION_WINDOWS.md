# Distribución Windows x64

Entrega preparada el 22 de octubre de 2026 para Windows 10/11 x64 actualizado.
El instalador contiene Python 3.12, PySide6/Qt, dependencias de los seis bots,
Chromium y ChromeDriver compatible. El equipo destino no necesita los entornos,
Python, Edge ni las rutas del equipo de desarrollo. Internet sigue siendo
necesario para TICA y SharePoint. No equivale a compatibilidad con cualquier
sistema operativo de 64 bits. Falta la aceptación en otro equipo físico limpio.

## Instalación y datos

Abrir `Instalar CHC Workbench x64.exe` y pulsar **Instalar y abrir**. Instala por
usuario en `%LOCALAPPDATA%\Programs\CHC Workbench\<versión de instalación>` y crea
accesos en escritorio/Inicio. Las actualizaciones usan una carpeta nueva y no
reemplazan ejecutables abiertos. Las versiones anteriores quedan conservadas.
No tiene firma digital. El EXE de la app requiere su carpeta de soporte completa.

Los datos nuevos se guardan en `%LOCALAPPDATA%\CHC Consultores\Workbench`,
separados del programa. No se empaquetan bases, credenciales, configuraciones de
la máquina ni resultados actuales. La instalación comienza vacía. La migración
de datos existentes queda como operación separada, con cierre de bots, respaldo
y revisión de rutas persistidas; copiar solo el ejecutable no migra los datos.
`CHC_WORKBENCH_HOME` permite un almacenamiento independiente para comprobaciones.
En desarrollo, sin esa variable, se conservan las rutas actuales del repositorio.

SharePoint conserva el registro público CHC y los permisos ya establecidos;
cada usuario inicia sesión y elige su destino. Caché DPAPI y cola permanecen en
su almacenamiento propio. No se incluyen sesiones del equipo de compilación.

## Construcción y tamaño

`distribution/windows/build.py --output <carpeta nueva>` arma la distribución;
ejecutarlo con `workbench/.venv/Scripts/python.exe`. Requiere los entornos de
desarrollo preparados y la caché del Chromium descrito en `browser.lock.json`.
El driver se obtiene de su URL oficial y se verifica con SHA-256. El compilador
C# del .NET Framework de Windows genera lanzador e instalador.

Cada bot conserva un intérprete privado aislado y precedencia para sus versiones
particulares de dependencias. Se comparten paquetes idénticos y las versiones
mayoritarias; BLs conserva sus diferencias de pandas/BeautifulSoup. El paquete
normaliza Playwright a 1.63 y comparte un solo Chromium entre Playwright y
Selenium. El adaptador Selenium modifica únicamente la creación del navegador.
No se alteran parsers, columnas, identificadores, checkpoints ni contratos CSV.

Se excluyen pruebas, pip, cachés, artefactos de desarrollo y datos operativos.
Se conservan bibliotecas Qt transitivas, recursos QML/qmldir, catálogos CAPTCHA
y licencias. La GUI clásica queda como referencia de desarrollo; el producto
distribuido es Workbench. No necesita los ejecutables clásicos originales.

`pack.py <carpeta>` audita la ausencia de datos operativos, crea `SHA256SUMS.json`,
comprime el soporte e incrusta el ZIP en el instalador. `release.json` registra
bytes instalados, peso del EXE y su SHA-256. El script no publica ni sube archivos.

Paquete 2026.10.22: instalador 412.732.928 bytes (393,6 MiB), instalado
1.024.600.050 bytes (977,1 MiB), 8.343 archivos. SHA-256 del instalador:
`06c1482b932c8567a38b115a6ac0adc869943b2073ad46d679b15d1d76341ec1`.

## Verificación

`verify.py <carpeta> --report <json>` ejecuta todos los intérpretes con variables
Python y navegador deliberadamente inválidas y PATH limitado a Windows. Comprueba
imports Qt/OAuth, inicio/cierre de motores y procedimientos, navegadores locales,
Selenium y navegación QML desde el EXE. Usa almacenamiento temporal, sin TICA.
El instalador admite `--extract-only <carpeta nueva>` para comprobar su payload.

Verificación final completada desde el EXE extraído en
`C:\CHC_Install_QA\Instalación verificada`: 8.342 hashes correctos (más el propio
manifiesto), siete intérpretes aislados, todos los motores/procedimientos,
seis lanzamientos Playwright, Selenium y smoke de navegación QML correctos.
Repetir la extracción al mismo destino devuelve error y conserva la instalación.
Informe: `runtime/diagnostics/distribution/final-installer.json`. El EXE copiado
a `runtime/releases/` conserva el SHA-256 indicado arriba.

La carpeta trasladada a una ruta con espacios y acento pasó 10 pruebas de puentes
Qt (incluidas las cinco de Detalles con su muestra aislada) y 25 de BLs sobre
páginas, búsqueda y actualización incremental. Los 105 archivos de parsers y
motores originales copiados mantienen sus hashes. Se abrió la app empaquetada
en Vista general antes de documentar, conservando las otras instancias.
Los informes finales se guardan en `runtime/diagnostics/distribution/`.

Se encontró ausente el formulario de las pruebas Selenium anteriores; se añade
un fixture exclusivamente local y un fallo explícito si vuelve a faltar. Cubre
fechas separadas por más de doce meses y cambios de formulario antes del envío.
Las cuatro pruebas Selenium pasaron con Chromium incluido. Las cuatro pruebas
de puentes DUA que habían agotado el plazo durante la copia intensiva del HDD
pasaron al repetirse sin esa carga (114 s en total); no se cambió el plazo.
Estas pruebas no acreditan una consulta real de TICA ni una instalación en otro PC.

El inventario SQLite `sqlite-size.json` mide archivos por tamaño y cabecera, sin
abrir conexiones ni cambiar bases. Distingue datos operativos, respaldos incluidos,
auxiliares WAL/SHM y bases de diagnóstico. No se empaqueta ninguno de esos datos.

Medición del 22/10 a las 00:09 Costa Rica: 1.729.619.056 bytes operativos
(1,611 GiB), incluidos 538.039.408 bytes de respaldos (513,1 MiB). Sin respaldos,
1,110 GiB. Los SQLite de diagnóstico añaden 461.213.696 bytes; la instalación
nueva vacía añade 196.608 bytes. Total de las ubicaciones medidas:
2.191.029.360 bytes (2,041 GiB). No incluye repositorios originales externos ni
las copias temporales de QA en C. No se compactaron ni alteraron las bases.
