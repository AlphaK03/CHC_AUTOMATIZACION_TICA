import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

AppDialog {
    id:dialog; objectName:"savedDownloadsDialog"
    property var service:null
    property var selected:[]
    property var rows:service ? service.downloadCatalog.rows || [] : []
    property var filtered:rows.filter(row=>
        (target.currentIndex<=0 || row.target===service.uploadTargets[target.currentIndex-1].id) &&
        (month.currentIndex<=0 || row.period.slice(5,7)===String(month.currentIndex).padStart(2,"0")) &&
        (!year.text.trim() || row.period.slice(0,4)===year.text.trim()) &&
        (!search.text.trim() || (row.name+" "+row.filename).toLowerCase().indexOf(search.text.trim().toLowerCase())>=0))
    property var chosen:rows.filter(row=>selected.indexOf(row.id)>=0)
    property int missing:chosen.filter(row=>!row.csvReady).length
    property bool working:!!service && (service.busy || service.downloadGenerationBusy)
    title:"Descargas guardadas"; modal:true; anchors.centerIn:parent
    width:Math.min(960,parent ? parent.width-48 : 960)
    height:Math.min(720,parent ? parent.height-32 : 720)
    padding:18; standardButtons:Dialog.NoButton
    onOpened:{selected=[];if(service)service.refreshDownloads()}
    function toggle(key,checked) { let next=selected.slice();let index=next.indexOf(key);if(checked && index<0)next.push(key);if(!checked && index>=0)next.splice(index,1);selected=next }
    function selectVisible() { let next=selected.slice();for(let row of filtered)if((row.csvReady || row.canGenerate) && next.indexOf(row.id)<0)next.push(row.id);selected=next }
    onRowsChanged:{let ids=rows.map(row=>row.id);selected=selected.filter(key=>ids.indexOf(key)>=0)}
    contentItem:ColumnLayout {
        spacing:10
        GridLayout {
            columns:2; Layout.fillWidth:true; columnSpacing:10; rowSpacing:8
            Select { id:target; objectName:"savedDownloadsTarget"; Layout.fillWidth:true; model:["Todos los procedimientos"].concat(service ? service.uploadTargets.map(row=>row.label) : []); enabled:!dialog.working }
            RowLayout {
                Layout.fillWidth:true
                Select { id:month; objectName:"savedDownloadsMonth"; Layout.fillWidth:true; model:["Todos los meses","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]; enabled:!dialog.working }
                Field { id:year; objectName:"savedDownloadsYear"; Layout.preferredWidth:90; placeholderText:"Año"; maximumLength:4; enabled:!dialog.working }
            }
        }
        Field { id:search; objectName:"savedDownloadsSearch"; Layout.fillWidth:true; placeholderText:"Buscar descarga o archivo"; enabled:!dialog.working }
        RowLayout {
            Layout.fillWidth:true
            Text { text:dialog.filtered.length+" descargas · "+dialog.chosen.length+" seleccionadas"; color:Theme.muted; font.pixelSize:12; Layout.fillWidth:true }
            ActionButton { objectName:"selectVisibleDownloads"; text:"Seleccionar visibles"; enabled:!dialog.working; onClicked:dialog.selectVisible() }
            ActionButton { text:"Quitar selección"; enabled:!dialog.working; onClicked:dialog.selected=[] }
        }
        ListView {
            id:list; objectName:"savedDownloadsList"; Layout.fillWidth:true; Layout.fillHeight:true
            clip:true; spacing:4; model:dialog.filtered; ScrollBar.vertical:ScrollBar{}
            delegate:ItemDelegate {
                id:entry; required property var modelData
                objectName:"savedDownloadRow"; width:list.width; height:84
                enabled:!dialog.working && (modelData.csvReady || modelData.canGenerate)
                onClicked:dialog.toggle(modelData.id,dialog.selected.indexOf(modelData.id)<0)
                background:Rectangle { color:dialog.selected.indexOf(entry.modelData.id)>=0 ? Theme.accentTint : Theme.raised; radius:6 }
                contentItem:RowLayout {
                    spacing:8
                    CheckBox { objectName:"savedDownloadCheck"; checked:dialog.selected.indexOf(entry.modelData.id)>=0; onClicked:dialog.toggle(entry.modelData.id,checked) }
                    ColumnLayout {
                        Layout.fillWidth:true; spacing:3
                        Text { text:entry.modelData.procedure+" · "+entry.modelData.name+" · "+entry.modelData.periodLabel+(entry.modelData.mode ? " · "+({maritimo:"Marítimo",aereo:"Aéreo",terrestre:"Terrestre"})[entry.modelData.mode] : ""); textFormat:Text.PlainText; color:Theme.text; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideRight }
                        Text { text:entry.modelData.relativePath; textFormat:Text.PlainText; color:Theme.muted; font.pixelSize:10; Layout.fillWidth:true; elide:Text.ElideMiddle }
                        Text { text:entry.modelData.csvReady ? "CSV disponible" : entry.modelData.canGenerate ? "Generar CSV desde los resultados guardados" : "CSV no disponible"; color:entry.modelData.csvReady ? Theme.success : Theme.warning; font.pixelSize:11 }
                    }
                }
            }
            Label { anchors.centerIn:parent; visible:list.count===0; text:dialog.working ? "Leyendo descargas guardadas…" : "No hay descargas con estos filtros."; color:Theme.muted }
        }
        Text { text:service && service.destination.folderName ? "Destino: "+service.destination.folderName : "Conecta tu cuenta y elige la carpeta común de SharePoint."; color:Theme.muted; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
        Text { text:dialog.missing ? dialog.missing+" seleccionadas sin CSV. Puedes generarlos aquí antes de subir." : "Cada CSV se enviará a su ruta de procedimiento, mes y modalidad."; color:Theme.muted; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
        Text { visible:!!service && !!(service.error || service.downloadGenerationMessage || (service.downloadCatalog.errors || []).length); text:service ? service.error || service.downloadGenerationMessage || service.downloadCatalog.errors.join("\n") : ""; textFormat:Text.PlainText; color:Theme.warning; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
    }
    footer:Item {
        implicitHeight:66
        RowLayout {
            anchors.left:parent.left; anchors.right:parent.right; anchors.verticalCenter:parent.verticalCenter; anchors.margins:18; spacing:8
            ActionButton { objectName:"refreshSavedDownloads"; text:"Actualizar"; enabled:!dialog.working; onClicked:service.refreshDownloads() }
            ActionButton { objectName:"generateSelectedDownloads"; text:"Generar CSV seleccionados"; enabled:!dialog.working && dialog.chosen.some(row=>row.canGenerate); onClicked:service.generateDownloads(dialog.selected) }
            Item { Layout.fillWidth:true }
            ActionButton { text:"Cerrar"; onClicked:dialog.close() }
            ActionButton { objectName:"uploadSelectedDownloads"; text:"Subir seleccionados ("+dialog.chosen.length+")"; primary:true; enabled:!dialog.working && dialog.chosen.length>0 && dialog.missing===0 && !!service && service.connected && !!service.destination.folderId; onClicked:service.uploadDownloads(dialog.selected) }
        }
    }
}
