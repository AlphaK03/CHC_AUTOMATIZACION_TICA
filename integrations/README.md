# Proveedores de bases — fase posterior

Primer candidato: `D:/PortafolioDesarrollador/DUAS_SCRAPPING`.
Se copió a `duas_source/` y se integra en un proceso separado para el piloto diario
de Detalles. El repositorio original permanece intacto. La copia del extractor
tiene una adaptación documentada para confirmar consultas sin registros, mediante
`src/query_confirmation.py`; el manifiesto conserva la línea base inicial.
Leer el [piloto implementado](../docs/PILOTO_DETALLES_DIARIO.md).

Su adaptación deberá proporcionar datasets DUA con período, régimen, selección,
procedencia y cobertura verificada. Se preservan las tres clasificaciones Total,
Tránsito e Importación y la compatibilidad de `NroDUA` como texto.

Correspondencia confirmada por el usuario: Total → Detalles; Tránsito → DUAs
Tránsito; Importación → Talón y XMovimientos. El objetivo incluye obtener la base
desde cada bot sin elegir Excel, por mes terminado o mediante el ciclo diario de
ayer, procesamiento, espera a las 00:01 y recuperación de fechas atrasadas.
Los resultados se acumulan en el mes de los datos. Leer el contrato completo en
[`docs/AUTOMATIZACION_DIARIA.md`](../docs/AUTOMATIZACION_DIARIA.md).

El proveedor BLS de Conocimientos/Manifiestos requiere un inventario adicional;
su contrato actual son las cinco columnas documentadas en `docs/INVENTARIO.md`.
Agregar proveedores como módulos independientes, sin dependencias de sus GUI.
