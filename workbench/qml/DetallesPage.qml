import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as Native
import "components"

ScrollView {
    id: page
    objectName: "detailsRealPage"
    property int tab: 0
    property var selectedIds: []
    property string activeId: details.activeTable.id || ""
    property bool configDirty: false
    property bool startAfterSave: false
    property string confirmAction: ""
    property string confirmTable: ""
    property var confirmIds: []
    property string confirmText: ""
    property string importName: ""
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    function selectedIndex() { for(let i=0;i<details.tables.length;i++) if(details.tables[i].id === page.activeId) return i; return -1 }
    function filterName() { return ["all", "pending", "succeeded", "retry"][filterBox.currentIndex] || "all" }
    function refreshRows(offset) { details.searchRows(filterName(), rowSearch.text.trim(), offset); page.selectedIds = [] }
    function toggleRow(key, checked) { let values = page.selectedIds.slice(); if(checked && values.indexOf(key)<0) values.push(key); if(!checked) values = values.filter(x => x !== key); page.selectedIds = values }
    function currentConfig() { return {cant_hilos:workerSpin.value, timeout:timeoutSpin.value, max_retries:retrySpin.value, headless:headlessToggle.checked, reuse_context:reuseToggle.checked, lightweight_details:lightToggle.checked, dark_mode:Theme.dark} }
    function startQueries() { if(page.configDirty) { page.startAfterSave = true; details.saveConfig(page.currentConfig()) } else details.startQueries() }
    function requestDelete(action) {
        page.confirmAction = action; page.confirmTable = page.activeId; page.confirmIds = page.selectedIds.slice()
        if(action === "rows") page.confirmText = "¿Eliminar " + page.confirmIds.length + " filas de «" + details.activeTable.name + "»?\n\nLos pendientes elegidos dejarán de consultarse. Los resultados obtenidos se conservarán para exportar."
        if(action === "clean") page.confirmText = "¿Quitar las " + details.summary.succeeded + " filas completadas de «" + details.activeTable.name + "»?\n\nSe conservan pendientes y resultados para futuras exportaciones."
        if(action === "table") page.confirmText = "¿Eliminar la tabla «" + details.activeTable.name + "» y sus filas?\n\nDejará de estar disponible para consultas. Los archivos exportados se conservan."
        deleteDialog.open()
    }
    onTabChanged: { if(tab === 1) databaseDialog.open() }
    onActiveIdChanged: { page.selectedIds = []; rowSearch.text = ""; filterBox.currentIndex = 0 }
    Connections {
        target: details
        function onFilePrepared() { Qt.callLater(function() { importSheet.currentIndex = 0; importTableName.text = details.fileInfo.sheets[0] || ""; importDialog.open() }) }
        function onImportPlanReady() { Qt.callLater(function() { importDialog.close(); importConfirm.open() }) }
        function onDetailReady() { Qt.callLater(function() { detailDialog.open() }) }
        function onEventReceived(event) {
            if(event.command === "configure" && event.event === "error") page.startAfterSave = false
            if(event.command === "configure" && event.event === "result") page.configDirty = false
            if(event.event === "idle" && page.startAfterSave && !event.readonly) { page.startAfterSave = false; Qt.callLater(function() { details.startQueries() }) }
        }
    }

    ColumnLayout {
        width: page.availableWidth; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Detalles BOT"; color: Theme.text; font.family: Theme.family; font.pixelSize: 23; font.weight: Font.DemiBold; Layout.fillWidth: true }
            ActionButton { text: "Procesamiento"; primary: page.tab !== 2; onClicked: page.tab = 0 }
            ActionButton { text: "Configuración"; primary: page.tab === 2; onClicked: page.tab = 2 }
        }
        RowLayout {
            visible: !!details.error || !details.ready; Layout.fillWidth: true
            Text { text: details.error || details.status; color: details.error ? "#ef9ea2" : Theme.muted; font.family: Theme.family; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            ActionButton { visible: !details.ready; text: "Reconectar"; enabled: !details.busy; onClicked: details.connectModule() }
        }
        ColumnLayout {
            visible: page.tab !== 2; Layout.fillWidth: true; spacing: 12
            Panel {
                Layout.fillWidth: true; implicitHeight: sourceColumn.implicitHeight + 32
                ColumnLayout {
                    id: sourceColumn
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 10
                    GridLayout {
                        Layout.fillWidth: true; columns: 3; columnSpacing: 12; rowSpacing: 10
                        Text { text: "Tabla:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                        Select {
                            id: tableSelector; objectName: "detailsTableSelector"; Layout.fillWidth: true
                            model: details.tables; textRole: "name"; valueRole: "id"; placeholder: "Selecciona una tabla guardada"
                            currentIndex: page.selectedIndex(); enabled: details.ready && !details.busy
                            onActivated: { details.selectTable(currentValue); page.selectedIds = [] }
                        }
                        ActionButton { objectName: "detailsImportButton"; text: "Elegir Excel…"; iconName: "folder"; enabled: details.ready && !details.busy; onClicked: excelDialog.open() }
                        Text { text: "Guardar en:"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                        Text { text: details.config.output_base_path || "Selecciona una carpeta"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        ActionButton { text: "Elegir carpeta…"; iconName: "folder"; enabled: details.ready && !details.busy; onClicked: outputDialog.open() }
                    }
                    Text { text: page.activeId ? "Tabla guardada" : "Elige un Excel o abre una tabla guardada."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
                }
            }
            Panel {
                Layout.fillWidth: true; implicitHeight: progressColumn.implicitHeight + 32
                ColumnLayout {
                    id: progressColumn
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: details.summary.succeeded + " / " + details.summary.total; color: Theme.text; font.family: Theme.family; font.pixelSize: 25; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        Text { text: (details.summary.total ? 100 * details.summary.succeeded / details.summary.total : 0).toFixed(1) + "%"; color: Theme.accent; font.family: Theme.family; font.pixelSize: 17 }
                    }
                    Rectangle {
                        Layout.fillWidth: true; height: 6; radius: 3; color: Theme.raised
                        Rectangle { width: parent.width * (details.summary.total ? details.summary.succeeded / details.summary.total : 0); height: parent.height; radius: 3; color: Theme.success }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 22
                        Text { text: "Guardados: " + details.summary.succeeded; color: Theme.success; font.family: Theme.family; font.pixelSize: 11 }
                        Text { text: "Pendientes: " + (details.summary.pending + details.summary.retry); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                        Text { text: "En curso: " + details.summary.running; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                        Text { text: "Revisar: " + details.summary.invalid; color: details.summary.invalid ? Theme.accent : Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: details.status; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true }
                        Text { objectName: "detailsRemainingTime"; text: details.remainingTime; visible: text !== ""; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
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
                        ActionButton { text: "Limpiar vista"; subtle: true; implicitHeight: 26; onClicked: details.clearActivity() }
                    }
                    ListView {
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 6; model: details.events
                        ScrollBar.vertical: ScrollBar {}
                        delegate: RowLayout {
                            required property var modelData
                            width: ListView.view.width - 12
                            Text { text: parent.modelData.time; color: Theme.faint; font.family: "Consolas"; font.pixelSize: 10; Layout.preferredWidth: 65 }
                            Text { text: parent.modelData.message; color: parent.modelData.level === "SUCCESS" ? Theme.success : parent.modelData.level === "WARNING" ? Theme.accent : ["ERROR","CRITICAL"].indexOf(parent.modelData.level)>=0 ? "#ef9ea2" : Theme.muted; font.family: Theme.family; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        }
                    }
                }
            }
            Text { text: !page.activeId ? "Elige un Excel o una tabla para empezar." : !details.config.output_base_path ? "Elige dónde guardar los resultados." : details.summary.invalid ? "Hay entradas que revisar en Base de datos." : "Los resultados se guardan automáticamente."; color: details.summary.invalid ? Theme.accent : Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                ActionButton { text: "Resultados"; iconName: "folder"; enabled: details.outputFolder !== ""; onClicked: details.openOutput() }
                ActionButton { objectName: "detailsDatabaseButton"; text: "Base de datos"; iconName: "database"; enabled: details.ready; onClicked: databaseDialog.open() }
                ActionButton { text: "Más…"; onClicked: moreMenu.popup() }
                Item { Layout.fillWidth: true }
                ActionButton { objectName: "detailsStopButton"; text: "Detener"; iconName: "pause"; enabled: details.running && details.status !== "Deteniendo y guardando…"; onClicked: details.stopQueries() }
                ActionButton {
                    objectName: "detailsStartButton"
                    text: details.busy ? "Procesando…" : details.summary.total && details.summary.total === details.summary.succeeded ? "Actualizar resultados" : details.summary.attempts ? "Retomar pendientes" : "Iniciar consultas"
                    iconName: "play"; primary: true
                    enabled: details.ready && !details.busy && page.activeId !== "" && !!details.config.output_base_path && (details.runtime.chromiumReady || details.summary.total === details.summary.succeeded)
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
                    SpinBox { id: workerSpin; from: 1; to: 20; value: details.config.cant_hilos || 1; enabled: details.ready && !details.busy; palette.text: Theme.text; palette.base: Theme.raised; palette.button: Theme.raised; palette.buttonText: Theme.text; onValueModified: page.configDirty = true }
                    Text { text: "Tiempo de espera (s)"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                    SpinBox { id: timeoutSpin; from: 5; to: 120; value: details.config.timeout || 30; enabled: details.ready && !details.busy; palette.text: Theme.text; palette.base: Theme.raised; palette.button: Theme.raised; palette.buttonText: Theme.text; onValueModified: page.configDirty = true }
                    Text { text: "Rondas de intentos"; color: Theme.text; font.family: Theme.family; font.pixelSize: 12 }
                    SpinBox { id: retrySpin; from: 1; to: 10; value: details.config.max_retries || 3; enabled: details.ready && !details.busy; palette.text: Theme.text; palette.base: Theme.raised; palette.button: Theme.raised; palette.buttonText: Theme.text; onValueModified: page.configDirty = true }
                }
                Toggle { id: headlessToggle; text: "Mantener el navegador oculto"; checked: details.config.headless !== false; enabled: details.ready && !details.busy; onClicked: page.configDirty = true }
                ActionButton { id: advancedButton; property bool expanded: false; text: expanded ? "Ocultar opciones avanzadas" : "Opciones avanzadas"; subtle: true; onClicked: expanded = !expanded }
                ColumnLayout {
                    visible: advancedButton.expanded; Layout.fillWidth: true; spacing: 10
                Toggle { id: reuseToggle; text: "Reutilizar el contexto de cada trabajador"; checked: details.config.reuse_context !== false; enabled: details.ready && !details.busy; onClicked: page.configDirty = true }
                Toggle { id: lightToggle; text: "Simplificar detalles validados para mejorar la navegación"; checked: details.config.lightweight_details !== false; enabled: details.ready && !details.busy; onClicked: page.configDirty = true }
                }
                Toggle { text: "Modo oscuro"; checked: Theme.dark; onClicked: { Theme.dark = checked; preferences.setDark(checked); page.configDirty = true } }
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "Guardar configuración"; primary: true; enabled: details.ready && !details.busy; onClicked: details.saveConfig(page.currentConfig()) }
                }
            }
        }
    }

    Menu {
        id: moreMenu
        palette.window: Theme.surface; palette.windowText: Theme.text; palette.text: Theme.text; palette.base: Theme.surface; palette.highlight: Theme.hover
        MenuItem { text: "Actualizar"; enabled: details.ready && !details.busy; onTriggered: details.refresh() }
        MenuItem { text: "Exportar resultados"; enabled: details.ready && !details.busy && page.activeId !== "" && !!details.config.output_base_path; onTriggered: details.exportResults() }
        MenuSeparator {}
        MenuItem { text: "Abrir registros"; onTriggered: details.openLogs() }
        MenuItem { text: "Interfaz clásica"; enabled: details.ready && !details.busy; onTriggered: details.openClassic() }
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
                    ActionButton { text: "Respaldos"; iconName: "folder"; onClicked: details.openBackups() }
                    ActionButton { text: "Renombrar"; enabled: page.activeId !== "" && !details.busy; onClicked: { renameInput.text = details.activeTable.name; renameDialog.open() } }
                }
                Select {
                    Layout.fillWidth: true; model: details.tables; textRole: "name"; valueRole: "id"
                    currentIndex: page.selectedIndex(); enabled: details.ready && !details.busy
                    onActivated: details.selectTable(currentValue)
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    Select { id: filterBox; Layout.preferredWidth: 160; model: ["Todas", "Pendientes", "Guardadas", "Por reintentar"]; onActivated: page.refreshRows(0); enabled: details.ready && (!details.busy || details.running) }
                    Field { id: rowSearch; Layout.fillWidth: true; placeholderText: "Buscar por DUA o último error"; onAccepted: page.refreshRows(0) }
                    ActionButton { text: "Buscar"; iconName: "search"; enabled: details.ready && (!details.busy || details.running); onClicked: page.refreshRows(0) }
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
                    Layout.fillWidth: true; implicitHeight: 350; clip: true; model: details.rows
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle {
                        id: rowDelegate
                        required property var modelData
                        width: jobList.width - 14; height: 56
                        color: page.selectedIds.indexOf(modelData.id) >= 0 ? Theme.accentTint : "transparent"
                        Rectangle { height: 1; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; color: Theme.border }
                        RowLayout {
                            anchors.fill: parent; spacing: 10
                            Toggle { text: ""; implicitWidth: 26; checked: page.selectedIds.indexOf(rowDelegate.modelData.id) >= 0; onClicked: page.toggleRow(rowDelegate.modelData.id, checked) }
                            Text { text: rowDelegate.modelData.dua || rowDelegate.modelData.original || "(vacío)"; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; Layout.preferredWidth: 210; elide: Text.ElideRight }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 3
                                Text { text: ({pending:"Pendiente",running:"En curso",retry:"Por reintentar",succeeded:"Guardado",invalid:"Revisar dato"})[rowDelegate.modelData.status] || rowDelegate.modelData.status; color: rowDelegate.modelData.status === "succeeded" ? Theme.success : rowDelegate.modelData.status === "pending" ? Theme.muted : Theme.accent; font.family: Theme.family; font.pixelSize: 11 }
                                Text { text: rowDelegate.modelData.reason; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                            Text { text: String(rowDelegate.modelData.attempts); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.preferredWidth: 65 }
                            ActionButton { text: "Ver"; iconName: "chevron"; subtle: true; enabled: !details.busy || details.running; onClicked: details.showDetail(rowDelegate.modelData.id) }
                        }
                    }
                    Text { visible: details.rows.length === 0; anchors.centerIn: parent; text: page.activeId ? "No hay filas para este filtro." : "Importa o abre una tabla guardada."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 13 }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: (details.rows.length ? details.offset + 1 : 0) + "–" + (details.offset + details.rows.length) + " de " + details.rowCount + " filas"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true }
                    ActionButton { text: "Anterior"; enabled: details.offset > 0 && (!details.busy || details.running); onClicked: page.refreshRows(Math.max(0,details.offset - 100)) }
                    ActionButton { text: "Siguiente"; enabled: details.offset + details.rows.length < details.rowCount && (!details.busy || details.running); onClicked: page.refreshRows(details.offset + 100) }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    ActionButton { text: "Eliminar elegidas (" + page.selectedIds.length + ")"; enabled: page.selectedIds.length > 0 && !details.busy; onClicked: page.requestDelete("rows") }
                    ActionButton { text: "Limpiar completadas"; enabled: details.summary.succeeded > 0 && !details.busy; onClicked: page.requestDelete("clean") }
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "Eliminar tabla"; enabled: page.activeId !== "" && !details.busy; onClicked: page.requestDelete("table") }
                }
                Text { text: "Cada eliminación pide confirmación y crea un respaldo. Los resultados confirmados se conservan al limpiar filas."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
        }

        }
    }

    Native.FileDialog { id: excelDialog; title: "Seleccionar Excel de DUAs"; nameFilters: ["Excel (*.xlsx)"]; onAccepted: details.inspectExcel(String(selectedFile)) }
    Native.FolderDialog { id: outputDialog; title: "Seleccionar carpeta de resultados"; onAccepted: details.setOutput(String(selectedFolder)) }

    Dialog {
        id: importDialog
        title: "Guardar tabla"; anchors.centerIn: parent; width: Math.min(560, page.width - 30); modal: true; padding: 24
        palette.windowText: Theme.text; palette.buttonText: Theme.text; background: Panel {}
        contentItem: ColumnLayout {
            spacing: 13
            Text { text: details.fileInfo.path; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideMiddle }
            Text { text: "Hoja"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
            Select { id: importSheet; Layout.fillWidth: true; model: details.fileInfo.sheets; onActivated: importTableName.text = currentText }
            Text { text: "Nombre de la tabla"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
            Field { id: importTableName; Layout.fillWidth: true; placeholderText: "Por ejemplo: marzo26" }
            Text { text: "Si la tabla existe, se agregarán los DUAs nuevos."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        footer: RowLayout {
            spacing: 10
            ActionButton { text: "Cancelar"; onClicked: importDialog.close() }
            Item { Layout.fillWidth: true }
            ActionButton { text: "Continuar"; primary: true; enabled: !details.busy && importTableName.text.trim() !== ""; onClicked: details.prepareImport(importSheet.currentText, importTableName.text) }
        }
    }
    Dialog {
        id: importConfirm
        implicitHeight: 270
        title: "Guardar tabla"; anchors.centerIn: parent; width: Math.min(520,page.width - 30); modal: true; padding: 24
        palette.windowText: Theme.text; background: Panel {}
        contentItem: Text { text: details.importPlan.appended ? "Se agregarán DUAs a «" + details.importPlan.name + "».\nLos resultados guardados se conservan." : "Se creará «" + (details.importPlan.name || "") + "».\nLas consultas empiezan al pulsar Iniciar."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 13; wrapMode: Text.WordWrap }
        footer: RowLayout {
            ActionButton { text: "Volver"; onClicked: { importConfirm.close(); importDialog.open() } }
            Item { Layout.fillWidth: true }
            ActionButton { text: details.importPlan.appended ? "Agregar DUAs" : "Crear tabla"; primary: true; enabled: !details.busy; onClicked: { details.confirmImport(); importConfirm.close() } }
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
            ActionButton { text: "Guardar nombre"; primary: true; onClicked: { details.renameTable(renameInput.text); renameDialog.close() } }
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
            ActionButton { text: "Confirmar eliminación"; primary: true; enabled: !details.busy; onClicked: { if(page.confirmAction === "rows") details.removeRows(page.confirmIds,page.confirmTable); if(page.confirmAction === "clean") details.cleanCompleted(page.confirmTable); if(page.confirmAction === "table") details.deleteTable(page.confirmTable); page.selectedIds = []; deleteDialog.close() } }
        }
    }
    Dialog {
        id: detailDialog
        title: "DUA · " + (details.jobDetail.dua || details.jobDetail.original || "Entrada inválida")
        anchors.centerIn: parent; width: Math.min(840,page.width - 20); height: Math.min(700,page.height - 30); modal: true; padding: 22
        palette.windowText: Theme.text; palette.buttonText: Theme.text; palette.button: Theme.raised
        standardButtons: Dialog.Close; background: Panel {}
        contentItem: ScrollView {
            id: detailScroll
            contentWidth: availableWidth; clip: true
            ColumnLayout {
                width: detailScroll.availableWidth; spacing: 14
                Text { text: "Resultado"; color: Theme.text; font.family: Theme.family; font.pixelSize: 14; font.weight: Font.DemiBold }
                Repeater {
                    model: details.jobDetail.values || []
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
                Text { text: details.jobDetail.reason || ""; color: Theme.accent; font.family: Theme.family; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                Text { text: details.jobDetail.last_error || ""; visible: text !== ""; color: Theme.muted; font.family: "Consolas"; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                Text { text: details.jobDetail.evidence ? "Diagnóstico HTML: " + details.jobDetail.evidence : "Sin evidencia HTML asociada."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                ActionButton { text: "Abrir evidencia"; enabled: !!details.jobDetail.evidence; onClicked: details.openEvidence() }
                Text { text: "Origen de la entrada"; color: Theme.text; font.family: Theme.family; font.pixelSize: 14; font.weight: Font.DemiBold }
                Repeater { model: details.jobDetail.sources || []; Text { required property var modelData; text: "Fila " + modelData.row_number + " · " + (modelData.raw || "(vacío)"); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere } }
                Text { text: "Últimos 100 intentos registrados"; color: Theme.text; font.family: Theme.family; font.pixelSize: 14; font.weight: Font.DemiBold }
                Repeater { model: details.jobDetail.attemptHistory || []; Text { required property var modelData; text: modelData.started + " · " + modelData.outcome + (modelData.error ? " · " + modelData.error : ""); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere } }
                }
            }
        }
    }
}
