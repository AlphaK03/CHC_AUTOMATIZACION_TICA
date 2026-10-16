# Bases propias y ejecución diaria de los bots

Actualización del 16 de octubre: el diario normal de los cuatro bots DUA continúa
después del rango elegido. Al reabrir basta Iniciar; Desde/Hasta y Calendario
muestran el rango pendiente sin mover el origen persistente ni reabrir omitidos.
Tras agotar los días disponibles espera a las 00:01 de Costa Rica e incorpora el
nuevo día. El inicio conjunto por mes y los reintentos explícitos siguen acotados.
Esta regla sustituye la parada por Hasta del piloto original.

Actualización del 14 de octubre: los cuatro bots de DUA hacen hasta tres intentos
automáticos por pendiente y mantienen ese límite al reiniciar. Después dejan el
día **Omitido** y continúan; no lo reabren por sí solos. **Reintentar mes/día**
solicita otra ronda solo para pendientes. Esta política sustituye la recuperación
automática indefinida descrita como objetivo inicial. Véase el uso actualizado en
[Workbench](../workbench/README.md#revisión-en-tica-y-recuperación-de-pendientes).

Requisito registrado el 12 de octubre de 2026. Detalles tiene el primer piloto en
`feature/detalles-base-diaria-calendario`; leer [PILOTO_DETALLES_DIARIO.md](PILOTO_DETALLES_DIARIO.md).
Este contrato también describe el objetivo de los otros consumidores, aún pendientes.

## Relación confirmada entre bases y consumidores

| Base actual de DUAS_SCRAPPING | Bot consumidor | Selección |
| --- | --- | --- |
| `Total_DUAS.xlsx` | Detalles | Los nueve regímenes |
| `Total_DUAS - Transito.xlsx` | DUAs Tránsito (`duas_transito`) | TRANSITO |
| `Total_DUAS - Importacion.xlsx` | XMovimientos | Los cuatro regímenes de Importación |
| `Total_DUAS - Importacion.xlsx` | Talón | Los cuatro regímenes de Importación |

Importación comprende IMPORTACION DEFINITIVA, IMPORTACION TEMPORAL,
REIMPORTACION y REIMPORTACION PERFECCIONAMIENTO PASIVO. Las dos selecciones
pertenecen al Total; no sumar las tres listas para formar una base nueva.
BLs tiene otra fuente de entrada y no pertenece a este ciclo DUA.

Hoy el usuario ejecuta DUAS_SCRAPPING para descargar los regímenes de un mes ya
terminado, por ejemplo septiembre, genera esos tres Excel y los selecciona en
los cuatro bots. El objetivo elimina ese trabajo manual: cada bot debe poder
obtener su propia base y ejecutar sus consultas desde el Workbench.

## Flujo solicitado

1. Obtener del portal los regímenes correspondientes a un período pasado.
   Conservar el modo mensual y añadir el modo diario automático.
2. En modo diario, descargar los datos del día anterior a la fecha local actual.
   No consultar el día en curso ni fechas futuras como si estuvieran completas.
3. Validar y guardar la descarga en SQLite, preparar la selección del bot y
   agregar sus DUAs a la tabla mensual sin repetir existentes ni borrar éxitos.
4. Ejecutar el motor del bot y conservar sus resultados y pendientes.
5. Si terminó antes de que haya otro día elegible, esperar hasta las **00:01**
   del siguiente día local. La interfaz y la detención deben seguir respondiendo.
6. Si al terminar ya hay otro día pasado elegible, continuar automáticamente.
   Recuperar días omitidos en orden cronológico; no saltar directamente al último
   ayer cuando una ejecución larga, un apagado o una pausa dejó varios pendientes.
7. Acumular los resultados en el archivo del mes al que pertenece la fecha
   consultada, aunque la ejecución termine en otro mes o año.

Ejemplo: el 13 de octubre se descarga y procesa el 12. Si termina ese mismo 13,
espera al 14 a las 00:01 para descargar el 13. Si termina el 14 después de las
00:01, puede empezar inmediatamente el 13. Si termina recién el 16, debe recuperar
el 13, 14 y 15, sin omitir días. El 1 de noviembre se procesa el 31 de octubre y
se actualiza el archivo de octubre.

## Reglas para la implementación

- Calendario y hora: `America/Costa_Rica`. Usar fechas locales y esperar hasta
  la próxima fecha/hora elegible; no usar una pausa fija de 24 horas después de
  terminar, porque produciría desplazamiento del horario.
- Guardar configuración inicial del período/fecha de inicio. No inferir qué
  historial descargar únicamente de la fecha de instalación.
- Cobertura de bases por fecha y régimen; progreso de extracción por bot y DUA.
  Descargar una base no demuestra que todos sus DUAs hayan sido procesados.
- No completar un día con una descarga fallida o incompleta. Una respuesta vacía
  validada sí puede completar un régimen. Conservar y reanudar fallos; no descartar
  pendientes ni declarar éxito solo porque terminó una ronda de intentos.
- Mantener identidad interna del mes con año completo (`YYYY-MM`); nombre visible
  compatible como `septiembre26`, o el nombre mensual que el usuario configure.
- Hacer acumulación transaccional y deduplicar por identidad DUA como texto.
  Dos ejecuciones del mismo día no duplican entradas ni resultados confirmados.
- Al reiniciar, recuperar primero el progreso persistido. No volver a descargar
  rangos verificados ni consultar DUAs ya guardados por ese bot.
- Un ciclo activo por bot. Coordinar descarga compartida y concurrencia del portal;
  no duplicar descargas porque Talón y XMovimientos consumen la misma selección.
  Cada módulo debe poder operar solo usando el proveedor integrado y su motor.
- Mantener las funciones actuales de DUAS_SCRAPPING: clasificación, validación
  XML, cobertura, reintentos/subdivisión, cancelación y publicación recuperable.
- Los Excel pueden conservarse como exportación de compatibilidad. La coordinación
  interna debe consumir datasets/SQLite y no pedir elegir un archivo cada día.
- Salida pública de cada bot: únicamente su CSV acumulado en la carpeta de su
  tabla mensual. Bases, TXT/JSON, diagnósticos y respaldos permanecen internos.
- No reemplazar un acumulado mensual por la lista o resultados de un solo día.
  No presentar un mes parcial como si tuviera cobertura completa.
- Interfaz sencilla: modo mensual/manual o diario automático, período inicial,
  iniciar/detener y estado breve (descargando, procesando, esperando próxima fecha).
  Evitar añadir controles técnicos y tarjetas a la pantalla principal.

## Viabilidad y trabajo pendiente

El generador actual acepta rangos personalizados de un solo día y guarda fechas,
regímenes y cobertura en SQLite. Detalles ya permite agregar DUAs sin perder
resultados. Estas son bases útiles, pero no constituyen el ciclo automático.

El piloto de Detalles integra el proveedor, las entradas al catálogo, el
coordinador persistente, el calendario y la acumulación mensual. Los cuatro
consumidores DUA tienen recuperación transaccional y sus selecciones integradas.
Tránsito ya comparte el soporte `chc_runtime/` con Detalles y usa solo TRANSITO;
Talón y XMovimientos comparten la caché verificada de importación, serializan
el proveedor para no duplicar descargas y conservan calendarios/resultados
independientes. Ver `INTEGRACION_TRANSITO.md` e `INTEGRACION_IMPORTACION.md`.
La publicación actual de los tres Excel no acumula por sí sola entregas diarias:
genera el contenido de la entrega indicada y reemplaza los nombres compatibles.

La ejecución a las 00:01 requiere un equipo encendido y el coordinador en marcha.
Si debe continuar con la ventana cerrada, integrar ejecución en segundo plano y
arranque automático; ese comportamiento aún no está implementado. Al arrancar
después de un apagado, el coordinador debe recuperar las fechas pendientes.

La rama del piloto conserva este requisito y contiene ya las cuatro integraciones.
No inicia descargas al abrir ni modifica DUAS_SCRAPPING original. Las comprobaciones
offline y las consultas reales acotadas se distinguen en el documento de cada bot.
