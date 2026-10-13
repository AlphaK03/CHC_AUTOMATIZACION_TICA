# Entrega inicial — 12 de octubre de 2026

La fase 0 está completada: plan, cinco copias modulares y comprobación de
integridad. No se ha implementado aún la interfaz Workbench ni el ejecutor común.

| Módulo | Archivos copiados | Versión tomada |
| --- | ---: | --- |
| BLs | 40 | Raíz actual de BLs_BOT |
| Detalles | 44 | Raíz actual de Detalles_BOT |
| DUAs Tránsito | 14 | v2 |
| Talón | 14 | v2 |
| XMovimientos | 15 | v2 |
| Total | 127 | Código de trabajo actual |

Los conteos incluyen tres specs conservados como referencia. Además se generan
ocho ejemplos de configuración y tres archivos de requisitos runtime iniciales:
138 archivos de módulos registrados para comprobación SHA256.

La verificación local comprueba 97 archivos Python (incluye las dos herramientas)
sin errores de sintaxis, los cinco descriptores y sus recursos requeridos. No
se instalaron dependencias ni se ejecutaron los bots o consultas al portal.
El informe reproducible se conserva en `migration/validation.json`.

La copia mantiene los cambios locales guardados y los catálogos de ejecución;
no lleva datos de producción ni progreso. Las fuentes originales permanecen en
su ubicación. La integración de DUAS_SCRAPPING y de otros generadores queda en
la fase posterior indicada en el plan.

Siguiente entrega: validar instalación/apertura de los módulos e implementar el
acceso de escritorio a partir de `workbench/modules.json`, con procesos separados.
