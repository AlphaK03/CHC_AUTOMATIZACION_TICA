# Investigación de un dashboard TICA

Trabajo separado del Workbench, solicitado el 16 de octubre de 2026. Incluye
muestras reales de los seis módulos, documentación oficial, un modelo analítico
propuesto y un HTML navegable. No modifica la aplicación ni sus fuentes, datos,
configuración, calendarios o procesos. No publica servicios ni realiza consultas
por DUA/BL en TICA.

## Abrir el ejemplo

El resultado local está en:

`runtime/investigacion_dashboard/index.html`

Se abre con doble clic, sin servidor, instalación, internet ni credenciales.
Contiene su propia instantánea JSON: no vuelve a consultar los datos al abrirlo.
Las páginas Panorama, Relaciones, Explorar datos e Investigación permiten filtrar
por período/aduana/régimen, buscar un DUA y abrir sus tributos, movimientos y
líneas de tránsito. El explorador también muestra BLs y sus conocimientos.

Los filtros de aduana y régimen se refieren a los DUAs; el bloque de carga conserva
su alcance independiente. El selector de período se aplica a cada bloque según
su fuente. Septiembre no se presenta como si fuera octubre.

Los datos, HTML generado, inventario y capturas quedan en `runtime/`, excluidos de
Git. Solo se versionan la plantilla, los scripts y esta investigación. La muestra
omite nombres de consignatarios y las identificaciones/nombres de garantes.

## Resultado de la muestra inicial

| Fuente | Muestra | Unidad de observación |
| --- | ---: | --- |
| Detalles | 128 | Cabeceras DUA confirmadas |
| DUAs Tránsito | 111 | Líneas confirmadas de 32 DUAs; hasta 16 por DUA |
| Talón | 233 | Filas tributarias de 32 DUAs |
| XMovimientos | 53 | Filas asociadas de 32 DUAs con movimientos |
| XMovimientos, vacíos | 32 | Observaciones verificadas, separadas de las filas |
| BLs | 60 | Líneas de 24 BLs confirmados; hasta 12 por BL |
| Manifiestos / Conocimientos | 88 | Conocimientos de manifiestos confirmados |

Los cuatro primeros consumen resultados de octubre de 2026; carga tiene
septiembre de 2026. Conocimientos contiene fuentes marítima y aérea con estados
de cobertura diferentes. Ninguna de estas cifras acredita un mes completo.

Se eligieron primero hasta 32 DUAs confirmados de cada consumidor, y después se
buscaron sus cabeceras en Detalles. Se añadieron 32 cabeceras iniciales de Detalles
y cabeceras relacionadas con vacíos verificables. Por eso la coincidencia es
**dirigida**, no una estimación estadística de calidad o cobertura.

| Enlace comprobado | Coincidencias | Llave utilizada |
| --- | ---: | --- |
| Talón → Detalles | 32 / 32 DUAs | Aduana + año + número |
| XMovimientos → Detalles | 32 / 32 DUAs | Aduana + año + número |
| Tránsito → Detalles | 32 / 32 DUAs | Aduana + año + número |
| BLs → Conocimientos | 24 / 24 BLs | Manifiesto compuesto + secuencia TICA, verificando BL comercial |

Se preservaron ceros e identificadores como texto. No se emplearon nombres,
importes ni semejanza textual para unir documentos. «Sin enlace en la muestra»
no significa «no existe en TICA».

## Cómo se conectan los datos

### Declaraciones

`Detalles.numero_del_dua`, `Talón.numero_del_dua`,
`XMovimientos.numero_del_dua` y `Tránsito.numero_del_dua` comparten el contrato
`NNN-AAAA-NNNNNN`. La combinación de aduana, año y número es la identidad; el
número de envío del declarante no la sustituye. La [consulta oficial DUA](https://portaltica.hacienda.go.cr/TicaExterno/hcimppon.aspx)
utiliza esos componentes.

Detalles es una cabecera por DUA. Talón es varias filas tributarias por DUA;
Tránsito es varias líneas de mercancía; XMovimientos es una asociación del DUA
con depósito/año/movimiento/tipo y sus bultos agrupados. El mismo DUA no se cuenta
de nuevo por aparecer en cada bot.

**La regla para los importes:** agregar Talón por DUA antes de cruzarlo con
movimientos o líneas. Dos tributos y tres movimientos producirían seis filas en
una unión plana; eso triplicaría el total tributario. El HTML suma exclusivamente
las filas tributarias de la muestra, sin materializar ese producto.

El [Mensaje DUA v3.18, p. 66](https://www.hacienda.go.cr/docs/Mensaje_TD_DUA-V3-18.pdf)
define `TOTP_MN` como total por pagar en moneda nacional. El [BCCR identifica el
colón como moneda nacional](https://www.bccr.fi.cr/cr/es/billetes-y-monedas.html).
El prototipo rotula el importe de `Valor_MN` como **tributos reportados en CRC**;
su correspondencia es semántica con el resumen Sftributos1, no una afirmación de
haber extraído ese campo XML. No lo llama pago bancario ni recaudación. El
[procedimiento oficial de reenvío de talones](https://www.hacienda.go.cr/docs/CIRDGT0582008.pdf)
también contempla cobros rechazados y reenviados.

### Documentos de carga

El identificador de manifiesto del repositorio conserva componentes de modalidad,
tipo, número, ubicación y fecha. Se utiliza completo. Un conocimiento se identifica
por ese manifiesto y su **secuencia TICA**; el número comercial del BL es otro
atributo, que puede repetirse en contextos diferentes.

La entrada SQLite de BLs conserva `IDManifiesto`, `Secuencia Tica` y `BL original`.
El CSV público de resultados BLs conserva `manifiesto` y `bls`, pero no el
secuenciador. Para esta investigación se leyó la entrada confirmada de SQLite y
se enlazaron sus líneas por `results.job`; así se recuperó esa llave sin modificar
el contrato de salida del bot. Conocimientos permite comprobar los tres campos.

El [Mensaje DUA v3.18, pp. 28–30](https://www.hacienda.go.cr/docs/Mensaje_TD_DUA-V3-18.pdf)
distingue la llave de carga de la de inventario. `CONO_EMBAR` es la referencia o
secuenciador TICA; no debe sustituirse por el texto comercial del BL. La
[consulta oficial Conocimientos–Movimientos](https://portaltica.hacienda.go.cr/TicaExterno/hcgconstk.aspx)
también muestra número de conocimiento y secuencial por separado.

### El puente pendiente: DUA ↔ carga

El bloque **YCGASOEX** del [mensaje de Ingresos/Salidas v1.69, pp. 34–35](https://www.hacienda.go.cr/docs/Formato-Mensaje-IngresosySalidas-V169.pdf)
describe asociaciones entre línea DUA y línea de conocimiento. Eso sustenta una
tabla puente; una cardinalidad muchos a muchos es una propuesta conservadora
de modelado, pendiente de medir en datos locales.

El procedimiento ya existente **DUAs por manifiesto** tiene un contrato prometedor:

| Campo local | Uso propuesto | Estado |
| --- | --- | --- |
| `manifiesto` | Identidad compuesta de la carga | Preservar completa y su procedencia |
| `Conoc.` | Secuencia TICA del conocimiento | Falta muestra que confirme correspondencia |
| `Línea` | Línea del conocimiento | Falta muestra |
| `Aduana`, `Año`, `DUA` | Construir identidad DUA | Contrato documentado |
| `Item` | Línea del DUA | Falta muestra |
| `Cantidad de Bultos` | Cantidad asignada al vínculo | No sustituye el total del BL |
| `Estado de la Asociación` | Vigencia o situación del vínculo | Definir estados aceptados |
| `Fecha de la Asociación` | Fecha propia de la relación | No sustituye arribo ni aceptación |

No se encontró una muestra local confirmada de ese procedimiento, ni de listado
principal, movimientos de manifiesto o contenedores. Se documentaron sus esquemas
sin ejecutarlos. **No se dibujó ningún enlace real DUA–BL en el prototipo.**
El formato oficial también contempla otros atributos en ciertos mensajes; el CSV
local descrito no incluye peso bruto asociado ni unidades comerciales. No se
promete ni estima peso enlazado proporcionalmente a los bultos.

### Movimientos y existencias

El inventario requiere al menos depósito + año + movimiento. El [manual oficial,
p. 205](https://www.hacienda.go.cr/docs/Manual_de_Procedimientos_Aduaneros2021_Febrero2021.pdf)
contempla varios movimientos por conocimiento y relaciones parciales. La
[consulta de inventarios](https://portaltica.hacienda.go.cr/TicaExterno/hskmovstk.aspx)
distingue ancestros, descendientes y asociaciones; la [consulta por tipo de bulto](https://ticaconsultas.hacienda.go.cr/Tica/hskinfbul.aspx)
separa usados y salidos. Por ello:

- XMovimientos por DUA y movimientos de manifiesto se conservan separados.
- Los bultos asociados a un DUA no se presentan como stock actual del depósito.
- Una entrada, salida y afectación no se suman sin una regla de saldo validada.
- Los vacíos verificados son observaciones, sin inventar filas con cero bultos.

## Propuesta de arquitectura

1. Tomar instantáneas de resultados confirmados con procedencia y fecha de corte,
   fuera de los procesos que descargan. Usar una capa analítica independiente.
2. Mantener dimensiones DUA, manifiesto y conocimiento; hechos tributarios,
   líneas de tránsito, líneas BL y asociaciones de movimientos separados.
3. Incorporar la tabla puente cuando exista una muestra confirmada de DUAs por
   manifiesto y se validen sus columnas/estados.
4. Agregar las medidas en su nivel correcto antes de cada cruce. Mantener la
   cobertura por fuente/período junto a cada indicador.
5. Alimentar un HTML estático, una API analítica o Power BI desde esa capa. Esta
   entrega solo materializa el HTML de muestra; no configura ni conecta Power BI.

`modelo_propuesto.sql` contiene un esquema ilustrativo: **no es una migración de
la app y no se ejecuta sobre sus bases**. Conserva instantáneas separadas para no
sumar repetidamente el mismo resultado en distintas fechas de extracción.

## Reproducir la investigación

Desde la raíz del repositorio:

```powershell
.\workbench\.venv\Scripts\python.exe investigacion/dashboard_tica/snapshot.py
.\bots\detalles\.venv\Scripts\python.exe investigacion/dashboard_tica/validate_preview.py
```

El primer script usa solo la biblioteca estándar. Abre SQLite con `mode=ro` y
`query_only`, lee exclusivamente resultados confirmados y escribe únicamente
en la carpeta de investigación. No importa código de los bots ni servicios del
Workbench. Si una fuente está ocupada o no es legible, la registra como no
disponible; no intenta recuperar ni cambiar sus reservas.

El segundo usa el Playwright ya instalado para un navegador efímero sin red:
carga el HTML local, comprueba navegación, filtros, detalle DUA/BL, suma tributaria,
separación de períodos y formato móvil. Guarda capturas y `VALIDACION.json` en la
carpeta generada. No abre el navegador del bot ni toca la instancia de la app.

Archivos generados:

- `index.html`: dashboard autónomo con la muestra incorporada.
- `muestra.json`: filas seleccionadas, enlaces, notas y hash de la selección.
- `FUENTES.json`: inventario de fuentes, estados y criterios de lectura.
- `VALIDACION.json`: resultado de la comprobación del HTML.
- `panorama.png`, `detalle-dua.png`, `relaciones.png`, `movil.png`: vistas comprobadas.

## Límites y siguientes comprobaciones

Las lecturas se realizan por fuente y en instantes distintos; no es una foto
transaccional conjunta de todos los bots. La muestra no es aleatoria y no se
pueden extrapolar sus sumas, proporciones ni porcentajes de enlace.

Antes de un dashboard conectado falta reunir muestras del mismo período y
modalidad, obtener la asociación DUA–conocimiento desde datos ya terminados,
resolver los estados de asociación, comprobar la granularidad de contenedores,
validar monedas/unidades de valores aduaneros y definir cómo se actualizan
rectificaciones, reliquidaciones y cambios de inventario. Nada de ello exige
modificar ahora los motores activos.
