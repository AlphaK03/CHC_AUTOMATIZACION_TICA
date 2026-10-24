import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

AppDialog {
    id:dialog
    parent:Overlay.overlay
    objectName:"blsKnowledgeDialog"
    required property QtObject moduleBridge
    property var selectedPeriods:[]
    signal periodsSelected(var periods)
    title:"Conocimientos disponibles para BLs"
    modal:true
    anchors.centerIn:parent
    width:Math.min(680,parent.width-30)
    height:Math.min(500,parent.height-30)
    padding:20
    palette.windowText:Theme.text; palette.buttonText:Theme.text; palette.button:Theme.raised
    background:Panel {}
    onOpened:moduleBridge.refreshKnowledge()
    contentItem:ColumnLayout {
        spacing:12
        RowLayout {
            Layout.fillWidth:true
            Text { text:"Seleccione meses y modalidades."; color:Theme.muted; Layout.fillWidth:true }
            ActionButton { text:"Actualizar"; enabled:!moduleBridge.knowledgeBusy; onClicked:moduleBridge.refreshKnowledge() }
        }
        ListView {
            id:periods
            Layout.fillWidth:true; Layout.fillHeight:true; clip:true; spacing:4
            model:moduleBridge.knowledgeCatalog.periods || []
            ScrollBar.vertical:ScrollBar {}
            delegate:Choice {
                required property var modelData
                objectName:"knowledgeChoice_"+modelData.key
                width:periods.width; implicitHeight:48
                text:modelData.label+"  ·  "+modelData.coverage
                checked:dialog.selectedPeriods.indexOf(modelData.key)>=0
                enabled:!moduleBridge.knowledgeBusy
                onClicked:dialog.selectedPeriods=checked ? dialog.selectedPeriods.concat([modelData.key]) : dialog.selectedPeriods.filter(k=>k!==modelData.key)
            }
            Text {
                anchors.centerIn:parent; width:parent.width-30; horizontalAlignment:Text.AlignHCenter
                visible:periods.count===0; wrapMode:Text.WordWrap
                text:moduleBridge.knowledgeBusy ? "Buscando descargas terminadas…" : moduleBridge.knowledgeCatalog.message || "No hay descargas completas de Conocimientos disponibles."
                color:Theme.muted
            }
        }
        Text { text:"Solo se ofrecen descargas terminadas. La base se generará automáticamente con Courier N."; color:Theme.faint; font.pixelSize:12; Layout.fillWidth:true; wrapMode:Text.WordWrap }
        RowLayout {
            Layout.fillWidth:true
            ActionButton { text:"Todos"; enabled:!moduleBridge.knowledgeBusy && periods.count>0; onClicked:dialog.selectedPeriods=moduleBridge.knowledgeCatalog.periods.map(p=>p.key) }
            ActionButton { text:"Ninguno"; enabled:!moduleBridge.knowledgeBusy; onClicked:dialog.selectedPeriods=[] }
            ActionButton { text:"Ir a Conocimientos"; visible:periods.count===0 && !moduleBridge.knowledgeBusy; onClicked:{manifests.setFlow("conocimientos"); demo.navigate("manifiestos"); dialog.close()} }
            Item { Layout.fillWidth:true }
            ActionButton { objectName:"blsKnowledgeAccept"; text:"Usar selección"; primary:true; enabled:!moduleBridge.knowledgeBusy && dialog.selectedPeriods.some(k=>moduleBridge.knowledgeCatalog.periods.some(p=>p.key===k)); onClicked:{dialog.periodsSelected(dialog.selectedPeriods.filter(k=>moduleBridge.knowledgeCatalog.periods.some(p=>p.key===k))); dialog.close()} }
            ActionButton { text:"Cerrar"; onClicked:dialog.close() }
        }
    }
}
