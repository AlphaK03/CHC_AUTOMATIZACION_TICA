import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: log
    objectName: "monthlyLog"
    Layout.fillWidth: true
    spacing: 10
    property string expandedMonth: ""
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Bitácora de descargas"; color: Theme.text; font.family: Theme.family; font.pixelSize: 22; font.weight: Font.DemiBold }
        Item { Layout.fillWidth: true }
        ActionButton { objectName: "refreshMonthly"; text: demo.monthlyBusy ? "Actualizando…" : "Actualizar"; enabled: !demo.monthlyBusy; onClicked: demo.refreshMonthly() }
    }
    Text { text: "Progreso por mes · Completado indica cobertura mensual verificada."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Text { visible: !demo.monthlyRows.length; text: demo.monthlyBusy ? "Leyendo descargas guardadas…" : demo.monthlyMessage; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Repeater {
        model: demo.monthlyRows
        delegate: ColumnLayout {
            id: month
            required property var modelData
            Layout.fillWidth: true
            spacing: 8
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
            RowLayout {
                Layout.fillWidth: true
                Text { text: month.modelData.label; color: Theme.text; font.family: Theme.family; font.pixelSize: 15; font.weight: Font.DemiBold }
                Item { Layout.fillWidth: true }
                Text { text: month.modelData.completed + " / 6 bots completos"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: log.width < 750 ? 3 : 6
                columnSpacing: 8; rowSpacing: 8
                Repeater {
                    model: month.modelData.cells
                    delegate: Rectangle {
                        id: cell
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 64
                        radius: 7
                        color: hover.hovered ? Theme.hover : Theme.surface
                        border.color: Theme.border
                        property color stateColor: modelData.status === "completed" ? Theme.success : modelData.status === "missing" ? Theme.faint : Theme.accent
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 10; spacing: 6
                            Text { text: ({detalles:"Detalles",duas_transito:"Tránsito",talon:"Talón",xmovimientos:"XMovimientos",bls:"BLs",manifiestos:"Manifiestos"})[cell.modelData.module]; color: Theme.text; font.family: Theme.family; font.pixelSize: 11; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                            RowLayout {
                                Rectangle { width: 5; height: 5; radius: 3; color: cell.stateColor }
                                Text { text: cell.modelData.label; color: cell.stateColor; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                        }
                        HoverHandler { id: hover }
                        ToolTip.visible: hover.hovered
                        ToolTip.delay: 300
                        ToolTip.text: cell.modelData.detail
                        Button { anchors.fill: parent; flat: true; background: Item {} Accessible.name: cell.modelData.module + " " + month.modelData.label + ": " + cell.modelData.label; onClicked: demo.navigate(cell.modelData.module) }
                    }
                }
            }
            ActionButton { text: log.expandedMonth === month.modelData.period ? "Ocultar procedimientos de Manifiestos" : "Ver procedimientos de Manifiestos"; subtle: true; onClicked: log.expandedMonth = log.expandedMonth === month.modelData.period ? "" : month.modelData.period }
            Repeater {
                model: log.expandedMonth === month.modelData.period ? month.modelData.procedures : []
                delegate: RowLayout {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    Text { text: ["Manifiestos", "Conocimientos", "DUAs", "Movimientos", "Contenedores"][index]; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.preferredWidth: 125 }
                    Text { text: modelData.label; color: modelData.status === "completed" ? Theme.success : Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.preferredWidth: 95 }
                    Text { text: modelData.detail; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                }
            }
        }
    }
    Text { visible: demo.monthlyRows.length > 0; text: demo.monthlyMessage; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
}
