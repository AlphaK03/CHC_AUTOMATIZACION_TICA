# Consultas reales y cancelación de la muestra — 2/11/2026

El usuario informó que DUAs por manifiesto y Contenedores parecían no avanzar.
Confirmó que cerró él mismo la app. No se atribuyó el cierre a un fallo del programa.

Se consultaron literalmente los dos manifiestos aéreos de la captura, con los
workers originales de ambas ramas, navegador real, dos trabajadores y raíces
temporales independientes. No se utilizaron fixtures, HTML local ni resultados
precargados. La rama base `8f75fb9` recibió HTTP 504 en ambos casos, en unos
127 segundos, sin filas confirmadas. La optimizada `24d8c52` recibió HTTP 504 en
uno y una página `frmAmbiente` en el otro, en unos 247 segundos, sin filas
confirmadas. Se conservaron las reglas originales de pendientes/exclusiones.
Son errores devueltos por TICA y no evidencia de una extracción exitosa.

Contenedores abrió páginas reales de mercancías de tres manifiestos marítimos
que figuraban en los registros. La muestra resultó demasiado extensa y el usuario
pidió cancelarla. Se canceló su supervisor y se comprobó que no quedaran procesos
de esa prueba ni sus navegadores. **Esta muestra no se presenta como validada.**
No se aplicaron sus datos, intentos ni estados a las colas operativas.

El usuario aclaró que bastan pocas muestras pequeñas con información realmente
extraída. Las comprobaciones reales anteriores ya confirmaron, entre otros,
135 filas de Conocimientos, 262 de DUAs por manifiesto y 200 de Contenedores,
además de los cuatro consumidores DUA y BLs. Sus conteos constan en
[el recibo de memoria](benchmarks/memoria-2026-11-02.json); no fueron simulaciones.
No se iniciarán más descargas de prueba como parte de este diagnóstico.

Los recibos detallados y el registro de cancelación permanecen privados en
`runtime/real-stall/`. La extracción y la interfaz quedan en el código ya validado
de `24d8c52`; no se entrega un cambio funcional nuevo sin comprobación. La rama
original y sus archivos de código permanecen intactos. La app queda cerrada según
la acción del usuario. No se reinició ni se reanudaron consultas automáticamente.

La revisión automática rechazó la limpieza del temporal propio cancelado con
`blocked by policy`. Queda pendiente, sin procesos activos ni espacio presentado
como liberado. Destino y motivo en `runtime/real-stall/cancelled-contenedores.json`.
