import QtQuick
import QtQuick.Layouts

Panel {
    id: card
    property string label: ""
    property string value: ""
    property string note: ""
    property string iconName: "grid"
    property color valueColor: Theme.text
    implicitHeight: 112
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 7
        RowLayout {
            Layout.fillWidth: true
            Text { text: card.label; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true }
            Icon { name: card.iconName; width: 18; height: 18; tint: Theme.faint }
        }
        Text { text: card.value; font.family: Theme.family; font.pixelSize: 27; font.weight: Font.DemiBold; color: card.valueColor }
        Text { text: card.note; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
    }
}
