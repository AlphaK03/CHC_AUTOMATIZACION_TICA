import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Panel {
    id: panel
    objectName: "monthStartPanel"
    property var launcher: demo.monthLauncher
    property bool expanded: false
    Layout.fillWidth: true
    implicitHeight: body.implicitHeight + 32
    ColumnLayout {
        id: body
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 16
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Iniciar bots por mes"; color: Theme.text; font.family: Theme.family; font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true }
            ActionButton { objectName: "monthStartExpand"; text: panel.expanded ? "Ocultar" : "Elegir bots…"; onClicked: panel.expanded = !panel.expanded }
        }
        ColumnLayout {
            visible: panel.expanded
            Layout.fillWidth: true
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                Select { id: month; objectName: "bulkMonth"; Layout.preferredWidth: 170; model: ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]; currentIndex: panel.launcher.month-1; enabled: !panel.launcher.active; onActivated: panel.launcher.setPeriod(year.value,currentIndex+1) }
                NumberField { id: year; objectName: "bulkYear"; from: 2000; to: 2100; value: panel.launcher.year; enabled: !panel.launcher.active; onValueModified: panel.launcher.setPeriod(value,month.currentIndex+1) }
                Item { Layout.fillWidth: true }
                ActionButton { objectName: "bulkSelectAll"; text: "Marcar todos"; subtle: true; enabled: !panel.launcher.active; onClicked: panel.launcher.selectAll(true) }
                ActionButton { text: "Desmarcar"; subtle: true; enabled: !panel.launcher.active; onClicked: panel.launcher.selectAll(false) }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: panel.width < 750 ? 1 : 2
                columnSpacing: 20; rowSpacing: 4
                Repeater {
                    model: panel.launcher.items
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 0
                        RowLayout {
                            Layout.fillWidth: true
                            Choice { objectName: "bulkSelect_" + modelData.id; text: modelData.label; checked: modelData.selected; Layout.fillWidth: true; enabled: !panel.launcher.active && modelData.available; onClicked: panel.launcher.setSelected(modelData.id,checked) }
                            NumberField { objectName: "bulkWorkers_" + modelData.id; from: 1; to: modelData.maximum; value: modelData.workers; Layout.preferredWidth: 95; implicitHeight: 32; enabled: !panel.launcher.active && modelData.available; onValueModified: panel.launcher.setWorkers(modelData.id,value) }
                        }
                        Text { text: modelData.status; color: modelData.state === "completed" ? Theme.success : modelData.state === "error" || modelData.state === "blocked" ? Theme.accent : Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: "Manifiestos y BLs:"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                Choice { objectName: "bulkMaritime"; text: "Marítimo"; checked: panel.launcher.modes.indexOf("maritimo") >= 0; enabled: !panel.launcher.active; onClicked: panel.launcher.setMode("maritimo",checked) }
                Choice { objectName: "bulkAir"; text: "Aéreo"; checked: panel.launcher.modes.indexOf("aereo") >= 0; enabled: !panel.launcher.active; onClicked: panel.launcher.setMode("aereo",checked) }
                Choice { text: "Terrestre"; checked: panel.launcher.modes.indexOf("terrestre") >= 0; enabled: !panel.launcher.active; onClicked: panel.launcher.setMode("terrestre",checked) }
                Item { Layout.fillWidth: true }
            }
            Text { text: "Los números indican trabajadores por proceso. Se retoma el progreso del mes; BLs espera la base completa de Conocimientos. Terrestre aplica solo a Manifiestos."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            RowLayout {
                Layout.fillWidth: true
                Text { text: panel.launcher.selectionSummary; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true }
                ActionButton { objectName: "bulkCancel"; text: "Detener este inicio"; visible: panel.launcher.active; onClicked: panel.launcher.cancel() }
                ActionButton { objectName: "bulkStart"; text: "Iniciar seleccionados"; primary: true; enabled: !panel.launcher.active && panel.launcher.canStart; onClicked: panel.launcher.start() }
            }
            Text { text: panel.launcher.message; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
    }
}
