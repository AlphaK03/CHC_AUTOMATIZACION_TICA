# Cuenta CHC y resultados en SharePoint

La conexión es opcional. **Cuenta y SharePoint**, en la barra lateral, permite
conectar una cuenta de CHC, elegir sitios, bibliotecas y carpetas, y asignar un
destino a cada bot o procedimiento de Manifiestos. La aplicación funciona sin
cuenta y conserva siempre SQLite, CSV locales y recuperación de los bots.

## Registro creado en Microsoft Entra

Se creó mediante la sesión autorizada del usuario el 14 de octubre de 2026:

| Campo | Valor |
| --- | --- |
| Nombre | CHC Workbench · Resultados SharePoint |
| Id. de aplicación | `da7ff4b7-8a2e-4c49-9338-17975a058a99` |
| Id. de directorio CHC | `f7015bc9-c229-413a-ab08-e1e5a76a09f1` |
| Tipo de cuenta | Solo CHC Consultores, un inquilino |
| Plataforma | Aplicaciones móviles y de escritorio |
| Retorno | `http://localhost` |
| Lectura y exploración Microsoft Graph | `Sites.Read.All`, delegado (autorizado por el usuario después del registro inicial) |
| Escritura Microsoft Graph | `Sites.Selected`, delegado |

El permiso `User.Read` agregado por defecto fue retirado. No se crearon secretos,
certificados ni permisos de aplicación. Los identificadores públicos se incluyen
en `workbench/sharepoint_app.json`; no son credenciales.

MSAL usa el navegador del sistema, código de autorización con PKCE y renovación
silenciosa. Los ámbitos OIDC de sesión son administrados por MSAL. Los tokens se
guardan con DPAPI, cifrados para el usuario de Windows; nunca se incluyen en Git,
la salida del worker o los logs. **Desconectar** elimina la sesión local de esta
app; no cierra la sesión general de Microsoft del navegador.

## Autorizar un sitio cuando se elija

`Sites.Read.All` delegado permite explorar y leer los sitios a los que tenga acceso
la cuenta conectada. El usuario eligió expresamente esta opción para navegar por
todas sus bibliotecas. Se usa `/sites?search=...`, con paginación y filtro al host
SharePoint de CHC. No concede escritura general.

`Sites.Selected` permite escritura únicamente en sitios autorizados explícitamente.
El consentimiento OAuth y la asignación al sitio son pasos diferentes. Todavía
no se asignó ningún sitio: el usuario configurará sus rutas más adelante.
El consentimiento al ámbito debe completarse al conectar, conforme a las
políticas del directorio; un administrador deberá intervenir si esas políticas
lo requieren.

Cuando se conozca el sitio, un administrador con las facultades necesarias debe
asignar el rol `write` a esta aplicación, por ejemplo mediante Microsoft Graph
Explorer o una herramienta administrativa ya autorizada. Esa herramienta necesita
los permisos administrativos para gestionar acceso; **no agregarlos a Workbench**.
Resolver primero su identificador con:

```http
GET https://graph.microsoft.com/v1.0/sites/{host-sharepoint}:/sites/{nombre-del-sitio}
```

Y aplicar la asignación:

```http
POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
Content-Type: application/json

{
  "roles": ["write"],
  "grantedToIdentities": [{
    "application": {
      "id": "da7ff4b7-8a2e-4c49-9338-17975a058a99",
      "displayName": "CHC Workbench · Resultados SharePoint"
    }
  }]
}
```

Además, cada usuario conectado debe tener permiso para escribir en la carpeta.
La autorización efectiva es la intersección entre su acceso y el de la app.
El selector permite buscar sitios por nombre o introducir su URL. También acepta
la página de **Bibliotecas** de CHC y los enlaces `FileBrowser.aspx` que contiene;
se normalizan al sitio correspondiente antes de consultar Microsoft Graph.
La asignación está limitada al sitio; las rutas elegidas en la interfaz no son
una restricción adicional de permisos a nivel de carpeta.

## Uso

1. Abrir **Cuenta y SharePoint** y pulsar **Conectar cuenta CHC**.
2. Seleccionar el bot o procedimiento y pulsar **Explorar sitios**, o introducir
   una URL de SharePoint y pulsar **Ver bibliotecas**. La página inicial
   `https://chcconsultorescr.sharepoint.com/_layouts/15/sharepoint.aspx/onedrive/places`
   abre el catálogo de sitios; elegir uno para ver sus bibliotecas.
3. Elegir biblioteca, recorrer carpetas y pulsar **Usar esta carpeta**.
4. Ejecutar el bot o exportar sus resultados normalmente. Los CSV se envían a
   `carpeta elegida / nombre del lote / nombre original del CSV`.

Se publican exclusivamente los CSV de resultados, sin transformar columnas,
codificación ni datos. SQLite, pendientes TXT/JSON y diagnósticos siguen locales.
Las exportaciones periódicas/finales del motor DUA y las publicaciones de BLs y
Manifiestos notifican al proceso online. No se inicia ninguna consulta TICA por
conectar, seleccionar destinos o reintentar una subida. No se envían resultados
antiguos al agregar una ruta: pulsar **Exportar** en el lote deseado para hacerlo.

La cola online es independiente y persistente. Sin sesión o red, conserva las
copias pendientes; después de conectar, envía pendientes compatibles con esa
cuenta y destino. Los errores de publicación quedan visibles y se reintentan
con **Reintentar envíos**. Retirar o cambiar un destino pausa sus copias pendientes
anteriores. No redirige automáticamente esos archivos a otra cuenta o carpeta.

Una primera subida no reemplaza archivos preexistentes. Para futuras versiones
de un archivo publicado por esta app se conserva el identificador y `eTag`;
se rechazan modificaciones o movimientos externos. Dos lotes diferentes tampoco
pueden usar el mismo nombre y destino. Ante un conflicto, se conserva el archivo
online y el CSV local; elegir otro destino o resolverlo antes de reintentar.

## Implementación y validación

`chc_cloud/` administra MSAL, Graph y la cola; `sharepoint_bridge.py` inicia un
proceso del entorno Workbench, separado de todos los bots. Configuración local,
avisos pendientes, caché DPAPI y SQLite están en
`runtime/workbench/sharepoint/`, excluido de Git. Al cerrar, se termina solo ese
proceso y se recuperan sus publicaciones inconclusas al siguiente inicio.

Comprobaciones realizadas: 12 pruebas de publicación y transporte con Graph
simulado, dos pruebas de interfaz/proceso y cifrado real de Windows; integración
local de Talón/XMovimientos y cinco procedimientos de Manifiestos con entrega a
BLs; smoke QML. Se comprobaron registro, directorio, retorno y permiso en Entra.
Actualización de navegación: se verificó una conexión OAuth real con la cuenta
CHC del usuario. Con el ámbito inicial `Sites.Selected`, la lectura del sitio raíz
devolvió 403 por falta de asignación. En Edge se comprobaron seis entradas de
biblioteca y sus enlaces reales, sin extraer cookies ni tokens del navegador.
El usuario agregó `Sites.Read.All` delegado al registro; al renovar la sesión,
Microsoft mostró **Se necesita la aprobación del administrador**. Por tanto, la
exploración real por Graph con el nuevo ámbito sigue pendiente de aprobación.
Se añadieron pruebas de enlaces reales, catálogo de sitios y filtro al host CHC:
15 pruebas cloud y dos de Qt/worker/DPAPI, más smoke QML, satisfactorias.
No se subieron archivos ni se configuraron destinos reales. Estas pruebas no
demuestran una entrega real a SharePoint ni una actualización de Power BI.

Referencias oficiales: [permisos seleccionados](https://learn.microsoft.com/en-us/graph/permissions-selected-overview),
[registro de escritorio](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration),
[MSAL Python](https://msal-python.readthedocs.io/en/latest/),
[cargas por sesión](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0).
La búsqueda delegada de sitios usa el permiso documentado en
[Search for sites](https://learn.microsoft.com/en-us/graph/api/site-search?view=graph-rest-1.0).
