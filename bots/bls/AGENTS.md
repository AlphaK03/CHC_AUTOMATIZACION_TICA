# Trabajo en este repositorio

Leer `README.md`, `docs/ARQUITECTURA.md` y `CLAUDE.md` antes de modificar el motor.
La implementación activa está en `src/` (`main.py`, `cli.py`, `core/`),
rama `AstraCode/bls-asyncio`. No crear carpetas de código por versión.
Conservar configuración local, Excel, SQLite, CSV y progreso existente.
`src/` contiene exclusivamente la versión actual. No recuperar los motores
antiguos ni recrear `legacy/` o `v2/`. Configuración y datos locales quedan
en la raíz en desarrollo, y junto al ejecutable dentro de `dist/` en distribución.

Para comprobar cambios, usar `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
Después de cambiar fuentes funcionales, recompilar y verificar el ejecutable.
No reemplazar un ejecutable abierto ni terminar una descarga de producción a la fuerza.

Preferencia del usuario: al terminar el trabajo, emitir un pitido de tres segundos
justo antes de enviar la respuesta final. En Windows: `[Console]::Beep(900, 3000)`.
