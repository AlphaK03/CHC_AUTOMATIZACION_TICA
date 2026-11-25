import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as Native
import "components"

AppDialog {
    id:dialog
    objectName:"manualUploadDialog"
    property var service:null
    property var file:service ? service.manualUpload : ({})
    property string lastToken:""
    property string chosenTarget:""
    property string chosenMode:""
    property var modeCodes:chosenTarget==="manifiestos:contenedores" ? ["maritimo"] : chosenTarget==="bls" ? ["maritimo","aereo"] : chosenTarget.startsWith("manifiestos:") ? ["maritimo","aereo","terrestre"] : [""]
    property bool matches:file.reviewed===true && !file.destinationChanged && chosenTarget===file.target && selectedPeriod()===(file.period || "") && selectedMode()===(file.mode || "")
    onFileChanged:Qt.callLater(syncFile)
    title:"Subir un CSV individual"; modal:true
    width:Math.min(640,parent ? parent.width-48 : 640)
    height:Math.min(580,parent ? parent.height-32 : 580)
    anchors.centerIn:parent; padding:20; standardButtons:Dialog.NoButton
    function chooseFile() { csvPicker.open() }
    function targetIndex(value) {
        if(service) for(let i=0;i<service.uploadTargets.length;i++) if(service.uploadTargets[i].id===value)return i
        return -1
    }
    function selectedPeriod() { return month.currentIndex>0 ? String(year.value)+"-"+String(month.currentIndex).padStart(2,"0") : "" }
    function selectedMode() { return modeCodes.indexOf(chosenMode)>=0 ? chosenMode : modeCodes[0] }
    function syncFile() {
        if(!file.token) { if(visible) close();lastToken="";return }
        if(lastToken===file.token)return
        lastToken=file.token;chosenTarget=file.target || "";chosenMode=file.mode || ""
        year.value=file.period ? Number(file.period.slice(0,4)) : new Date().getFullYear()
        month.currentIndex=file.period ? Number(file.period.slice(5,7)) : 0
        if(!visible)open()
    }
    Connections { target:dialog.service; function onChanged(){dialog.syncFile()} }
    contentItem:ScrollView {
        id:manualScroll
        clip:true; contentWidth:availableWidth
        ColumnLayout {
            width:manualScroll.availableWidth; spacing:12
            Text { text:dialog.file.name || ""; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:14; font.weight:Font.DemiBold; Layout.fillWidth:true; wrapMode:Text.WrapAnywhere }
            Text { text:dialog.file.path || ""; textFormat:Text.PlainText; color:Theme.faint; font.pixelSize:10; Layout.fillWidth:true; wrapMode:Text.WrapAnywhere }
            GridLayout {
                columns:2; Layout.fillWidth:true; columnSpacing:12; rowSpacing:10
                Text { text:"Procedimiento:"; color:Theme.text; font.pixelSize:12 }
                Select { objectName:"manualUploadTarget"; Layout.fillWidth:true; model:service ? service.uploadTargets : []; textRole:"label"; placeholder:"Selecciona el procedimiento"; currentIndex:dialog.targetIndex(dialog.chosenTarget); enabled:!dialog.file.registered && !!service && !service.busy; onActivated:dialog.chosenTarget=service.uploadTargets[currentIndex].id }
                Text { text:"Mes:"; color:Theme.text; font.pixelSize:12 }
                RowLayout {
                    Layout.fillWidth:true
                    Select { id:month; objectName:"manualUploadMonth"; Layout.fillWidth:true; model:["Selecciona mes","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]; enabled:!dialog.file.registered && !!service && !service.busy }
                    SpinBox { id:year; objectName:"manualUploadYear"; from:2000; to:2099; textFromValue:function(value,locale){return String(value)}; enabled:!dialog.file.registered && !!service && !service.busy; palette.text:Theme.text; palette.base:Theme.raised; palette.button:Theme.raised; palette.buttonText:Theme.text }
                }
                Text { visible:dialog.modeCodes[0]!==""; text:"Modalidad:"; color:Theme.text; font.pixelSize:12 }
                Select { objectName:"manualUploadMode"; visible:dialog.modeCodes[0]!==""; Layout.fillWidth:true; model:dialog.modeCodes.map(value=>({maritimo:"Marítimo",aereo:"Aéreo",terrestre:"Terrestre"})[value] || ""); currentIndex:Math.max(0,dialog.modeCodes.indexOf(dialog.chosenMode)); enabled:!dialog.file.registered && dialog.modeCodes.length>1 && !!service && !service.busy; onActivated:dialog.chosenMode=dialog.modeCodes[currentIndex] }
            }
            Text { text:"Destino: "+(service ? service.destination.folderName || "Selecciona la carpeta común de SharePoint" : ""); textFormat:Text.PlainText; color:Theme.muted; font.pixelSize:12; Layout.fillWidth:true; wrapMode:Text.WordWrap }
            Text { objectName:"manualUploadPreview"; text:dialog.matches ? dialog.file.relativePath || "" : "Revisa el destino después de elegir el procedimiento y el mes."; textFormat:Text.PlainText; color:Theme.muted; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WrapAnywhere }
            Text { text:"Solo se enviará este CSV. Esta acción no marca el mes como completado."; color:Theme.faint; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
            Text { visible:!!service && service.error!==""; text:service ? service.error : ""; textFormat:Text.PlainText; color:Theme.warning; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
        }
    }
    footer:Item {
        implicitHeight:64
        RowLayout {
            anchors.right:parent.right; anchors.left:parent.left; anchors.margins:20; anchors.verticalCenter:parent.verticalCenter; spacing:8
            ActionButton { text:"Cambiar CSV…"; enabled:!!service && !service.busy; onClicked:dialog.chooseFile() }
            Item { Layout.fillWidth:true }
            ActionButton { text:"Cerrar"; onClicked:dialog.close() }
            ActionButton {
                objectName:"manualUploadSubmit"; text:dialog.matches ? "Subir este CSV" : "Revisar destino"; primary:true
                enabled:!!service && service.connected && !!service.destination.folderId && !service.busy && !!dialog.chosenTarget && (!!dialog.selectedPeriod() || dialog.file.registered)
                onClicked: {
                    if(dialog.matches)service.uploadFile(dialog.file.token)
                    else service.reviewUpload(dialog.file.token,dialog.chosenTarget,dialog.selectedPeriod(),dialog.selectedMode())
                }
            }
        }
    }
    Native.FileDialog {
        id:csvPicker; title:"Elegir CSV de resultados"; nameFilters:["CSV (*.csv *.CSV)"]; fileMode:Native.FileDialog.OpenFile
        onAccepted:if(dialog.service)dialog.service.inspectUpload(selectedFile.toString())
    }
}
