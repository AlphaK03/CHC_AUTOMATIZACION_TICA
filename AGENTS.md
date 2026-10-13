# Mantenimiento de CHC Workbench

- Leer primero `docs/CONTEXTO_PROYECTO.md`: objetivo final, stack, decisiones,
  restricciones y estado real para retomar desde otra sesión.
- Destino: una plataforma de escritorio modular Python + PySide6 + Qt Quick/QML
  que administre bots, bases, lotes y resultados desde un solo repositorio.
  Integrar generadores más adelante para eliminar aplicaciones auxiliares.
- Requisito confirmado de autonomía: leer `docs/AUTOMATIZACION_DIARIA.md`.
  Total_DUAS alimenta Detalles; Transito alimenta DUAs Tránsito; Importacion
  alimenta Talón y XMovimientos. Cada bot deberá obtener su base sin elegir Excel,
  con modos mensual y diario: día anterior, espera hasta 00:01 Costa Rica,
  recuperación de días atrasados y resultados acumulados en su mes correspondiente.
  Este ciclo está documentado como objetivo, todavía no implementado.
- Alcance vigente ampliado: integrar y hacer funcionar Detalles, preservando
  todas sus funciones, SQLite, pendientes, validaciones, configuración y respaldos.
  El usuario autorizó usar datos base originales como prueba. Leerlos sin modificar
  los originales, probar una muestra acotada y usar almacenamiento/salida propios.
- Los otros cuatro módulos siguen en demostración y no se refactorizan en esta fase.
- Aislar el motor de Detalles en un proceso: la GUI Qt no importa paquetes de bots.
  El backend de demo nunca realiza consultas reales. No anunciar demos como éxitos.
- Las pruebas reales de esta integración están limitadas a dos DUAs de la base
  original y una ronda por DUA, con un trabajador y carpetas separadas.
- La interfaz clásica de la copia se conserva como compatibilidad temporal;
  no lanzar el ejecutable original ni depender de él.
- Interfaz en `workbench/qml/`; demo en `workbench/demo.py`; arranque en
  `workbench/app.py`; entorno propio `workbench/.venv/`.
- Preferencia explícita del usuario: interfaz sencilla, similar a la clásica.
  Mostrar el flujo principal; evitar tarjetas, textos técnicos y opciones extra
  a la vista. Conservar funciones secundarias en menús, ventanas o secciones plegadas.
- En Resultados mostrar únicamente el CSV, en una carpeta con el nombre elegido
  de la tabla, sin subcarpetas de UUID. TXT/JSON y diagnósticos son internos en
  `bots/detalles/data/exports/<id>/`; mantener SQLite y recuperación intactos.
- Ajustar la verificación al riesgo. En cambios visuales hacer una comprobación
  breve de carga/captura; no repetir suites completas ni consultas reales.
  Reservar pruebas amplias para cambios sensibles de motor, datos o recuperación.
- Actualizar README, contexto y manual del panel distinguiendo objetivo final,
  funcionalidad implementada y pendientes. La documentación debe servir de
  contexto autosuficiente a una nueva sesión.
- Leer `README.md`, `docs/PLAN_IMPLEMENTACION.md` y `docs/INVENTARIO.md`.
- Los repositorios originales son fuentes de referencia; hacer cambios aquí.
- Código activo: `bots/<id>/src/`. Tránsito, Talón y XMovimientos provienen de
  `v2/`; no incorporar los `src/` antiguos ni crear carpetas por versión.
- Cada módulo mantiene sus imports aislados. No importar varios motores en un
  mismo proceso mientras existan nombres globales `core`, `utils`, `ui`, `flows`.
- Preservar identificadores como texto, ceros iniciales, formatos de salida y
  resultados confirmados. No convertir índices de sesión en prueba de éxito.
- No borrar bases, progreso, entradas ni resultados durante reorganizaciones.
- La entrega inicial conserva las fuentes copiadas byte a byte. Una modificación
  futura del motor debe documentarse: el manifiesto registra la línea base inicial.
- Leer las instrucciones internas de cada módulo antes de cambiar su motor.
- Validar con `py -3.12 tools/verify_import.py` durante la etapa de copia.
  Las fases funcionales requieren pruebas offline por módulo y de recuperación.
- No consultar bases de producción para probar cambios. Las pruebas reales deben
  ser explícitas, acotadas y con una carpeta de salida independiente.
- No asumir que copiar el código demuestra independencia de generadores externos.
- No publicar ni desplegar automáticamente como parte de una revisión local.
