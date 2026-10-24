import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Panel {
    id: card
    required property var info
    signal openModule(string moduleId)
    implicitHeight: 126
    border.color: cardHover.hovered ? Qt.alpha(info.color, 0.6) : Theme.border
    Behavior on border.color { ColorAnimation { duration: 160 } }
    HoverHandler { id: cardHover }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                width: 38; height: 38; radius: 10; color: Qt.alpha(card.info.color, 0.12)
                Icon { anchors.centerIn: parent; name: card.info.icon; tint: card.info.color; width: 22; height: 22 }
            }
            Item { Layout.fillWidth: true }
            BusyIndicator { visible: card.info.status === "loading"; running: visible; implicitWidth: 16; implicitHeight: 16; palette.dark: Theme.accent }
            Rectangle { visible: card.info.status !== "loading"; width: 6; height: 6; radius: 3; color: card.info.status === "running" ? Theme.accent : Theme.success }
            Text { text: card.info.mode === "real" ? (card.info.status === "loading" ? "Cargando" : card.info.status === "running" ? "Consultando" : card.info.status === "unavailable" ? "Preparando" : "Conectado") : card.info.status === "running" ? "Simulando" : card.info.status === "paused" ? "Pausado" : card.info.status === "completed" ? "Demo completada" : "Demostración"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 10 }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            Text { text: card.info.title; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold }
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Text { text: "Abrir módulo"; color: cardHover.hovered ? Theme.accent : Theme.text; font.family: Theme.family; font.pixelSize: 11; font.weight: Font.DemiBold }
            Icon { name: "arrow"; width: 16; height: 16; tint: cardHover.hovered ? Theme.accent : Theme.muted }
        }
    }
    Button {
        anchors.fill: parent
        flat: true
        background: Item {}
        Accessible.name: "Abrir " + card.info.title
        onClicked: card.openModule(card.info.id)
    }
}
