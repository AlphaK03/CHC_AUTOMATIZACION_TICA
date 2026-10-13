import QtQuick
import QtQuick.Controls

CheckBox {
    id: control
    implicitHeight: 31
    font.family: Theme.family
    font.pixelSize: 12
    spacing: 9
    indicator: Rectangle {
        implicitWidth: 18; implicitHeight: 18; radius: 4
        x: control.leftPadding
        y: (control.height - height) / 2
        color: control.checked ? Theme.accent : Theme.raised
        border.color: control.activeFocus ? Theme.accent : Theme.border
        Icon { anchors.centerIn: parent; width: 13; height: 13; name: "check"; tint: "#251e19"; visible: control.checked }
    }
    contentItem: Text { text: control.text; font: control.font; color: Theme.muted; leftPadding: control.indicator.width + control.spacing; verticalAlignment: Text.AlignVCenter; wrapMode: Text.WordWrap }
}
