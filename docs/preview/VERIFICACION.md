# Verificación del panel — 12 de octubre de 2026

## Actualización: Detalles integrado

Tras la simplificación solicitada por el usuario, se renovó
`detalles-integrado.png`: carga correcta, módulo listo y cero advertencias QML.
Esta revisión visual no ejecutó consultas al portal ni repitió las suites del motor.

La primera integración operativa se documenta en
[INTEGRACION_DETALLES.md](../INTEGRACION_DETALLES.md). La captura
`detalles-integrado.png` muestra el panel real con la tabla de dos DUAs validada.
Se completaron 50 pruebas del bot y cinco de integración; la prueba real obtuvo
los mismos 38 campos que el original, sin repetir consultas al retomar. La copia
conserva los archivos originales y los repositorios de origen no cambiaron.
El smoke test de las cinco demostraciones volvió a pasar tras la integración.

## Evidencia histórica del prototipo

Entorno propio: Python 3.12, PySide6-Essentials 6.12.0 y shiboken6 6.12.0.
`pip check` no reporta requisitos incompatibles.

Comprobaciones completadas:

- Carga de la ventana y de las cinco páginas QML sin advertencias.
- Simulación independiente por módulo; pausa y continuación del avance.
- Cambio de módulo sin perder el estado de los demás.
- Reinicio y finalización de un lote sintético de 240 registros.
- Resultados de muestra confirmados al completar la simulación.
- Búsqueda, búsqueda sin coincidencias, navegación contraída y cambio de tema.
- Ningún módulo Python importado desde `bots/` durante la prueba.
- Capturas revisadas de vista general oscura, Detalles y tema claro contraído.
- Apertura real en Windows de `CHC Workbench · Panel de prueba`, con proceso
  respondiendo y registro de errores vacío.
- Los 138 archivos de módulos coinciden con sus hashes iniciales; los 127
  archivos fuente originales y el estado Git de los cinco orígenes no cambiaron.

Estas comprobaciones acreditan el prototipo y la integridad de la copia. No
certifican motores, comportamiento de TICA, bases reales o integración operativa.

Para reproducir: consultar `workbench/README.md`. Objetivo final y decisiones para
continuar desde otra sesión: `docs/CONTEXTO_PROYECTO.md` y `AGENTS.md`.
