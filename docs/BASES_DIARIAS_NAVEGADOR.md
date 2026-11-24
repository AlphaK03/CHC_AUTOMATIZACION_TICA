# Bases diarias y preparación del navegador — 24/11/2026

Detalles, DUAs Tránsito, Talón y XMovimientos no alcanzaban a descargar sus bases:
el proveedor fallaba al crear la sesión de Edge. El navegador instalado era
158.0.4370.33 y su controlador propio permanecía en 155.0.4283.62. SQLite guarda
`session not created` y ambas versiones. No era evidencia de cero DUAs ni de una
respuesta lenta de TICA: el fallo era anterior a la consulta.

La consola repetía un mensaje genérico por régimen, hasta tres rondas dentro de
cada invocación y tres ciclos diarios. Talón y XMovimientos además esperaban el
turno del proveedor de importación compartido. Esto explica los reintentos y el
tiempo transcurrido sin llegar a las consultas de los motores.

## Corrección y comportamiento vigente

Se instaló WebDriver 158.0.4370.33 en
`integrations/duas_source/drivers/msedgedriver.exe`, sin cambiar otros controladores
ni la distribución empaquetada. Microsoft exige coincidencia en los tres primeros
componentes de versión; una revisión final distinta sigue siendo compatible.
[Documentación oficial](https://learn.microsoft.com/en-us/microsoft-edge/webdriver/#download-microsoft-edge-webdriver).

La copia de desarrollo ahora prepara el navegador automáticamente al abrir:

- Una tarea compartida en `workbench/daily_browser_bridge.py` ejecuta
  `tools/install_daily_driver.py --json` fuera de Qt, después de adquirir la
  instancia única. Las segundas aperturas solo activan la ventana existente.
- Compara versiones locales; solo descarga desde Microsoft si falta el
  controlador o la compilación es incompatible. No inicia consultas a TICA,
  exportaciones ni subidas. No importa motores en Qt.
- `chc_runtime/selenium_browser.py` coordina el bloqueo del actualizador,
  descarga temporal, verificación y reemplazo atómico. Una descarga fallida,
  cancelación o ejecutable inválido conserva el anterior. Los temporales se
  limpian al salir; el cierre tiene supervisión acotada ante E/S sin respuesta.
- Los cuatro bots muestran **Preparando navegador…** y bloquean inicios diarios
  mientras se prepara. El inicio mensual comprueba lo mismo antes de cambiar
  configuraciones. Los errores muestran el motivo; el BAT sigue disponible
  como reintento manual. No hay reinicios ni consultas automáticas.
- El coordinador valida antes de rearmar un rango y antes del próximo día sin
  base, también después de esperar a las 00:01. El proveedor valida antes de
  planificar consultas. Una incompatibilidad local detiene el ciclo, conserva
  pendientes y no recorre otros días agotando oportunidades.

Demo, smoke, capturas y almacenamientos aislados no lanzan actualizaciones. La
distribución empaquetada conserva su Chromium y controlador incluidos; no requiere
adaptarlos al Edge de Windows. Los parsers y las fuentes copiadas del proveedor
permanecen intactos; la adaptación está en el soporte común y `worker.py`.

## Recuperar el intento fallido del 24/11

Inspección en modo lectura de los calendarios de desarrollo:

| Bot | Omitidos por el incidente | Día pendiente al detener |
| --- | --- | --- |
| Detalles | 6 de noviembre | 7 de noviembre |
| DUAs Tránsito | 6 al 10 de noviembre | 11 de noviembre |
| Talón | 6 de noviembre | 7 de noviembre |
| XMovimientos | 6 de noviembre | 7 de noviembre |

En cada bot: **Calendario → noviembre 2026 → Reintentar mes**. Recupera los días
sin completar del período y conserva los resultados confirmados; no consulta
otra vez sus DUAs guardados. El reintento mensual es acotado: después se puede
pulsar **Iniciar automático** para continuar el ciclo diario. También es posible
reintentar únicamente los días indicados. Las marcas manuales permanecen intactas.

La reparación no modifica estas marcas ni inicia los reintentos. El usuario
decide cuándo consultar. Los CSV siguen siendo manuales y separados por mes.

## Verificación y límites

Pasaron 42 pruebas offline distintas y el smoke QML:

```powershell
bots/detalles/.venv/Scripts/python.exe -m unittest chc_runtime.tests.test_daily_browser chc_runtime.tests.test_daily_resume chc_runtime.tests.test_daily_omissions -v
workbench/.venv/Scripts/python.exe -m unittest workbench.tests.test_daily_browser_setup workbench.tests.test_month_launcher -v
workbench/.venv/Scripts/python.exe -m unittest workbench.tests.test_details_daily workbench.tests.test_transit_bridge workbench.tests.test_import_bots_bridge -v
$env:DUA_TEST_DRIVER=(Resolve-Path integrations/duas_source/drivers/msedgedriver.exe).Path
bots/detalles/.venv/Scripts/python.exe -m unittest discover -s integrations/duas_source/tests -p test_browser.py -v
$env:CHC_LAYOUT_CAPTURES='runtime/diagnostics/daily-driver-20261124/layout'
workbench/.venv/Scripts/python.exe -m unittest workbench.tests.test_platform_layout -v
workbench/.venv/Scripts/python.exe workbench/app.py --smoke-test
```

Se comprobó actualización solo cuando hace falta, bloqueo entre actualizadores,
conservación del ejecutable previo ante fallo/cancelación, respuesta tardía al
cerrar, rechazo previo a modificar calendarios, reanudación de los cuatro bots y
conservación de éxitos/presupuestos. Edge real navegó únicamente al formulario
local. El smoke no emitió avisos QML y la auditoría de 229 vistas/diálogos no
encontró problemas en 1280×774, 1000×680 y 1000×600. Una expectativa antigua de
CSV automático en `test_details_daily.py` se adaptó al contrato manual vigente.

El controlador compatible respondió al instalador sin otra descarga. No se
consultó TICA para validar el arreglo; la descarga real desde Microsoft acredita
la instalación, no el estado del portal. La app se abrió sin consultas antes de
documentar y se conservó abierta durante la ampliación posterior. La actualización
automática se carga en su próxima apertura voluntaria. No se actualizó la
instalación empaquetada ni se generó otro instalador.

El preparador Qt también se ejecutó con su proceso real, fuera de la ventana
abierta: quedó listo en 0,266 s con las versiones compatibles y sin descargar
otro controlador. No es un tiempo garantizado. Se retiraron 226 capturas
sintéticas adicionales y se conservaron tres representativas con la auditoría;
los almacenamientos temporales de las pruebas se limpiaron al terminar.

Evidencia privada pequeña en `runtime/diagnostics/daily-driver-20261124/`:
diagnóstico de errores/calendarios, hashes de las tres bases del proveedor y
auditoría de geometría. Las pruebas usaron almacenamiento temporal, sin copiar
bases de producción. Controlador y bloqueo regenerables quedan fuera de Git.
