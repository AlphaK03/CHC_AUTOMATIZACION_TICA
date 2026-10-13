# Copia inicial y comprobación

`tools/import_bots.py` copia únicamente las cinco raíces activas registradas.
Sus modos son explícitos: `--plan` genera un inventario previo sin copiar bots;
`--copy` exige ese plan y copia los archivos incluidos sin sobrescribir destinos.
Comprueba el hash antes y después de leer cada fuente. No usa checkout, git clean,
git reset ni movimientos sobre los originales.

```powershell
py -3.12 tools/import_bots.py --plan
py -3.12 tools/import_bots.py --copy
py -3.12 tools/verify_import.py
py -3.12 tools/verify_import.py --check-sources
```

Estos comandos se incluyen como trazabilidad de la operación inicial. No repetir
`--plan`/`--copy` para actualizar un módulo ya modificado: el script rechaza
destinos existentes y el manifiesto inicial debe conservarse.

## Se incluye

Fuentes, pruebas, documentos, scripts de mantenimiento, requisitos presentes en
la raíz activa, specs relativos, catálogos JSON y los tres Excel CAPTCHA de v2.
Se generan ejemplos de machine/session desde las constantes por defecto del
código mediante AST, sin importar ni ejecutar bots. No se copian los JSON locales.

Los specs externos a v2 se registran como referencias documentales, byte a byte,
en cada módulo; no se añaden como puntos de compilación operativos.

## Se omite

Historias `.git`, IDE, ajustes de agentes locales, entornos, build/dist, binarios,
datos cargados, SQLite, CSV, logs, capturas, HTML de diagnóstico, drivers descargados
y configuraciones personales. Se conservan las fixtures HTML de las pruebas.
Los archivos omitidos dentro de las raíces seleccionadas se enumeran en el plan;
los árboles podados se registran por directorio sin recorrer sus datos.

Los árboles antiguos fuera de v2 y el archivo histórico `codigo viejo` de Detalles
quedan fuera del alcance por elección de versión. No se alteran ni eliminan.

## Evidencia

- `docs/migration/copy_plan.json`: lista previa y clasificación.
- `docs/migration/import_manifest.json`: rutas fuente/destino, tamaño, SHA256,
  rama, HEAD y estado Git de cada origen.
- `docs/migration/validation.json`: integridad de copia, sintaxis y registro.

Los informes describen una instantánea del disco, no una importación del historial
de commits. El SHA256 verifica la copia y permite detectar modificaciones futuras.
El verificador no acredita instalación, pruebas de negocio, empaquetado ni el
comportamiento de TICA; esos controles pertenecen a las siguientes fases.

`--check-sources` compara también los archivos originales y su estado Git con
la instantánea previa. Es opcional: una vez trasladado el repositorio, la
verificación normal funciona sin acceso a las fuentes originales.
