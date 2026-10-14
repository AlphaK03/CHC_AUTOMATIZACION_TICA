import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

Dialog {
    id: dialog
    property var service: null
    property string driveId: ""
    property var ancestors: []
    title: "Cuenta y carpetas SharePoint"
    modal: true
    width: Math.min(840, parent ? parent.width - 60 : 840)
    height: Math.min(710, parent ? parent.height - 50 : 710)
    anchors.centerIn: parent
    padding: 22
    standardButtons: Dialog.Close
    palette.windowText: Theme.text
    palette.buttonText: Theme.text
    palette.button: Theme.raised
    background: Panel {}
    onOpened: { if(service) service.refresh() }
    contentItem: ScrollView {
        clip: true
        ColumnLayout {
            width: dialog.availableWidth
            spacing: 14
            Text { text: service && service.connected ? service.account : "Sin cuenta conectada"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth:true }
            Text { text: "Los bots funcionan sin cuenta. Conecta CHC para guardar también una copia de los CSV en SharePoint."; color: Theme.muted; font.pixelSize:12; wrapMode:Text.WordWrap; Layout.fillWidth:true }
            RowLayout {
                ActionButton { objectName:"connectSharePoint"; text: service && service.connected ? "Cambiar cuenta" : "Conectar cuenta CHC"; primary:true; enabled: !!service && service.enabled && !service.busy; onClicked: service.connectAccount() }
                ActionButton { text:"Desconectar"; visible:!!service && service.connected; enabled:!!service && !service.busy; onClicked:service.disconnectAccount() }
                Item { Layout.fillWidth:true }
                BusyIndicator { running:!!service && service.busy; visible:running; Layout.preferredWidth:28; Layout.preferredHeight:28 }
            }
            Text { text: service ? service.error || service.status : "Conexión desactivada en demostración."; color: service && service.error ? Theme.accent : Theme.muted; wrapMode:Text.WordWrap; Layout.fillWidth:true; font.pixelSize:11 }
            Rectangle { Layout.fillWidth:true; height:1; color:Theme.border }
            Text { text:"Carpetas de resultados"; color:Theme.text; font.pixelSize:14; font.weight:Font.DemiBold }
            Repeater {
                model:service ? service.destinations : []
                RowLayout {
                    required property var modelData
                    Layout.fillWidth:true
                    Text { text:modelData.label; color:Theme.text; Layout.preferredWidth:175; font.pixelSize:12 }
                    Text { text:modelData.webUrl || "Solo local"; color:Theme.muted; font.pixelSize:11; elide:Text.ElideMiddle; Layout.fillWidth:true; ToolTip.visible:routeHover.hovered; ToolTip.text:modelData.webUrl || ""; HoverHandler { id:routeHover } }
                    ActionButton { text:"Quitar"; visible:!!modelData.folderId; enabled:!!service && !service.busy; onClicked:service.removeDestination(modelData.key) }
                }
            }
            ColumnLayout {
                visible:!!service && service.connected
                Layout.fillWidth:true
                spacing:10
                Text { text:"Agregar o cambiar carpeta"; color:Theme.text; font.pixelSize:13; font.weight:Font.DemiBold }
                ComboBox { id:targetBox; objectName:"sharePointTarget"; Layout.fillWidth:true; model:service ? service.destinations : []; textRole:"label" }
                RowLayout {
                    Layout.fillWidth:true
                    TextField { id:siteUrl; objectName:"sharePointSiteUrl"; Layout.fillWidth:true; placeholderText:"URL del sitio SharePoint de CHC"; selectByMouse:true; color:Theme.text; background:Rectangle { color:Theme.surface; radius:6; border.color:Theme.border } }
                    ActionButton { text:"Ver bibliotecas"; enabled:!!service && !service.busy && siteUrl.text.length>0; onClicked:{ dialog.driveId=""; dialog.ancestors=[]; service.openSite(siteUrl.text) } }
                }
                Text { text:"El sitio debe estar autorizado para esta app y tu cuenta debe tener acceso. Puedes configurar las rutas más adelante."; color:Theme.faint; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                Repeater {
                    model:service && service.browse.drives ? service.browse.drives : []
                    ActionButton { required property var modelData; text:"Biblioteca · " + modelData.name; enabled:!!service && !service.busy; onClicked:{ dialog.driveId=modelData.id; dialog.ancestors=[]; service.openFolder(modelData.id,"root") } }
                }
                RowLayout {
                    visible:dialog.driveId.length>0 && !!service && !!service.browse.folder
                    Layout.fillWidth:true
                    ActionButton { text:"Subir"; enabled:dialog.ancestors.length>0 && !!service && !service.busy; onClicked:{ let stack=dialog.ancestors.slice(); let parentId=stack.pop(); dialog.ancestors=stack; service.openFolder(dialog.driveId,parentId) } }
                    Text { text:service && service.browse.folder ? service.browse.folder.name : ""; color:Theme.text; font.pixelSize:12; Layout.fillWidth:true }
                    ActionButton { objectName:"saveSharePointFolder"; text:"Usar esta carpeta"; primary:true; enabled:!!service && !service.busy && service.browse.driveId===dialog.driveId && targetBox.currentIndex>=0; onClicked:service.saveDestination(service.destinations[targetBox.currentIndex].key,dialog.driveId,service.browse.folder.id) }
                }
                Repeater {
                    model:service && service.browse.driveId===dialog.driveId ? service.browse.folders || [] : []
                    ActionButton { required property var modelData; text:"Carpeta · " + modelData.name; enabled:!!service && !service.busy; onClicked:{ dialog.ancestors=dialog.ancestors.concat([service.browse.folder.id]); service.openFolder(dialog.driveId,modelData.id) } }
                }
            }
            Rectangle { Layout.fillWidth:true; height:1; color:Theme.border }
            RowLayout {
                Text { text:"Publicaciones · " + (service ? service.pending : 0) + " pendientes"; color:Theme.text; Layout.fillWidth:true; font.pixelSize:13 }
                ActionButton { text:"Reintentar envíos"; enabled:!!service && service.connected && !service.busy && service.pending>0; onClicked:service.retry() }
            }
            Text { text:"Se copia el CSV dentro de una carpeta con el nombre del lote. Las subidas fallidas conservan el archivo local y no vuelven a consultar TICA."; color:Theme.faint; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
            Repeater {
                model:service ? service.tasks : []
                Text { required property var modelData; text:modelData.name + " / " + modelData.filename + " · " + ({pending:"Pendiente",uploading:"Subiendo",synced:"En SharePoint",error:"Por reintentar",paused:"Destino retirado"})[modelData.state] + (modelData.error ? "\n" + modelData.error : ""); color:modelData.state==="synced" ? Theme.success : Theme.muted; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
            }
        }
    }
}
