import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"

Item {
    id: page
    objectName: "batchRealPage"
    required property QtObject moduleBridge
    property bool isBls: moduleBridge.isBls
    property var flows: ["tabla","conocimientos","duas","movimientos","contenedores"]
    property var titles: ["Tabla de manifiestos","Conocimientos asociados","DUAs por manifiesto","Movimientos de manifiesto","Contenedores asociados"]
    property bool optionsVisible: false
    property int rowOffset: 0
    function localPath(url) { return decodeURIComponent(url.toString().replace(/^file:\/\/\//,"")) }
    function loadConfig() {
        const c = moduleBridge.config
        if (!c || c.year === undefined) return
        year.value = c.year; month.currentIndex = c.month - 1
        maritime.checked = c.modes.indexOf("maritimo") >= 0
        air.checked = c.modes.indexOf("aereo") >= 0
        land.checked = c.modes.indexOf("terrestre") >= 0
        tableName.text = c.name || ""
        threads.value = c.workers
        visibleBrowser.checked = !c.headless
        timeout.value = c.timeout
        output.text = c.outputRoot
        fromDate.text = c.start || ""; toDate.text = c.end || ""
        courier.currentIndex = ["todos","N","S"].indexOf(c.courier)
        manifestIds.text = c.manifestIds || ""; limit.value = c.limit || 0
        input.text = c.input || ""; sheet.text = c.sheet || "BLS"
        retries.value = c.max_retries || 3
        history.currentIndex = moduleBridge.history.findIndex(item => item.id === moduleBridge.activeId)
    }
    function configuration() {
        let modes = []
        if(maritime.checked) modes.push("maritimo")
        if(air.checked) modes.push("aereo")
        if(land.checked) modes.push("terrestre")
        return {year:year.value, month:month.currentIndex+1, modes:modes, name:tableName.text,
            workers:threads.value, headless:!visibleBrowser.checked, timeout:timeout.value,
            outputRoot:output.text, start:fromDate.text, end:toDate.text,
            courier:["todos","N","S"][courier.currentIndex], manifestIds:manifestIds.text,
            limit:limit.value, input:input.text, sheet:sheet.text, max_retries:retries.value}
    }
    Component.onCompleted: loadConfig()
    Connections {
        target: moduleBridge
        function onEventReceived(event) {
            if(event.flow === moduleBridge.flow && (event.event === "ready" ||
               (event.event === "result" && ["configure","refresh","select","import_progress"].indexOf(event.command) >= 0))) loadConfig()
        }
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Text { text: page.isBls ? "BLs" : "Manifiestos"; color:Theme.text; font.family:Theme.family; font.pixelSize:27; font.weight:Font.DemiBold; Layout.fillWidth:true }
            ActionButton { visible:!page.isBls; text:"Crear base para BLs"; onClicked:baseDialog.open() }
            ActionButton { text:"Más"; onClicked:more.open(); Menu {
                id:more
                MenuItem { text:page.optionsVisible ? "Ocultar configuración" : "Configuración"; onTriggered:page.optionsVisible=!page.optionsVisible }
                MenuItem { text:"Actualizar CSV"; enabled:!moduleBridge.busy && moduleBridge.activeId!==""; onTriggered:moduleBridge.command("export",{}) }
                MenuItem { text:"Pendientes y exclusiones"; enabled:!moduleBridge.busy && moduleBridge.activeId!==""; onTriggered:moduleBridge.command("review",{}) }
                MenuItem { text:"Importar progreso SQLite…"; visible:!page.isBls && ["conocimientos","duas","movimientos"].indexOf(moduleBridge.flow)>=0; enabled:!moduleBridge.busy; onTriggered:progressFile.open() }
                MenuItem { text:"Dividir CSV para Excel"; enabled:!moduleBridge.busy; onTriggered:splitFile.open() }
                MenuItem { text:"Reconectar"; enabled:!moduleBridge.busy; onTriggered:moduleBridge.connectModule() }
            } }
        }
        Panel {
            Layout.fillWidth:true
            implicitHeight:setup.implicitHeight+32
            ColumnLayout {
                id:setup
                anchors.fill:parent; anchors.margins:16; spacing:10
                RowLayout {
                    visible:!page.isBls
                    Layout.fillWidth:true
                    Select { id:procedure; objectName:"manifestProcedure"; Layout.fillWidth:true; model:page.titles; currentIndex:page.flows.indexOf(moduleBridge.flow); onActivated:{ moduleBridge.setFlow(page.flows[currentIndex]); Qt.callLater(page.loadConfig) } }
                    Select { id:month; Layout.preferredWidth:145; model:["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]; enabled:!moduleBridge.busy }
                    NumberField { id:year; from:2000; to:2100; value:2026; editable:true; enabled:!moduleBridge.busy; Layout.preferredWidth:115 }
                }
                RowLayout {
                    visible:!page.isBls
                    Choice { id:maritime; text:"Marítimo"; checked:true; enabled:!moduleBridge.busy; palette.windowText:Theme.text }
                    Choice { id:air; text:"Aéreo"; enabled:!moduleBridge.busy; palette.windowText:Theme.text }
                    Choice { id:land; text:"Terrestre"; enabled:!moduleBridge.busy; palette.windowText:Theme.text }
                    Item { Layout.fillWidth:true }
                    Text { visible:moduleBridge.flow==="contenedores"; text:"Contenedores llenos"; color:Theme.muted; font.pixelSize:12 }
                }
                RowLayout {
                    visible:page.isBls
                    Layout.fillWidth:true
                    Field { id:input; Layout.fillWidth:true; placeholderText:"Seleccione la base de BLs"; readOnly:true }
                    ActionButton { text:"Seleccionar base…"; enabled:!moduleBridge.busy; onClicked:inputFile.open() }
                    Field { id:sheet; text:"BLS"; Layout.preferredWidth:110; enabled:!moduleBridge.busy; placeholderText:"Hoja" }
                }
                RowLayout {
                    Layout.fillWidth:true
                    Field { id:tableName; objectName:"manifestTableName"; Layout.fillWidth:true; placeholderText:"Nombre de la tabla (opcional)"; enabled:!moduleBridge.busy }
                    ActionButton { text:moduleBridge.busy ? "En ejecución…" : "Iniciar consulta"; objectName:"manifestStart"; primary:true; enabled:moduleBridge.ready && !moduleBridge.busy; onClicked:moduleBridge.command("run",{config:page.configuration()}) }
                    ActionButton { text:"Detener"; enabled:moduleBridge.busy; onClicked:moduleBridge.stop() }
                }
            }
        }
        ScrollView {
            visible:page.optionsVisible
            Layout.fillWidth:true; Layout.preferredHeight:180; clip:true
            ColumnLayout {
                width:parent.width; spacing:8
                RowLayout {
                    Text { text:"Descargas simultáneas"; color:Theme.text }
                    NumberField { id:threads; from:1; to:page.isBls ? 20 : 32; value:4; editable:true; enabled:!moduleBridge.busy }
                    Choice { id:visibleBrowser; text:"Mostrar navegador"; checked:true; enabled:!moduleBridge.busy; palette.windowText:Theme.text }
                    Text { text:"Espera (segundos)"; color:Theme.text }
                    NumberField { id:timeout; from:5; to:3600; value:120; editable:true; enabled:!moduleBridge.busy }
                    Text { visible:page.isBls; text:"Intentos"; color:Theme.text }
                    NumberField { id:retries; visible:page.isBls; from:1; to:10; value:3; editable:true; enabled:!moduleBridge.busy }
                }
                RowLayout {
                    visible:!page.isBls; Layout.fillWidth:true
                    Field { id:fromDate; Layout.fillWidth:true; placeholderText:"Desde YYYY-MM-DD (opcional)"; enabled:!moduleBridge.busy }
                    Field { id:toDate; Layout.fillWidth:true; placeholderText:"Hasta YYYY-MM-DD (mismo mes)"; enabled:!moduleBridge.busy }
                    Select { id:courier; visible:moduleBridge.flow==="conocimientos"; model:["Todos los Courier","Courier N","Courier S"]; Layout.preferredWidth:165; enabled:!moduleBridge.busy }
                }
                RowLayout {
                    visible:!page.isBls; Layout.fillWidth:true
                    Field { id:manifestIds; Layout.fillWidth:true; placeholderText:"IDs de manifiesto separados por espacios (opcional)"; enabled:!moduleBridge.busy }
                    Text { text:"Límite (0 = todos)"; color:Theme.text }
                    NumberField { id:limit; from:0; to:100000; editable:true; enabled:!moduleBridge.busy }
                }
                RowLayout {
                    Layout.fillWidth:true
                    Field { id:output; Layout.fillWidth:true; placeholderText:"Carpeta de resultados"; readOnly:true }
                    ActionButton { text:"Elegir carpeta…"; enabled:!moduleBridge.busy; onClicked:outputFolder.open() }
                    ActionButton { text:"Guardar configuración"; enabled:!moduleBridge.busy; onClicked:moduleBridge.command("configure",{config:page.configuration()}) }
                }
            }
        }
        RowLayout {
            Layout.fillWidth:true
            Select { id:history; objectName:"manifestHistory"; Layout.fillWidth:true; model:moduleBridge.history; textRole:"label"; placeholder:"Ejecuciones guardadas"; enabled:!moduleBridge.busy; onActivated:moduleBridge.command("select",{id:moduleBridge.history[currentIndex].id}) }
            ActionButton { text:"Ver resultados"; enabled:moduleBridge.activeId!==""; onClicked:moduleBridge.openResults() }
        }
        RowLayout {
            Layout.fillWidth:true
            Text { text:moduleBridge.summary.succeeded+" guardados   ·   "+moduleBridge.summary.pending+" pendientes   ·   "+moduleBridge.summary.running+" en curso"+(moduleBridge.summary.excluded ? "   ·   "+moduleBridge.summary.excluded+" excluidos" : "")+"   ·   "+moduleBridge.summary.rows+" filas"; color:Theme.muted; font.pixelSize:12; Layout.fillWidth:true }
            Field { id:search; placeholderText:"Buscar manifiesto"; Layout.preferredWidth:170; enabled:!moduleBridge.busy; onAccepted:{page.rowOffset=0; moduleBridge.command("view",{search:text,offset:0})} }
        }
        Panel {
            Layout.fillWidth:true; Layout.fillHeight:true; Layout.minimumHeight:90; clip:true
            ColumnLayout {
                anchors.fill:parent; anchors.margins:12; spacing:8
                RowLayout {
                    Layout.fillWidth:true
                    Text { text:"Manifiesto / BL"; color:Theme.faint; Layout.fillWidth:true }
                    Text { text:"Estado"; color:Theme.faint; Layout.preferredWidth:105 }
                    Text { text:"Intentos"; color:Theme.faint; Layout.preferredWidth:55 }
                    Text { text:"Filas"; color:Theme.faint; Layout.preferredWidth:60 }
                }
                ListView {
                    id:jobsList
                    objectName:"manifestJobs"
                    Layout.fillWidth:true; Layout.fillHeight:true; clip:true; spacing:2
                    model:moduleBridge.jobs
                    ScrollBar.vertical:ScrollBar {}
                    delegate:Item {
                        required property var modelData
                        width:jobsList.width; height:modelData.error ? 58 : 34
                        ColumnLayout {
                            anchors.fill:parent; spacing:2
                            RowLayout {
                                Layout.fillWidth:true
                                Text { text:modelData.id; color:Theme.text; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideMiddle; ToolTip.visible:hover.hovered; ToolTip.text:modelData.id; HoverHandler{id:hover} }
                                Text { text:modelData.state; color:modelData.state==="Guardado" ? Theme.success : Theme.muted; Layout.preferredWidth:105; font.pixelSize:12 }
                                Text { text:modelData.attempts; color:Theme.muted; Layout.preferredWidth:55; font.pixelSize:12 }
                                Text { text:modelData.rows; color:Theme.muted; Layout.preferredWidth:60; font.pixelSize:12 }
                            }
                            Text { visible:modelData.error!==""; text:modelData.error; color:"#db9d80"; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideRight; ToolTip.visible:errorHover.hovered; ToolTip.text:modelData.error; HoverHandler{id:errorHover} }
                        }
                    }
                    Text { anchors.centerIn:parent; visible:jobsList.count===0; text:moduleBridge.busy ? "Preparando la consulta…" : "Elija el período y pulse Iniciar consulta."; color:Theme.faint; font.pixelSize:13 }
                }
            }
        }
        RowLayout {
            Layout.fillWidth:true
            Text { text:moduleBridge.error || moduleBridge.status; color:moduleBridge.error ? "#ee9d91" : Theme.muted; Layout.fillWidth:true; elide:Text.ElideRight; ToolTip.visible:statusHover.hovered; ToolTip.text:text; HoverHandler{id:statusHover} }
            ActionButton { text:"Anterior"; enabled:!moduleBridge.busy && page.rowOffset>0; onClicked:{page.rowOffset=Math.max(0,page.rowOffset-200); moduleBridge.command("view",{search:search.text,offset:page.rowOffset})} }
            ActionButton { text:"Siguiente"; enabled:!moduleBridge.busy && moduleBridge.jobs.length>=200; onClicked:{page.rowOffset+=200; moduleBridge.command("view",{search:search.text,offset:page.rowOffset})} }
        }
    }
    FileDialog { id:inputFile; title:"Base de BLs"; nameFilters:["Bases BLs (*.xlsx *.sqlite3 *.sqlite *.db)"]; onAccepted:input.text=page.localPath(selectedFile) }
    FileDialog { id:splitFile; title:"Dividir un CSV para Excel"; nameFilters:["CSV (*.csv)"]; onAccepted:moduleBridge.command("split",{source:page.localPath(selectedFile)}) }
    FileDialog { id:progressFile; title:"Importar una copia del progreso original"; nameFilters:["Progreso SQLite (*.sqlite3 *.sqlite *.db)"]; onAccepted:moduleBridge.command("import_progress",{source:page.localPath(selectedFile)}) }
    FolderDialog { id:outputFolder; title:"Carpeta de resultados"; onAccepted:output.text=page.localPath(selectedFolder) }
    ManifiestosBaseDialog { id:baseDialog; moduleBridge:page.moduleBridge }
}
