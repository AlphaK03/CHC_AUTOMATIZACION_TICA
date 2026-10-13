# Manifiestos en CHC Workbench

- Leer `../../docs/INTEGRACION_MANIFIESTOS.md` y el AGENTS de la raíz.
- Origen de referencia: `D:/PortafolioDesarrollador/Manifiestos_Bot2`; no modificarlo.
- `source_manifest.json` conserva los hashes de 28 fuentes/pruebas originales.
  No cambiar esos archivos para adaptar la interfaz. Motores nuevos y envoltorios
  viven en `../../chc_runtime/manifest_adapters.py`, `manifest_service.py` y `batch_worker.py`.
- Mantener cinco procedimientos independientes y el generador local para BLs.
  La GUI QML nunca importa motores ni paquetes `utils`, `core` o Tk de los bots.
- Conservar columnas, texto, ceros, duplicados legítimos, orden, filtros, páginas,
  checkpoints y validación de identidad del original. Contenedores usa Llenos.
- Solo una tabla vacía confirmada es éxito. Una respuesta inválida o mercancía
  incompleta permanece pendiente. DUAs conserva su excepción frmAmbiente y sus
  reglas de contadores; no aplicarlas a otros procedimientos sin comprobarlos.
- No aplicar el timeout de Detalles a DUAs por manifiesto: su espera ilimitada
  con cliente HTTP independiente es una decisión explícita del motor original.
- Bases BLs: solo Courier N, filas confirmadas y contrato de cinco columnas TEXT.
  No incluir avances parciales ni confundir asociaciones DUAs con regímenes.
- Resultados públicos: únicamente CSV de datos, en carpeta con nombre elegido.
  SQLite, logs, revisiones y auditoría son privados. No sobrescribir CSV ajenos.
- Importar progreso por instantánea de solo lectura y conservar su original.
  No migrar índices CSV a éxitos. Recuperar reservas solo bajo bloqueo al iniciar.
- No ejecutar organización/limpieza de resultados de la aplicación original.
  Las rutinas copiadas solo reciben rutas de trabajo propias del Workbench.
- Probar cambios sensibles con el portal local de `manifest_fixture.py`, salida
  temporal y consultas de red deshabilitadas; no usar lotes de producción como prueba.
- La integración comprobada es mensual y por intervalos dentro del mes.
  No presentar como implementado un calendario diario continuo para este módulo.
