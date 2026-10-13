# Herramientas de desarrollo

`benchmark_bls.py` compara el motor actual con cuatro combinaciones de sesiones,
detalle y concurrencia, en dos rondas. Limita la muestra a entre uno y cuatro BL.
Las llamadas consultan TICA; usar únicamente una muestra y una salida independientes.

```powershell
python scripts/benchmark_bls.py --archivo ruta/muestra.xlsx --limite 2 --salida logs/comparacion_nueva
```

Para procesar y exportar normalmente, usar `run_cli.py`; para comprobar el motor
sin consultar el portal, ejecutar las pruebas de `tests/`.

`verify_conocimientos_input.py` prueba el contrato entre el generador real de
Manifiestos y este bot. Crea archivos pequeños temporales, abre XLSX/SQLite,
compara filas y firmas y procesa/reanuda con sesiones simuladas. No consulta TICA
ni modifica el progreso de producción. Opcionalmente lee las primeras 12 filas
de dos bases reales del mismo alcance con `--sqlite-real` y `--excel-real`.

```powershell
python scripts/verify_conocimientos_input.py --manifiestos D:\PortafolioDesarrollador\Manifiestos_Bot2 --informe logs/compatibilidad_conocimientos.json
```
