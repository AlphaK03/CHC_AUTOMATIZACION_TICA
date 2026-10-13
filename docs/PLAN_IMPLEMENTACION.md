# Plan de implementación — CHC Workbench

Fecha de revisión: 12 de octubre de 2026.

Estado actual: fases 0 y 1A completadas. Detalles es el primer piloto operativo
de las fases 1B/2: controles nativos QML, worker aislado, SQLite y entorno propio.
Se comprobaron 50 pruebas del bot, cinco de integración y dos consultas reales
comparadas contra sus 38 campos originales. Los otros cuatro motores permanecen
en demo. Consultar `INTEGRACION_DETALLES.md` para alcance y evidencia del piloto.

## Objetivo y alcance inicial

Centralizar el mantenimiento de cinco bots en un repositorio, ofrecer acceso por
módulo y convertir progresivamente sus motores en componentes independientes de
las aplicaciones que hoy generan sus entradas. La primera entrega comprende el
plan, las copias de las versiones actuales y la evidencia de integridad.

Por indicación del usuario se toma `v2/` cuando existe: Tránsito, Talón y
XMovimientos. BLs y Detalles se toman de su raíz actual. No se recuperan motores
anteriores. `DUAS_SCRAPPING` se inventaría para integrarlo más adelante; no se
copia ni se modifica en esta fase.

## Fase 0 — Base de trabajo y trazabilidad

- Identificar puntos de entrada activos y dependencias por lectura del código.
- Copiar fuentes, pruebas, documentación y recursos necesarios a `bots/<id>/`.
- Conservar los archivos copiados byte a byte; registrar origen, rama, commit,
  cambios locales, archivos omitidos y SHA256. Los commits no representan por sí
  solos esta copia porque todos los orígenes tienen cambios locales.
- Dejar datos de producción y ajustes personales en su ubicación original.
- Registrar cinco módulos con ID estable y sus entradas actuales.
- Verificar integridad y sintaxis sin ejecutar consultas al portal.

Criterio de cierre: cinco módulos completos respecto al plan de copia, ninguna
modificación en los originales y verificación local satisfactoria. Esto no
certifica aún instalación, comportamiento del portal ni interfaz unificada.

## Fase 1 — Workbench como punto de acceso

### Fase 1A — Panel de prueba (completada)

- Tecnologías elegidas: Python + PySide6 + Qt Quick/QML.
- Navegación lateral expandible, vista general y acceso a cada módulo; temas y búsqueda.
- Backend de demostración en memoria para probar estados y navegación.
- En esta etapa inicial no se conectaron ni ejecutaron bots. El usuario amplió
  después el alcance para integrar Detalles y probar datos base originales.
- Documentar el objetivo final y las decisiones para otras sesiones.

Cierre: panel navegable, estados sintéticos independientes, QML verificado y
fuentes copiadas intactas. Esto no constituye integración real.

### Fase 1B — Acceso a motores (Detalles completado; otros pendientes)

- Añadir instalación, apertura, diagnóstico y supervisión de módulos reales al
  panel. Detalles ya dispone de estas funciones y de control nativo de sus datos.
- Lanzar inicialmente cada interfaz existente en un proceso separado y con su
  entorno propio. Evitar colisiones entre `core`, `utils`, `flows` y `ui`.
- Resolver todas las rutas desde el nuevo repositorio, nunca desde los originales.
- Preparar una instalación reproducible por módulo; validar dependencias y
  Chromium, sin depender de un entorno virtual de otra aplicación.
- Identificar instancias abiertas y definir detención/cierre ordenado. No prometer
  control del progreso desde el Workbench antes de tener eventos del motor.

Criterio de cierre: abrir los cinco módulos desde un único acceso, agregar otro
mediante su registro y no necesitar los repositorios originales para arrancar.
La primera interfaz puede abrir ventanas independientes como transición.

## Fase 2 — Motores y ejecución modular

- Extraer contratos de entrada, validación, ejecución, cancelación y eventos.
- Migrar un módulo a la vez; comenzar por Detalles como referencia de colas y
  BLs como referencia de sesiones y validación. No sustituir de golpe ambos motores.
- Llevar Tránsito, Talón y XMovimientos a resultados/estados transaccionales;
  su progreso por índice no tiene las garantías actuales de BLs/Detalles.
- Separar presentación y motor para que los módulos puedan usar la misma interfaz.
- Centralizar servicios solo después de demostrar compatibilidad: catálogo,
  rutas, logs, esquemas de entrada, configuración y preparación de navegador.
- Mantener perfiles y cookies por trabajador; añadir un límite global de
  concurrencia para evitar que la suma de bots exceda la capacidad del portal.
- Unificar estados: pendiente, en ejecución, confirmado con datos, vacío validado,
  fallido reintentable y cancelado. Un fallo nunca equivale a vacío confirmado.

Criterio de cierre por módulo: mismos campos y ceros iniciales, recuperación tras
interrupción, no duplicación, exportación bloqueada recuperable, errores visibles
y cancelación comprobada. Recién entonces integrar sus controles en el Workbench.

## Fase 3 — Bases propias e integración de generadores

- Integrar `D:/PortafolioDesarrollador/DUAS_SCRAPPING` como proveedor de bases DUA.
  Conservar clasificación, cobertura de períodos y entregas verificadas actuales.
- Aplicar el contrato confirmado en `AUTOMATIZACION_DIARIA.md`: Total para
  Detalles, Tránsito para DUAs Tránsito e Importación para Talón/XMovimientos.
  Obtener bases desde cada módulo, sin elegir Excel, con modos mensual y diario.
- Incorporar coordinador persistente por fecha: descargar ayer, procesar,
  esperar hasta 00:01 Costa Rica o recuperar días atrasados, sin ciclos simultáneos
  del mismo bot. Acumular y deduplicar en la tabla/CSV del mes de los datos.
- Inventariar el generador de Conocimientos/Manifiestos que alimenta BLs; todavía
  no está incluido en el alcance ni se conoce aquí su ruta. `DUAS_SCRAPPING` no
  sustituye esa fuente: genera DUAs, no las cinco columnas de BLS.
- Introducir un catálogo local de datasets con identidad, período, régimen,
  esquema, procedencia, versión y evidencia de cobertura.
- Alimentar motores desde consultas a datasets/SQLite, sin pasos manuales de
  abrir otra aplicación, unir Excel ni ejecutar scripts separadores.
- Mantener importación/exportación Excel y CSV como compatibilidad de frontera.
- Evaluar los scripts auxiliares de pendientes, separación y corrección a partir
  de resultados confirmados, sin reconstruir éxitos desde índices o archivos viejos.

Criterio de cierre: generar y consumir una base desde el Workbench, demostrar
equivalencia de selección y clasificación y reanudar sin aplicaciones auxiliares.

## Fase 4 — Distribución y mantenimiento

- Adaptar specs y recursos a rutas relativas; empaquetar desde este repositorio.
- Separar instalación de código y almacenamiento operativo con respaldos.
- Validar en un equipo sin los repositorios ni entornos actuales: apertura,
  preparación del navegador, entrada, recuperación y exportaciones compatibles.
- Documentar instalación, actualización, incorporación de módulos y restauración.
- Automatizar verificaciones offline y publicar versiones con evidencia por módulo.

Criterio de cierre: instalación trasladable y mantenimiento centralizado.
La independencia buscada elimina aplicaciones auxiliares; el acceso a TICA y un
motor de navegador siguen siendo requisitos externos que deben prepararse.

## Riesgos concretos y tratamiento

| Hallazgo | Tratamiento |
| --- | --- |
| Cambios locales en los cinco bots | Copiar disco actual, registrar hashes y estado Git |
| Imports globales repetidos | Procesos separados; namespaces propios en la refactorización |
| Specs de v2 apuntan al repositorio original | Conservar referencia; adaptar antes de empaquetar |
| Requisitos antiguos omiten Playwright/requests o no existen | Archivo runtime inicial por imports; validar instalación en fase 1 |
| Tránsito/Talón/XMovimientos reanudan por índices | Migración transaccional antes de ejecución integrada |
| Algunos logs de Tk se actualizan desde workers | Revisar cola de eventos al desacoplar las interfaces |
| Documentación antigua describe Selenium como motor activo | Dar prioridad al import de la GUI: los cinco usan Playwright |
| Generadores de entrada fuera del repositorio | Integración explícita por contrato en fase 3 |
| Bases y salidas grandes o activas | No moverlas durante la copia; migración operativa con respaldos |

## Orden de trabajo siguiente

1. Validar y revisar el panel QML de prueba, sin tocar los bots.
2. Cuando se amplíe el alcance, validar instalaciones y acceso a los cinco motores
   desde el catálogo, con procesos separados.
3. Definir el contrato de ejecución y adaptar un módulo piloto.
4. Adaptar y validar los demás motores, con persistencia fiable primero.
5. Integrar generadores de bases y eliminar pasos manuales auxiliares.
6. Preparar distribución y probar en un equipo limpio.

No se asignan plazos aún: faltan la validación de instalación y las pruebas de
equivalencia de los tres módulos v2. Cada fase debe cerrar con evidencia concreta.
