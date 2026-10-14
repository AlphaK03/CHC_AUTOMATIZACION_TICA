import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"

ScrollView {
    id: page
    objectName: "batchRealPage"
    required property QtObject moduleBridge
    property bool isBls: moduleBridge.isBls
    property var flows: ["tabla","conocimientos","duas","movimientos","contenedores"]
    property var titles: ["Tabla de manifiestos","Conocimientos asociados","DUAs por manifiesto","Movimientos de manifiesto","Contenedores asociados"]
    property var navLabels: ["Manifiestos","Conocimientos","DUAs","Movimientos","Contenedores"]
    property var navIcons: ["ship","document","route","activity","database"]
    property var navWidths: [116,160,88,134,148]
    property bool optionsVisible: false
    property int rowOffset: 0
    property var selectedKnowledge:[]
    property var availableKnowledge:moduleBridge.knowledgeCatalog.periods || []
    property bool knowledgeSelectionReady:selectedKnowledge.length>0 && selectedKnowledge.every(k=>availableKnowledge.some(p=>p.key===k))
    property bool resumesBls: page.isBls && moduleBridge.activeId!=="" &&
        tableName.text===(moduleBridge.config.name || "") && output.text===moduleBridge.config.outputRoot &&
        sheet.text===moduleBridge.config.sheet && (inputMode.currentIndex===0 ?
            moduleBridge.config.inputMode==="knowledge" && JSON.stringify(page.selectedKnowledge.slice().sort())===JSON.stringify((moduleBridge.config.knowledgePeriods || []).slice().sort()) :
            moduleBridge.config.inputMode==="file" && input.text===moduleBridge.config.input)
    contentWidth: availableWidth
    contentHeight: contentColumn.height
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    function knowledgeLabel() {
        if(availableKnowledge.length===0) return moduleBridge.knowledgeBusy ? "Buscando descargas completas…" : "Aún no hay descargas completas de Conocimientos"
        let chosen=availableKnowledge.filter(p=>selectedKnowledge.indexOf(p.key)>=0)
        return chosen.length===1 ? chosen[0].label : chosen.length ? chosen.length+" períodos seleccionados" : "Seleccione los meses y modalidades descargados"
    }
    function localPath(url) { return decodeURIComponent(url.toString().replace(/^file:\/\/\//,"")) }
    function automaticName() {
        let modes = []
        if (maritime.checked) modes.push("maritimo")
        if (air.checked) modes.push("aereo")
        if (land.checked) modes.push("terrestre")
        return moduleBridge.automaticTableName({flow:moduleBridge.flow, year:year.value, month:month.currentIndex+1,
            modes:modes, start:fromDate.text, end:toDate.text,
            courier:["todos","N","S"][courier.currentIndex] || "todos",
            manifestIds:manifestIds.text, limit:limit.value})
    }
    function selectProcedure(flow) {
        if (flow === moduleBridge.flow) return
        page.rowOffset = 0
        search.text = ""
        moduleBridge.setFlow(flow)
        Qt.callLater(page.loadConfig)
    }
    function loadConfig() {
        const c = moduleBridge.config
        if (!c || c.year === undefined) return
        year.value = c.year; month.currentIndex = c.month - 1
        maritime.checked = c.modes.indexOf("maritimo") >= 0
        air.checked = c.modes.indexOf("aereo") >= 0
        land.checked = c.modes.indexOf("terrestre") >= 0
        if (page.isBls) tableName.text = c.name || ""
        threads.value = c.workers
        visibleBrowser.checked = !c.headless
        timeout.value = c.timeout
        output.text = c.outputRoot
        fromDate.text = c.start || ""; toDate.text = c.end || ""
        courier.currentIndex = ["todos","N","S"].indexOf(c.courier)
        manifestIds.text = c.manifestIds || ""; limit.value = c.limit || 0
        input.text = c.input || ""; sheet.text = c.sheet || "BLS"
        retries.value = c.max_retries || 3
        inputMode.currentIndex=c.inputMode==="file" ? 1 : 0
        page.selectedKnowledge=c.knowledgePeriods || []
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
            limit:limit.value, input:input.text, sheet:sheet.text, max_retries:retries.value,
            inputMode:inputMode.currentIndex===0 ? "knowledge" : "file", knowledgePeriods:page.selectedKnowledge}
    }
    Component.onCompleted: loadConfig()
    Connections {
        target: moduleBridge
        function onEventReceived(event) {
            if(event.flow === moduleBridge.flow && (event.event === "ready" ||
               (event.event === "result" && ["configure","refresh","select","import_progress","run","knowledge_empty"].indexOf(event.command) >= 0))) loadConfig()
        }
    }
    ColumnLayout {
        id: contentColumn
        width: page.availableWidth
        height: Math.max(page.availableHeight, implicitHeight)
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Text { text: page.isBls ? "BLs" : "Manifiestos"; color:Theme.text; font.family:Theme.family; font.pixelSize:27; font.weight:Font.DemiBold; Layout.fillWidth:true }
            ActionButton { visible:!page.isBls; text:"Crear base para BLs"; onClicked:baseDialog.open() }
            ActionButton { text:"Más"; onClicked:more.open(); Menu {
                id:more
                MenuItem { text:"Actualizar CSV"; enabled:!moduleBridge.busy && moduleBridge.activeId!==""; onTriggered:moduleBridge.command("export",{}) }
                MenuItem { text:"Pendientes y exclusiones"; enabled:!moduleBridge.busy && moduleBridge.activeId!==""; onTriggered:moduleBridge.command("review",{}) }
                MenuItem { text:"Importar progreso SQLite…"; visible:!page.isBls && ["conocimientos","duas","movimientos"].indexOf(moduleBridge.flow)>=0; enabled:!moduleBridge.busy; onTriggered:progressFile.open() }
                MenuItem { text:"Dividir CSV para Excel"; enabled:!moduleBridge.busy; onTriggered:splitFile.open() }
                MenuItem { text:"Reconectar"; enabled:!moduleBridge.busy; onTriggered:moduleBridge.connectModule() }
            } }
        }
        Rectangle {
            visible: !page.isBls
            Layout.fillWidth: true
            implicitHeight: 62
            radius: 10
            color: Theme.sidebar
            border.color: Theme.border
            RowLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 4
                Repeater {
                    model: page.flows
                    delegate: NavItem {
                        required property int index
                        required property string modelData
                        objectName: "manifestNav_" + modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: page.navWidths[index]
                        horizontal: true
                        label: page.navLabels[index]
                        helpText: page.titles[index]
                        iconName: page.navIcons[index]
                        selected: moduleBridge.flow === modelData
                        onClicked: page.selectProcedure(modelData)
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { visible: !page.isBls; text: page.titles[page.flows.indexOf(moduleBridge.flow)] || ""; color: Theme.text; font.family: Theme.family; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight }
            Item { visible: page.isBls; Layout.fillWidth: true }
            ActionButton { objectName: "manifestProcessingTab"; text: "Procesamiento"; primary: !page.optionsVisible; onClicked: page.optionsVisible = false }
            ActionButton { objectName: "manifestConfigurationTab"; text: "Configuración"; primary: page.optionsVisible; onClicked: page.optionsVisible = true }
        }
        Panel {
            visible: !page.optionsVisible
            Layout.fillWidth:true
            implicitHeight:setup.implicitHeight+32
            ColumnLayout {
                id:setup
                anchors.fill:parent; anchors.margins:16; spacing:10
                RowLayout {
                    visible:!page.isBls
                    Layout.fillWidth:true
                    Text { text: "Período:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                    Select { id:month; objectName:"manifestMonth"; Layout.preferredWidth:145; model:["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]; enabled:!moduleBridge.busy }
                    NumberField { id:year; objectName:"manifestYear"; from:2000; to:2100; value:2026; editable:true; enabled:!moduleBridge.busy; Layout.preferredWidth:115 }
                    Item { Layout.fillWidth: true }
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
                    Select { id:inputMode; objectName:"blsInputMode"; model:["Desde Conocimientos","Archivo externo"]; Layout.preferredWidth:210; enabled:!moduleBridge.busy; onActivated:{if(currentIndex===0) moduleBridge.refreshKnowledge()} }
                    Text { visible:inputMode.currentIndex===0; text:page.knowledgeLabel(); color:Theme.muted; Layout.fillWidth:true; elide:Text.ElideRight }
                    ActionButton { objectName:"blsChooseKnowledge"; visible:inputMode.currentIndex===0; text:"Elegir meses…"; enabled:!moduleBridge.busy; onClicked:{knowledgeDialog.selectedPeriods=page.selectedKnowledge.slice(); knowledgeDialog.open()} }
                }
                RowLayout {
                    visible:page.isBls && inputMode.currentIndex===1
                    Layout.fillWidth:true
                    Field { id:input; Layout.fillWidth:true; placeholderText:"Seleccione la base de BLs"; readOnly:true }
                    ActionButton { text:"Seleccionar base…"; enabled:!moduleBridge.busy; onClicked:inputFile.open() }
                    Field { id:sheet; text:"BLS"; Layout.preferredWidth:110; enabled:!moduleBridge.busy; placeholderText:"Hoja" }
                }
                RowLayout {
                    Layout.fillWidth:true
            Text { visible:!page.isBls; text:"Tabla:"; color:Theme.text; font.family:Theme.family; font.pixelSize:12 }
            Field { id:tableName; objectName:"manifestTableName"; Layout.fillWidth:true; text:page.isBls ? "" : page.automaticName(); readOnly:!page.isBls; placeholderText:page.isBls ? "Nombre de la tabla (opcional)" : "Seleccione un período y modalidad válidos"; enabled:!moduleBridge.busy }
                    ActionButton { text:moduleBridge.busy ? "En ejecución…" : page.resumesBls && moduleBridge.summary.pending>0 ? "Continuar pendientes" : "Iniciar consulta"; objectName:"manifestStart"; primary:true; enabled:moduleBridge.ready && !moduleBridge.busy && (!page.isBls || inputMode.currentIndex===1 || page.knowledgeSelectionReady); onClicked:moduleBridge.command("run",{config:page.configuration()}) }
                    ActionButton { text:"Detener"; enabled:moduleBridge.busy; onClicked:moduleBridge.stop() }
                }
            }
        }
        ScrollView {
            id: configurationView
            visible:page.optionsVisible
            objectName: "manifestConfiguration"
            Layout.fillWidth:true; Layout.fillHeight:true; Layout.minimumHeight: 250; clip:true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            Panel {
                width: configurationView.availableWidth
                implicitHeight: configColumn.implicitHeight + 44
                ColumnLayout {
                    id: configColumn
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 22
                    spacing: 19
                    Text { text: "Parámetros de consulta"; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold }
                    GridLayout {
                        Layout.fillWidth: true; columns: 2; columnSpacing: 18; rowSpacing: 12
                        Text { text:"Consultas simultáneas"; color:Theme.text; font.family:Theme.family; font.pixelSize:12 }
                        NumberField { id:threads; from:1; to:page.isBls ? 20 : 32; value:4; editable:true; enabled:!moduleBridge.busy }
                        Text { text:"Tiempo de espera (s)"; color:Theme.text; font.family:Theme.family; font.pixelSize:12 }
                        NumberField { id:timeout; from:5; to:3600; value:120; editable:true; enabled:!moduleBridge.busy }
                        Text { visible:page.isBls; text:"Rondas de intentos"; color:Theme.text; font.family:Theme.family; font.pixelSize:12 }
                        NumberField { id:retries; visible:page.isBls; from:1; to:10; value:3; editable:true; enabled:!moduleBridge.busy }
                    }
                    Choice { id:visibleBrowser; text:"Mostrar navegador"; checked:true; enabled:!moduleBridge.busy; palette.windowText:Theme.text }
                    ActionButton { id:advancedButton; visible:!page.isBls; property bool expanded:false; text:expanded ? "Ocultar opciones avanzadas" : "Opciones avanzadas"; subtle:true; onClicked:expanded=!expanded }
                    ColumnLayout {
                        visible:!page.isBls && advancedButton.expanded; Layout.fillWidth:true; spacing:10
                        RowLayout {
                            Layout.fillWidth:true
                            Field { id:fromDate; Layout.fillWidth:true; placeholderText:"Desde YYYY-MM-DD (opcional)"; enabled:!moduleBridge.busy }
                            Field { id:toDate; Layout.fillWidth:true; placeholderText:"Hasta YYYY-MM-DD (mismo mes)"; enabled:!moduleBridge.busy }
                        }
                        Select { id:courier; visible:moduleBridge.flow==="conocimientos"; model:["Todos los Courier","Courier N","Courier S"]; Layout.preferredWidth:190; enabled:!moduleBridge.busy }
                        RowLayout {
                            Layout.fillWidth:true
                            Field { id:manifestIds; Layout.fillWidth:true; placeholderText:"IDs de manifiesto separados por espacios (opcional)"; enabled:!moduleBridge.busy }
                            Text { text:"Límite (0 = todos)"; color:Theme.text; font.family:Theme.family; font.pixelSize:12 }
                            NumberField { id:limit; from:0; to:100000; editable:true; enabled:!moduleBridge.busy }
                        }
                    }
                    Text { text:"Carpeta madre común a todos los bots"; color:Theme.text; font.family:Theme.family; font.pixelSize:12 }
                    RowLayout {
                        Layout.fillWidth:true
                        Field { id:output; Layout.fillWidth:true; placeholderText:"Carpeta madre común"; readOnly:true }
                        ActionButton { text:"Elegir carpeta…"; enabled:!moduleBridge.busy; onClicked:outputFolder.open() }
                    }
                    RowLayout {
                        Layout.fillWidth:true
                        Item { Layout.fillWidth:true }
                        ActionButton { text:"Guardar configuración"; primary:true; enabled:!moduleBridge.busy; onClicked:moduleBridge.command("configure",{config:page.configuration()}) }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth:true
            visible: !page.optionsVisible
            Select { id:history; objectName:"manifestHistory"; Layout.fillWidth:true; model:moduleBridge.history; textRole:"label"; placeholder:"Ejecuciones guardadas"; enabled:!moduleBridge.busy; onActivated:moduleBridge.command("select",{id:moduleBridge.history[currentIndex].id}) }
            ActionButton { text:"Ver resultados"; enabled:moduleBridge.activeId!==""; onClicked:moduleBridge.openResults() }
        }
        RowLayout {
            Layout.fillWidth:true
            Text { text:moduleBridge.summary.succeeded+" guardados   ·   "+moduleBridge.summary.pending+" pendientes   ·   "+moduleBridge.summary.running+" en curso"+(moduleBridge.summary.excluded ? "   ·   "+moduleBridge.summary.excluded+" excluidos" : "")+"   ·   "+moduleBridge.summary.rows+(page.isBls ? " filas confirmadas" : " filas"); color:Theme.muted; font.pixelSize:12; Layout.fillWidth:true }
            visible: !page.optionsVisible
            Field { id:search; placeholderText:page.isBls ? "Buscar BL" : "Buscar manifiesto"; Layout.preferredWidth:170; enabled:!moduleBridge.busy; onAccepted:{page.rowOffset=0; moduleBridge.command("view",{search:text,offset:0})} }
        }
        Panel {
            visible: !page.optionsVisible && moduleBridge.activeJobs.length > 0
            Layout.fillWidth:true; implicitHeight: activeColumn.implicitHeight + 24
            ColumnLayout {
                id: activeColumn
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 6
                Text { text: "Descargando ahora"; color: Theme.accent; font.pixelSize: 12 }
                Repeater {
                    model: moduleBridge.activeJobs
                    Text {
                        required property var modelData
                        objectName: "batchActiveJob"; Layout.fillWidth: true; color: Theme.text; font.pixelSize: 12
                        text: modelData.id + (page.isBls ? " · Página " + (modelData.page || 1) + " · " + (modelData.collectedRows || 0) + " filas acumuladas" : "")
                        elide: Text.ElideMiddle; ToolTip.visible: activeHover.hovered; ToolTip.text: text
                        HoverHandler { id: activeHover }
                    }
                }
            }
        }
        Panel {
            visible: !page.optionsVisible
            Layout.fillWidth:true; Layout.fillHeight:true; Layout.minimumHeight:90; clip:true
            ColumnLayout {
                anchors.fill:parent; anchors.margins:12; spacing:8
                RowLayout {
                    Layout.fillWidth:true
                    Text { visible:page.isBls; text:"Fila"; color:Theme.faint; Layout.preferredWidth:40 }
                    Text { text:page.isBls ? "Manifiesto / BL original" : "Manifiesto"; color:Theme.faint; Layout.fillWidth:true }
                    Text { text:"Estado"; color:Theme.faint; Layout.preferredWidth:105 }
                    Text { text:"Intentos"; color:Theme.faint; Layout.preferredWidth:55 }
                    Text { visible:page.isBls; text:"Página"; color:Theme.faint; Layout.preferredWidth:55 }
                    Text { text:"Filas"; color:Theme.faint; Layout.preferredWidth:60 }
                    Item { Layout.preferredWidth:62 }
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
                                Text { visible:page.isBls; text:modelData.ordinal; color:Theme.muted; font.pixelSize:12; Layout.preferredWidth:40 }
                                Text { text:modelData.id; color:Theme.text; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideMiddle; ToolTip.visible:hover.hovered; ToolTip.text:modelData.id; HoverHandler{id:hover} }
                                Text { text:modelData.state; color:modelData.state==="Guardado" ? Theme.success : Theme.muted; Layout.preferredWidth:105; font.pixelSize:12 }
                                Text { text:modelData.attempts; color:Theme.muted; Layout.preferredWidth:55; font.pixelSize:12 }
                                Text { visible:page.isBls; text:modelData.page || "—"; color:Theme.muted; Layout.preferredWidth:55; font.pixelSize:12; ToolTip.visible:pageHover.hovered; ToolTip.text:modelData.checkpointPage ? "Última página guardada: "+modelData.checkpointPage : "Todavía no hay una página guardada"; HoverHandler{id:pageHover} }
                                Text { text:page.isBls && modelData.state!=="Guardado" ? modelData.collectedRows || 0 : modelData.rows; color:Theme.muted; Layout.preferredWidth:60; font.pixelSize:12; ToolTip.visible:page.isBls && rowsHover.hovered; ToolTip.text:modelData.state==="Guardado" ? "Filas confirmadas del BL completo" : "Filas recopiladas y guardadas por página; el BL sigue pendiente hasta terminar"; HoverHandler{id:rowsHover} }
                                ActionButton { objectName: "batchOpenTica"; text: "TICA"; Layout.preferredWidth:62; enabled: !moduleBridge.manualReview.running && !moduleBridge.closing; onClicked: moduleBridge.openInTica(modelData.id,modelData.ordinal); ToolTip.visible: hovered; ToolTip.text: "Revisar esta consulta en un navegador visible" }
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
            ActionButton { visible: !page.optionsVisible; text:"Anterior"; enabled:!moduleBridge.busy && page.rowOffset>0; onClicked:{page.rowOffset=Math.max(0,page.rowOffset-200); moduleBridge.command("view",{search:search.text,offset:page.rowOffset})} }
            ActionButton { visible: !page.optionsVisible; text:"Siguiente"; enabled:!moduleBridge.busy && moduleBridge.jobs.length>=200; onClicked:{page.rowOffset+=200; moduleBridge.command("view",{search:search.text,offset:page.rowOffset})} }
        }
        ReviewStatus { Layout.fillWidth:true; inspector:moduleBridge.manualReview }
    }
    FileDialog { id:inputFile; title:"Base de BLs"; nameFilters:["Bases BLs (*.xlsx *.sqlite3 *.sqlite *.db)"]; onAccepted:input.text=page.localPath(selectedFile) }
    FileDialog { id:splitFile; title:"Dividir un CSV para Excel"; nameFilters:["CSV (*.csv)"]; onAccepted:moduleBridge.command("split",{source:page.localPath(selectedFile)}) }
    FileDialog { id:progressFile; title:"Importar una copia del progreso original"; nameFilters:["Progreso SQLite (*.sqlite3 *.sqlite *.db)"]; onAccepted:moduleBridge.command("import_progress",{source:page.localPath(selectedFile)}) }
    FolderDialog { id:outputFolder; title:"Carpeta madre común a todos los bots"; onAccepted:output.text=page.localPath(selectedFolder) }
    ManifiestosBaseDialog { id:baseDialog; moduleBridge:page.moduleBridge }
    BlsKnowledgeDialog { id:knowledgeDialog; moduleBridge:page.moduleBridge; onPeriodsSelected:function(periods){page.selectedKnowledge=periods} }
}
