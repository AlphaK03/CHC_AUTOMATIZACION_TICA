import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"

AppDialog {
    id:dialog
    parent:Overlay.overlay
    objectName:"manifestBaseDialog"
    required property QtObject moduleBridge
    property var chosenPeriods: []
    property var chosenSources: []
    property var externalPaths: []
    property bool loaded: false
    property string builtPath: ""
    title:"Crear base para BLs"
    modal:true
    anchors.centerIn:parent
    width:Math.min(850,parent.width-30)
    height:Math.min(720,parent.height-30)
    padding:20
    palette.windowText:Theme.text; palette.buttonText:Theme.text; palette.button:Theme.raised
    background:Panel {}
    function pathOf(url) { return decodeURIComponent(url.toString().replace(/^file:\/\/\//,"")) }
    function change(values,key,checked) { return checked ? values.concat([key]) : values.filter(v=>v!==key) }
    function invalidate() { loaded=false; builtPath="" }
    onOpened: { dialog.invalidate(); baseYear.value=moduleBridge.config.year||2026; baseMonth.currentIndex=moduleBridge.config.month||0; destination.text=moduleBridge.defaultBaseFolder+"/Base_BLs.sqlite3"; dialog.builtPath=moduleBridge.lastBase }
    Connections {
        target:moduleBridge
        function onEventReceived(event) {
            if(event.flow!=="bases") return
            if(event.event==="result" && event.command==="base_load") {
                dialog.loaded=true
                dialog.chosenPeriods=(moduleBridge.baseInfo.periods||[]).filter(p=>p.rows>0).map(p=>p.key)
                dialog.chosenSources=(moduleBridge.baseInfo.sources||[]).filter(s=>s.rows>0).map(s=>s.path+"|"+s.sheet)
            }
            if(event.baseResult) dialog.builtPath=event.baseResult.output
        }
    }
    contentItem:ColumnLayout {
        spacing:10
        RowLayout {
            Layout.fillWidth:true
            NumberField { id:baseYear; from:0; to:2100; value:2026; editable:true; enabled:!moduleBridge.baseBusy; ToolTip.visible:hovered; ToolTip.text:"0 = todos los años"; onValueModified:dialog.invalidate() }
            Select { id:baseMonth; Layout.fillWidth:true; model:["Todos los meses","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]; enabled:!moduleBridge.baseBusy; onActivated:dialog.invalidate() }
            Select { id:baseMode; Layout.preferredWidth:145; model:["Todas","Marítimo","Aéreo","Terrestre"]; enabled:!moduleBridge.baseBusy; onActivated:dialog.invalidate() }
            ActionButton { objectName:"baseLoad"; text:"Cargar datos"; enabled:!moduleBridge.baseBusy; onClicked:{dialog.invalidate(); moduleBridge.baseCommand("base_load",{year:baseYear.value,month:baseMonth.currentIndex,mode:["","maritimo","aereo","terrestre"][baseMode.currentIndex],kind:["preferred","CSV","all"][kind.currentIndex],includeHistory:historical.checked,external:dialog.externalPaths})} }
        }
        TabBar { id:tabs; Layout.fillWidth:true; TabButton {text:"Meses"} TabButton {text:"Archivos y opciones"} }
        StackLayout {
            currentIndex:tabs.currentIndex; Layout.fillWidth:true; Layout.fillHeight:true
            ColumnLayout {
                RowLayout {
                    ActionButton { text:"Todos"; enabled:dialog.loaded; onClicked:dialog.chosenPeriods=(moduleBridge.baseInfo.periods||[]).filter(p=>p.rows>0).map(p=>p.key) }
                    ActionButton { text:"Ninguno"; enabled:dialog.loaded; onClicked:dialog.chosenPeriods=[] }
                    Item { Layout.fillWidth:true }
                    Text { text:"Año 0 = todos"; color:Theme.faint; font.pixelSize:11 }
                }
                ListView {
                    id:periodList; Layout.fillWidth:true; Layout.fillHeight:true; clip:true
                    model:moduleBridge.baseInfo.periods||[]
                    ScrollBar.vertical:ScrollBar {}
                    delegate:Choice {
                        required property var modelData
                        width:periodList.width
                        text:modelData.period+" · "+modelData.mode+" · "+modelData.rows+" filas"+(modelData.pending ? " · "+modelData.pending+" pendientes" : "")
                        checked:dialog.chosenPeriods.indexOf(modelData.key)>=0
                        enabled:dialog.loaded && modelData.rows>0 && !moduleBridge.baseBusy
                        palette.windowText:Theme.text
                        onClicked:dialog.chosenPeriods=dialog.change(dialog.chosenPeriods,modelData.key,checked)
                    }
                    Text { visible:periodList.count===0; anchors.centerIn:parent; text:"Elija el período y pulse Cargar datos."; color:Theme.muted }
                }
            }
            ColumnLayout {
                RowLayout {
                    Select { id:kind; model:["Preferir SQLite","Solo CSV","Todos los formatos"]; enabled:!moduleBridge.baseBusy; Layout.fillWidth:true; onActivated:dialog.invalidate() }
                    Choice { id:historical; text:"Incluir históricos"; enabled:!moduleBridge.baseBusy; palette.windowText:Theme.text; onClicked:dialog.invalidate() }
                }
                RowLayout {
                    ActionButton { text:"Añadir archivos…"; enabled:!moduleBridge.baseBusy; onClicked:externalFiles.open() }
                    ActionButton { text:"Añadir carpeta…"; enabled:!moduleBridge.baseBusy; onClicked:externalFolder.open() }
                    ActionButton { text:"Quitar externos"; enabled:!moduleBridge.baseBusy; onClicked:{dialog.externalPaths=[]; dialog.invalidate()} }
                }
                Text { text:dialog.externalPaths.length ? dialog.externalPaths.length+" entradas externas añadidas" : "Origen: datos de este Workbench"; color:Theme.muted }
                ListView {
                    id:sourceList; Layout.fillWidth:true; Layout.fillHeight:true; clip:true
                    model:moduleBridge.baseInfo.sources||[]; ScrollBar.vertical:ScrollBar {}
                    delegate:Choice {
                        required property var modelData
                        width:sourceList.width
                        text:modelData.path.split(/[\\/]/).pop()+" · "+modelData.kind+(modelData.sheet ? " · "+modelData.sheet : "")+" · "+modelData.rows+" filas"
                        checked:dialog.chosenSources.indexOf(modelData.path+"|"+modelData.sheet)>=0
                        enabled:dialog.loaded && !moduleBridge.baseBusy
                        palette.windowText:Theme.text
                        ToolTip.visible:hovered; ToolTip.text:modelData.path
                        onClicked:dialog.chosenSources=dialog.change(dialog.chosenSources,modelData.path+"|"+modelData.sheet,checked)
                    }
                }
            }
        }
        Text { text:moduleBridge.baseError || moduleBridge.baseInfo.message || "Solo Courier N; se conservan los ceros iniciales."; color:moduleBridge.baseError ? "#ee9d91" : Theme.muted; Layout.fillWidth:true; wrapMode:Text.WordWrap; font.pixelSize:12 }
        RowLayout {
            Layout.fillWidth:true
            Select { id:format; model:["SQLite","Excel"]; enabled:!moduleBridge.baseBusy; onActivated:{destination.text=destination.text.replace(/\.(sqlite3|sqlite|db|xlsx)$/i,currentIndex===0 ? ".sqlite3" : ".xlsx"); dialog.builtPath=""} }
            Field { id:destination; Layout.fillWidth:true; enabled:!moduleBridge.baseBusy; placeholderText:"Archivo de salida" }
            ActionButton { text:"Guardar en…"; enabled:!moduleBridge.baseBusy; onClicked:saveFile.open() }
        }
        Choice { id:replace; text:"Sustituir el archivo si ya existe"; enabled:!moduleBridge.baseBusy; palette.windowText:Theme.text }
        RowLayout {
            Layout.fillWidth:true
            ActionButton { objectName:"baseBuild"; text:"Generar base"; primary:true; enabled:dialog.loaded && dialog.chosenPeriods.length>0 && dialog.chosenSources.length>0 && !moduleBridge.baseBusy; onClicked:moduleBridge.baseCommand("base_build",{periods:dialog.chosenPeriods,sources:dialog.chosenSources,destination:destination.text,replace:replace.checked}) }
            ActionButton { text:"Detener"; enabled:moduleBridge.baseBusy; onClicked:moduleBridge.stopBase() }
            ActionButton { objectName:"baseTransfer"; text:"Abrir base en BLs"; enabled:dialog.builtPath!=="" && !moduleBridge.baseBusy; onClicked:{ bls.useBase(dialog.builtPath); demo.navigate("bls"); dialog.close() } }
            Item { Layout.fillWidth:true }
            ActionButton { text:"Cerrar"; onClicked:dialog.close() }
        }
    }
    FileDialog { id:externalFiles; title:"Fuentes de Conocimientos"; fileMode:FileDialog.OpenFiles; nameFilters:["Datos (*.csv *.xlsx *.sqlite3 *.sqlite *.db)"]; onAccepted:{dialog.externalPaths=dialog.externalPaths.concat(selectedFiles.map(f=>dialog.pathOf(f))); dialog.invalidate()} }
    FolderDialog { id:externalFolder; onAccepted:{dialog.externalPaths=dialog.externalPaths.concat([dialog.pathOf(selectedFolder)]); dialog.invalidate()} }
    FileDialog { id:saveFile; title:"Guardar base para BLs"; fileMode:FileDialog.SaveFile; nameFilters:format.currentIndex===0 ? ["SQLite (*.sqlite3)"] : ["Excel (*.xlsx)"]; defaultSuffix:format.currentIndex===0 ? "sqlite3" : "xlsx"; onAccepted:destination.text=dialog.pathOf(selectedFile) }
}
