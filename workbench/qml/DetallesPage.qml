import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as Native
import "components"

ScrollView {
    id: page
    property var moduleBridge: null
    property var worker: moduleBridge || details
    objectName: worker.moduleId === "detalles" ? "detailsRealPage" : worker.moduleId === "duas_transito" ? "transitRealPage" : worker.moduleId + "RealPage"
    property int tab: 0
    property int confirmed: worker.summary.succeeded + (worker.summary.empty || 0)
    property var selectedIds: []
    property string activeId: worker.activeTable.id || ""
    property bool configDirty: false
    property bool startAfterSave: false
    property bool dailyMode: worker.config.daily_mode === true
    property string confirmAction: ""
    property string confirmTable: ""
    property var confirmIds: []
    property string confirmText: ""
    property string importName: ""
    function selectDailyMode() { page.dailyMode = true }
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    function selectedIndex() { for(let i=0;i<worker.tables.length;i++) if(worker.tables[i].id === page.activeId) return i; return -1 }
    function filterName() { return (worker.moduleId === "xmovimientos" ? ["all", "pending", "succeeded", "retry", "empty", "unverified_empty", "manual_pending"] : ["all", "pending", "succeeded", "retry", "manual_pending"])[filterBox.currentIndex] || "all" }
    function refreshRows(offset) { worker.searchRows(filterName(), rowSearch.text.trim(), offset); page.selectedIds = [] }
    function toggleRow(key, checked) { let values = page.selectedIds.slice(); if(checked && values.indexOf(key)<0) values.push(key); if(!checked) values = values.filter(x => x !== key); page.selectedIds = values }
    function currentConfig() {
        let values = {cant_hilos:workerSpin.value, timeout:timeoutSpin.value, max_retries:retrySpin.value, headless:headlessToggle.checked, reuse_context:reuseToggle.checked, lightweight_details:lightToggle.checked, dark_mode:Theme.dark, daily_mode:page.dailyMode}
        if(dailyStart.text.trim()) values.daily_start_date = dailyStart.text.trim()
        values.daily_end_date = dailyEnd.text.trim()
        return values
    }
    function beginRun() { if(page.dailyMode) worker.startDaily(); else worker.startQueries() }
    function startQueries() { if(page.configDirty) { page.startAfterSave = true; worker.saveConfig(page.currentConfig()) } else page.beginRun() }
    function requestDelete(action) {
        page.confirmAction = action; page.confirmTable = page.activeId; page.confirmIds = page.selectedIds.slice()
        if(action === "rows") page.confirmText = "¿Eliminar " + page.confirmIds.length + " filas de «" + worker.activeTable.name + "»?\n\nLos pendientes elegidos dejarán de consultarse. Los resultados obtenidos se conservarán para exportar."
        if(action === "clean") page.confirmText = "¿Quitar las " + worker.summary.succeeded + " filas completadas de «" + worker.activeTable.name + "»?\n\nSe conservan pendientes y resultados para futuras exportaciones."
        if(action === "table") page.confirmText = "¿Eliminar la tabla «" + worker.activeTable.name + "» y sus filas?\n\nDejará de estar disponible para consultas. Los archivos exportados se conservan."
        deleteDialog.open()
    }
    onTabChanged: { if(tab === 1) databaseDialog.open() }
    onActiveIdChanged: { page.selectedIds = []; rowSearch.text = ""; filterBox.currentIndex = 0 }
    Connections {
        target: worker
        function onFilePrepared() { Qt.callLater(function() { importSheet.currentIndex = 0; importTableName.text = worker.fileInfo.sheets[0] || ""; importDialog.open() }) }
        function onImportPlanReady() { Qt.callLater(function() { importDialog.close(); importConfirm.open() }) }
        function onDetailReady() { Qt.callLater(function() { detailLine.currentIndex = 0; detailDialog.open() }) }
        function onEventReceived(event) {
            if(event.command === "configure" && event.event === "error") page.startAfterSave = false
            if(event.command === "configure" && event.event === "result") page.configDirty = false
            if(event.event === "idle" && page.startAfterSave && !event.readonly) { page.startAfterSave = false; Qt.callLater(function() { page.beginRun() }) }
        }
    }

    ColumnLayout {
        width: page.availableWidth; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Text { text: worker.moduleTitle + " BOT"; color: Theme.text; font.family: Theme.family; font.pixelSize: 23; font.weight: Font.DemiBold; Layout.fillWidth: true }
            ActionButton { text: "Procesamiento"; primary: page.tab !== 2; onClicked: page.tab = 0 }
            ActionButton { text: "Configuración"; primary: page.tab === 2; onClicked: page.tab = 2 }
        }
        RowLayout {
            visible: !!worker.error || !worker.ready; Layout.fillWidth: true
            Text { text: worker.error || worker.status; color: worker.error ? "#ef9ea2" : Theme.muted; font.family: Theme.family; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            ActionButton { visible: !worker.ready; text: "Reconectar"; enabled: !worker.busy; onClicked: worker.connectModule() }
        }
        ColumnLayout {
            visible: page.tab !== 2; Layout.fillWidth: true; spacing: 12
            Panel {
                Layout.fillWidth: true; implicitHeight: sourceColumn.implicitHeight + 32
                ColumnLayout {
                    id: sourceColumn
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 10
                    RowLayout {
                        Layout.fillWidth: true; spacing: 12
                        Text { text: "Modo:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12; Layout.preferredWidth: 61 }
                        Select { objectName: "detailsModeSelector"; Layout.preferredWidth: 235; model: ["Manual", "Diario automático"]; currentIndex: page.dailyMode ? 1 : 0; enabled: worker.ready && !worker.busy; onActivated: { page.dailyMode = currentIndex === 1; page.configDirty = true } }
                        Item { Layout.fillWidth: true }
                    }
                    RowLayout {
                        visible: page.dailyMode; Layout.fillWidth: true; spacing: 12
                        Text { text: "Desde:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12; Layout.preferredWidth: 61 }
                        Field { id: dailyStart; objectName: "detailsDailyStart"; Layout.preferredWidth: 170; text: worker.config.daily_start_date || worker.daily.startDate || ""; placeholderText: "AAAA-MM-DD"; enabled: worker.ready && !worker.busy; onTextEdited: page.configDirty = true }
                        Text { text: "Hasta:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                        Field { id: dailyEnd; objectName: "detailsDailyEnd"; Layout.preferredWidth: 140; text: worker.config.daily_end_date || ""; placeholderText: "Continuo"; enabled: worker.ready && !worker.busy; onTextEdited: page.configDirty = true }
                        Item { Layout.fillWidth: true }
                        ActionButton { objectName: "detailsCalendarButton"; text: "Calendario"; enabled: worker.ready; onClicked: { worker.loadCalendar(dailyStart.text.trim().slice(0,7) || worker.daily.month); calendarDialog.open() } }
                    }
                    GridLayout {
                        Layout.fillWidth: true; columns: 3; columnSpacing: 12; rowSpacing: 10
                        Text { visible: !page.dailyMode; text: "Tabla:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                        Select {
                            id: tableSelector; objectName: "detailsTableSelector"; Layout.fillWidth: true
                            visible: !page.dailyMode
                            model: worker.tables; textRole: "name"; valueRole: "id"; placeholder: "Selecciona una tabla guardada"
                            currentIndex: page.selectedIndex(); enabled: worker.ready && !worker.busy
                            onActivated: { worker.selectTable(currentValue); page.selectedIds = [] }
                        }
                        ActionButton { visible: !page.dailyMode; objectName: "detailsImportButton"; text: "Elegir Excel…"; iconName: "folder"; enabled: worker.ready && !worker.busy; onClicked: excelDialog.open() }
                        Text { text: "Guardar en:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                        Text { text: worker.config.output_base_path || "Selecciona una carpeta"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        ActionButton { text: "Elegir carpeta…"; iconName: "folder"; enabled: worker.ready && !worker.busy; onClicked: outputDialog.open() }
                    }
                    Text { text: page.dailyMode ? "Descarga su base diaria y acumula los resultados por mes." : page.activeId ? "Tabla guardada" : "Elige un Excel o abre una tabla guardada."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
                }
            }
            Panel {
                visible: !page.dailyMode || (!!worker.daily.tableId && worker.daily.tableId === page.activeId) || String(worker.activeTable.source_path || "").startsWith("daily://")
                Layout.fillWidth: true; implicitHeight: progressColumn.implicitHeight + 32
                ColumnLayout {
                    id: progressColumn
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: page.confirmed + " / " + worker.summary.total; color: Theme.text; font.family: Theme.family; font.pixelSize: 25; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        Text { text: (worker.summary.total ? 100 * page.confirmed / worker.summary.total : 0).toFixed(1) + "%"; color: Theme.accent; font.family: Theme.family; font.pixelSize: 17 }
                        ActionButton { objectName: "retryMonthButton"; visible: String(worker.activeTable.source_path || "").startsWith("daily://"); text: "Reintentar mes"; enabled: worker.ready && !worker.busy; onClicked: worker.retryMonth(String(worker.activeTable.source_path).slice(8)); ToolTip.visible: hovered; ToolTip.text: "Da hasta tres intentos nuevos a los pendientes del mes y consulta sus días sin completar" }
                    }
                    Rectangle {
                        Layout.fillWidth: true; height: 6; radius: 3; color: Theme.raised
                        Rectangle { width: parent.width * (worker.summary.total ? page.confirmed / worker.summary.total : 0); height: parent.height; radius: 3; color: Theme.success }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 22
                        Text { text: "Guardados: " + worker.summary.succeeded; color: Theme.success; font.family: Theme.family; font.pixelSize: 11 }
                        Text { visible: worker.moduleId === "xmovimientos"; text: "Vacíos: " + (worker.summary.empty || 0); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                        Text { text: "Pendientes: " + (worker.summary.pending + worker.summary.retry); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                        Text { text: "En curso: " + worker.summary.running; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                        Text { text: "Revisar: " + worker.summary.invalid; color: worker.summary.invalid ? Theme.accent : Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: worker.status; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true }
                        Text { objectName: "detailsRemainingTime"; text: worker.remainingTime; visible: text !== ""; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                    }
                }
            }
            Panel {
                Layout.fillWidth: true; implicitHeight: 150
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 16; spacing: 8
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Actividad"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        ActionButton { text: "Limpiar vista"; subtle: true; implicitHeight: 26; onClicked: worker.clearActivity() }
                    }
                    Text {
                        objectName: "detailsActiveJobs"
                        visible: worker.activeJobs.length > 0; text: "Descargando: " + worker.activeJobs.join("   ·   ")
                        color: Theme.accent; font.family: "Consolas"; font.pixelSize: 11
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                    }
                    ActivityView {
                        Layout.fillWidth: true; Layout.fillHeight: true; model: worker.activityModel
                    }
                }
            }
            Text { text: !worker.config.output_base_path ? "Elige dónde guardar los resultados." : page.dailyMode ? worker.dailyActive ? worker.status : dailyEnd.text.trim() ? "Se detiene al completar el rango elegido." : "Al terminar espera hasta las 00:01. Detener conserva el progreso." : !page.activeId ? "Elige un Excel o una tabla para empezar." : worker.summary.invalid ? "Hay entradas que revisar en Base de datos." : "Los resultados se guardan automáticamente."; color: worker.summary.invalid ? Theme.accent : Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                ActionButton { text: "Resultados"; iconName: "folder"; enabled: worker.outputFolder !== ""; onClicked: worker.openOutput() }
                ActionButton { objectName: "detailsDatabaseButton"; text: "Base de datos"; iconName: "database"; enabled: worker.ready; onClicked: databaseDialog.open() }
                ActionButton { text: "Más…"; onClicked: moreMenu.popup() }
                Item { Layout.fillWidth: true }
                ActionButton { objectName: "detailsStopButton"; text: "Detener"; iconName: "pause"; enabled: (worker.running || worker.dailyActive) && worker.status !== "Deteniendo y guardando…"; onClicked: worker.stopQueries() }
                ActionButton {
                    objectName: "detailsStartButton"
                    text: worker.dailyActive ? "Automático activo" : worker.busy ? "Procesando…" : page.dailyMode ? "Iniciar automático" : worker.summary.total && worker.summary.total === page.confirmed ? "Actualizar resultados" : worker.summary.attempts ? "Retomar pendientes" : "Iniciar consultas"
                    iconName: "play"; primary: true
                    enabled: worker.ready && !worker.busy && !!worker.config.output_base_path && (page.dailyMode ? worker.runtime.chromiumReady && dailyStart.text.trim() !== "" : page.activeId !== "" && (worker.runtime.chromiumReady || worker.summary.total === page.confirmed))
                    onClicked: page.startQueries()
                }
            }
        }
        Panel {
            visible: page.tab === 2
            Layout.fillWidth: true; implicitHeight: configColumn.implicitHeight + 44
            ColumnLayout {
                id: configColumn
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 22; spacing: 19
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Parámetros de consulta"; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    Text { text: page.configDirty ? "Cambios sin guardar" : "Ajustes guardados"; color: page.configDirty ? Theme.accent : Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
                }
                GridLayout {
                    Layout.fillWidth: true; columns: 2; columnSpacing: 18; rowSpacing: 12
                    Text { text: "Consultas simultáneas"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                    SpinBox { id: workerSpin; from: 1; to: 20; value: worker.config.cant_hilos || 1; enabled: worker.ready && !worker.busy; palette.text: Theme.text; palette.base: Theme.raised; palette.button: Theme.raised; palette.buttonText: Theme.text; onValueModified: page.configDirty = true }
                    Text { text: "Tiempo de espera (s)"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                    SpinBox { id: timeoutSpin; from: 5; to: 120; value: worker.config.timeout || 30; enabled: worker.ready && !worker.busy; palette.text: Theme.text; palette.base: Theme.raised; palette.button: Theme.raised; palette.buttonText: Theme.text; onValueModified: page.configDirty = true }
                    Text { text: "Rondas de intentos (modo Manual)"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                    SpinBox { id: retrySpin; from: 1; to: 10; value: worker.config.max_retries || 3; enabled: worker.ready && !worker.busy; palette.text: Theme.text; palette.base: Theme.raised; palette.button: Theme.raised; palette.buttonText: Theme.text; onValueModified: page.configDirty = true }
                }
                Toggle { id: headlessToggle; text: "Mantener el navegador oculto"; checked: worker.config.headless !== false; enabled: worker.ready && !worker.busy; onClicked: page.configDirty = true }
                Text { text: "Diario y reintentos del calendario: hasta 3 intentos por DUA. Después, los pendientes quedan para revisión manual."; color: Theme.faint; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                ActionButton { id: advancedButton; property bool expanded: false; text: expanded ? "Ocultar opciones avanzadas" : "Opciones avanzadas"; subtle: true; onClicked: expanded = !expanded }
                ColumnLayout {
                    visible: advancedButton.expanded; Layout.fillWidth: true; spacing: 10
                Toggle { id: reuseToggle; text: "Reutilizar el contexto de cada trabajador"; checked: worker.config.reuse_context !== false; enabled: worker.ready && !worker.busy; onClicked: page.configDirty = true }
                Toggle { id: lightToggle; visible: worker.supportsLightweight; text: "Simplificar detalles validados para mejorar la navegación"; checked: worker.config.lightweight_details !== false; enabled: worker.ready && !worker.busy; onClicked: page.configDirty = true }
                }
                Toggle { text: "Modo oscuro"; checked: Theme.dark; onClicked: { Theme.dark = checked; preferences.setDark(checked); page.configDirty = true } }
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "Guardar configuración"; primary: true; enabled: worker.ready && !worker.busy; onClicked: worker.saveConfig(page.currentConfig()) }
                }
            }
        }
    }

    Menu {
        id: moreMenu
        palette.window: Theme.surface; palette.windowText: Theme.text; palette.text: Theme.text; palette.base: Theme.surface; palette.highlight: Theme.hover
        MenuItem { text: "Calendario diario"; enabled: worker.ready; onTriggered: { worker.loadCalendar(worker.daily.month); calendarDialog.open() } }
        MenuItem { text: "Actualizar"; enabled: worker.ready && !worker.busy; onTriggered: worker.refresh() }
        MenuItem { text: "Exportar resultados"; enabled: worker.ready && !worker.busy && page.activeId !== "" && !!worker.config.output_base_path; onTriggered: worker.exportResults() }
        MenuSeparator {}
        MenuItem { text: "Abrir registros"; onTriggered: worker.openLogs() }
        MenuItem { text: "Interfaz clásica"; visible: worker.supportsClassic; enabled: worker.ready && !worker.busy; onTriggered: worker.openClassic() }
    }
    Dialog {
        id: databaseDialog; objectName: "detailsDatabaseDialog"
        title: "Base de datos"; modal: true; anchors.centerIn: parent
        width: Math.min(940, page.width - 20); height: Math.min(690, page.height - 20)
        padding: 16; standardButtons: Dialog.Close
        palette.windowText: Theme.text; palette.buttonText: Theme.text; palette.button: Theme.raised
        background: Panel {}
        contentItem: ScrollView {
            id: databaseScroll; contentWidth: availableWidth; clip: true
            Panel {
                width: databaseScroll.availableWidth
            implicitHeight: databaseColumn.implicitHeight + 44
            ColumnLayout {
                id: databaseColumn
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 22; spacing: 14
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Tablas y filas guardadas"; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    ActionButton { text: "Respaldos"; iconName: "folder"; onClicked: worker.openBackups() }
                    ActionButton { text: "Renombrar"; enabled: page.activeId !== "" && !worker.busy; onClicked: { renameInput.text = worker.activeTable.name; renameDialog.open() } }
                }
                Select {
                    Layout.fillWidth: true; model: worker.tables; textRole: "name"; valueRole: "id"
                    currentIndex: page.selectedIndex(); enabled: worker.ready && !worker.busy
                    onActivated: worker.selectTable(currentValue)
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    Select { id: filterBox; Layout.preferredWidth: 160; model: worker.moduleId === "xmovimientos" ? ["Todas", "Pendientes", "Guardadas", "Errores", "Vacías", "Vacías por verificar", "Omitidas del automático"] : ["Todas", "Pendientes", "Guardadas", "Por reintentar", "Omitidas del automático"]; onActivated: page.refreshRows(0); enabled: worker.ready && (!worker.busy || worker.running) }
                    Field { id: rowSearch; Layout.fillWidth: true; placeholderText: "Buscar por DUA o último error"; onAccepted: page.refreshRows(0) }
                    ActionButton { text: "Buscar"; iconName: "search"; enabled: worker.ready && (!worker.busy || worker.running); onClicked: page.refreshRows(0) }
                }
                Rectangle {
                    Layout.fillWidth: true; height: 33; radius: 6; color: Theme.raised
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 42; anchors.rightMargin: 46
                        Text { text: "DUA / ENTRADA ORIGINAL"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.preferredWidth: 210 }
                        Text { text: "ESTADO Y ÚLTIMO ERROR"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true }
                        Text { text: "INTENTOS"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.preferredWidth: 65 }
                    }
                }
                ListView {
                    id: jobList
                    objectName: "detailsJobList"
                    Layout.fillWidth: true; implicitHeight: 350; clip: true; model: worker.rows
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle {
                        id: rowDelegate
                        required property var modelData
                        property bool emptyUnverified: worker.moduleId === "xmovimientos" && modelData.error_kind === "NoMovimientosError"
                        width: jobList.width - 14; height: 56
                        color: page.selectedIds.indexOf(modelData.id) >= 0 ? Theme.accentTint : "transparent"
                        Rectangle { height: 1; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; color: Theme.border }
                        RowLayout {
                            anchors.fill: parent; spacing: 10
                            Toggle { text: ""; implicitWidth: 26; checked: page.selectedIds.indexOf(rowDelegate.modelData.id) >= 0; onClicked: page.toggleRow(rowDelegate.modelData.id, checked) }
                            Text { text: rowDelegate.modelData.dua || rowDelegate.modelData.original || "(vacío)"; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; Layout.preferredWidth: 210; elide: Text.ElideRight }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 3
                                Text { text: rowDelegate.emptyUnverified ? "Vacío por verificar" : ({pending:"Pendiente",running:"En curso",retry:worker.moduleId === "xmovimientos" ? "Error" : "Por reintentar",empty:"Vacío",succeeded:"Guardado",invalid:"Revisar dato"})[rowDelegate.modelData.status] || rowDelegate.modelData.status; color: rowDelegate.modelData.status === "succeeded" ? Theme.success : rowDelegate.emptyUnverified || ["pending","empty"].indexOf(rowDelegate.modelData.status) >= 0 ? Theme.muted : Theme.accent; font.family: Theme.family; font.pixelSize: 11 }
                                Text { text: rowDelegate.modelData.reason; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                            Text { text: String(rowDelegate.modelData.attempts); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.preferredWidth: 65 }
                            ActionButton { objectName: "duaOpenTica"; text: "TICA"; visible: !!rowDelegate.modelData.dua; enabled: !worker.manualReview.running && !worker.closing; onClicked: worker.openInTica(rowDelegate.modelData.id); ToolTip.visible: hovered; ToolTip.text: "Abrir una consulta automatizada en un navegador visible" }
                            ActionButton { text: "Ver"; iconName: "chevron"; subtle: true; enabled: !worker.busy || worker.running; onClicked: worker.showDetail(rowDelegate.modelData.id) }
                        }
                    }
                    Text { visible: worker.rows.length === 0; anchors.centerIn: parent; text: page.activeId ? "No hay filas para este filtro." : "Importa o abre una tabla guardada."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 13 }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: (worker.rows.length ? worker.offset + 1 : 0) + "–" + (worker.offset + worker.rows.length) + " de " + worker.rowCount + " filas"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true }
                    ActionButton { text: "Anterior"; enabled: worker.offset > 0 && (!worker.busy || worker.running); onClicked: page.refreshRows(Math.max(0,worker.offset - 100)) }
                    ActionButton { text: "Siguiente"; enabled: worker.offset + worker.rows.length < worker.rowCount && (!worker.busy || worker.running); onClicked: page.refreshRows(worker.offset + 100) }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    ActionButton { text: "Eliminar elegidas (" + page.selectedIds.length + ")"; enabled: page.selectedIds.length > 0 && !worker.busy; onClicked: page.requestDelete("rows") }
                    ActionButton { objectName: "retryEmptyButton"; visible: worker.moduleId === "xmovimientos"; text: "Reintentar vacíos"; enabled: ((worker.summary.empty || 0) + (worker.summary.empty_unverified || 0)) > 0 && !worker.busy; onClicked: worker.retryEmpty(page.selectedIds) }
                    ActionButton { text: "Limpiar completadas"; enabled: worker.summary.succeeded > 0 && !worker.busy; onClicked: page.requestDelete("clean") }
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "Eliminar tabla"; enabled: page.activeId !== "" && !worker.busy; onClicked: page.requestDelete("table") }
                }
                Text { text: "Cada eliminación pide confirmación y crea un respaldo. Los resultados confirmados se conservan al limpiar filas."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                ReviewStatus { Layout.fillWidth: true; inspector: worker.manualReview }
                Text { text: "TICA abre una revisión visible; no cambia el estado ni guarda resultados del lote."; color: Theme.faint; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
        }

        }
    }

    Native.FileDialog { id: excelDialog; title: "Seleccionar Excel de DUAs"; nameFilters: ["Excel (*.xlsx)"]; onAccepted: worker.inspectExcel(String(selectedFile)) }
    Native.FolderDialog { id: outputDialog; title: "Seleccionar carpeta de resultados"; onAccepted: worker.setOutput(String(selectedFolder)) }
    DailyCalendar {
        id: calendarDialog; moduleBridge: page.worker; anchors.centerIn: parent; width: Math.min(530,page.width - 20)
        initialStart: dailyStart.text.trim(); initialEnd: dailyEnd.text.trim()
        onRangeSelected: function(start, end) { dailyStart.text = start; dailyEnd.text = end; page.dailyMode = true; page.configDirty = true }
    }

    Dialog {
        id: importDialog
        title: "Guardar tabla"; anchors.centerIn: parent; width: Math.min(560, page.width - 30); modal: true; padding: 24
        palette.windowText: Theme.text; palette.buttonText: Theme.text; background: Panel {}
        contentItem: ColumnLayout {
            spacing: 13
            Text { text: worker.fileInfo.path; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideMiddle }
            Text { text: "Hoja"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
            Select { id: importSheet; Layout.fillWidth: true; model: worker.fileInfo.sheets; onActivated: importTableName.text = currentText }
            Text { text: "Nombre de la tabla"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
            Field { id: importTableName; Layout.fillWidth: true; placeholderText: "Por ejemplo: marzo26" }
            Text { text: "Si la tabla existe, se agregarán los DUAs nuevos."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        footer: RowLayout {
            spacing: 10
            ActionButton { text: "Cancelar"; onClicked: importDialog.close() }
            Item { Layout.fillWidth: true }
            ActionButton { text: "Continuar"; primary: true; enabled: !worker.busy && importTableName.text.trim() !== ""; onClicked: worker.prepareImport(importSheet.currentText, importTableName.text) }
        }
    }
    Dialog {
        id: importConfirm
        implicitHeight: 270
        title: "Guardar tabla"; anchors.centerIn: parent; width: Math.min(520,page.width - 30); modal: true; padding: 24
        palette.windowText: Theme.text; background: Panel {}
        contentItem: Text { text: worker.importPlan.appended ? "Se agregarán DUAs a «" + worker.importPlan.name + "».\nLos resultados guardados se conservan." : "Se creará «" + (worker.importPlan.name || "") + "».\nLas consultas empiezan al pulsar Iniciar."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 13; wrapMode: Text.WordWrap }
        footer: RowLayout {
            ActionButton { text: "Volver"; onClicked: { importConfirm.close(); importDialog.open() } }
            Item { Layout.fillWidth: true }
            ActionButton { text: worker.importPlan.appended ? "Agregar DUAs" : "Crear tabla"; primary: true; enabled: !worker.busy; onClicked: { worker.confirmImport(); importConfirm.close() } }
        }
    }
    Dialog {
        id: renameDialog
        title: "Renombrar tabla"; anchors.centerIn: parent; width: Math.min(450,page.width - 30); modal: true; padding: 24
        palette.windowText: Theme.text; background: Panel {}
        contentItem: Field { id: renameInput; placeholderText: "Nombre de la tabla" }
        footer: RowLayout {
            ActionButton { text: "Cancelar"; onClicked: renameDialog.close() }
            Item { Layout.fillWidth: true }
            ActionButton { text: "Guardar nombre"; primary: true; onClicked: { worker.renameTable(renameInput.text); renameDialog.close() } }
        }
    }
    Dialog {
        id: deleteDialog
        title: "Confirmar eliminación"; anchors.centerIn: parent; width: Math.min(540,page.width - 30); modal: true; padding: 24
        palette.windowText: Theme.text; background: Panel {}
        contentItem: ColumnLayout {
            spacing: 14
            Text { text: page.confirmText; color: Theme.text; font.family: Theme.family; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Text { text: "Se creará un respaldo SQLite antes de cambiar la tabla."; color: Theme.accent; font.family: Theme.family; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }
        footer: RowLayout {
            ActionButton { text: "Cancelar"; onClicked: deleteDialog.close() }
            Item { Layout.fillWidth: true }
            ActionButton { text: "Confirmar eliminación"; primary: true; enabled: !worker.busy; onClicked: { if(page.confirmAction === "rows") worker.removeRows(page.confirmIds,page.confirmTable); if(page.confirmAction === "clean") worker.cleanCompleted(page.confirmTable); if(page.confirmAction === "table") worker.deleteTable(page.confirmTable); page.selectedIds = []; deleteDialog.close() } }
        }
    }
    Dialog {
        id: detailDialog
        title: "DUA · " + (worker.jobDetail.dua || worker.jobDetail.original || "Entrada inválida")
        anchors.centerIn: parent; width: Math.min(840,page.width - 20); height: Math.min(700,page.height - 30); modal: true; padding: 22
        palette.windowText: Theme.text; palette.buttonText: Theme.text; palette.button: Theme.raised
        standardButtons: Dialog.Close; background: Panel {}
        contentItem: ScrollView {
            id: detailScroll
            contentWidth: availableWidth; clip: true
            ColumnLayout {
                width: detailScroll.availableWidth; spacing: 14
                Text { text: worker.jobDetail.status === "empty" ? "Vacío: sin movimientos por ahora" : "Resultado"; color: Theme.text; font.family: Theme.family; font.pixelSize: 14; font.weight: Font.DemiBold }
                ActionButton { text: "Abrir en TICA"; visible: !!worker.jobDetail.dua; enabled: !worker.manualReview.running && !worker.closing; onClicked: worker.openInTica(worker.jobDetail.id) }
                Text { visible: worker.jobDetail.status === "empty"; text: "Última consulta: " + (worker.jobDetail.emptyCheckedAt ? new Date(worker.jobDetail.emptyCheckedAt).toLocaleString() : "—"); color: Theme.muted; font.pixelSize: 12 }
                Select { id: detailLine; visible: (worker.jobDetail.resultRows || []).length > 1; Layout.fillWidth: true; model: (worker.jobDetail.resultRows || []).map((row,index) => (row.Item ? "Línea " + row.Item : row.Tributo ? "Tributo " + row.Tributo : row.Movimiento ? "Movimiento " + row.Movimiento : "Fila " + (index+1)) + " · " + (index+1) + " / " + worker.jobDetail.resultRows.length) }
                Repeater {
                    model: worker.jobDetail.status === "empty" ? [] : worker.jobDetail.values || []
                    ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true; spacing: 5
                        Text { text: parent.modelData.field; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10 }
                        Text { text: parent.modelData.value || "—"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                        Rectangle { height: 1; Layout.fillWidth: true; color: Theme.border }
                    }
                }
                ActionButton { id: historyButton; property bool expanded: false; text: expanded ? "Ocultar historial" : "Ver historial y diagnóstico"; subtle: true; onClicked: expanded = !expanded }
                ColumnLayout {
                    visible: historyButton.expanded; Layout.fillWidth: true; spacing: 12
                Text { text: worker.jobDetail.reason || ""; color: Theme.accent; font.family: Theme.family; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                Text { text: worker.jobDetail.last_error || ""; visible: text !== ""; color: Theme.muted; font.family: "Consolas"; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                Text { text: worker.jobDetail.evidence ? "Diagnóstico HTML: " + worker.jobDetail.evidence : "Sin evidencia HTML asociada."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                ActionButton { text: "Abrir evidencia"; enabled: !!worker.jobDetail.evidence; onClicked: worker.openEvidence() }
                Text { text: "Origen de la entrada"; color: Theme.text; font.family: Theme.family; font.pixelSize: 14; font.weight: Font.DemiBold }
                Repeater { model: worker.jobDetail.sources || []; Text { required property var modelData; text: "Fila " + modelData.row_number + " · " + (modelData.raw || "(vacío)"); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere } }
                Text { text: "Últimos 100 intentos registrados"; color: Theme.text; font.family: Theme.family; font.pixelSize: 14; font.weight: Font.DemiBold }
                Repeater { model: worker.jobDetail.attemptHistory || []; Text { required property var modelData; text: modelData.started + " · " + modelData.outcome + (modelData.error ? " · " + modelData.error : ""); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere } }
                }
            }
        }
    }
}
