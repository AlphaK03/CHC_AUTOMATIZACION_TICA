import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property string iconName: ""
    property bool primary: false
    property bool subtle: false
    implicitHeight: 40
    implicitWidth: contentItem.implicitWidth + 30
    leftPadding: 15
    rightPadding: 15
    opacity: enabled ? 1 : 0.4
    hoverEnabled: true
    background: Rectangle {
        radius: 8
        color: control.primary ? (control.hovered ? "#f5ba9b" : Theme.accent) : control.hovered ? Theme.hover : control.subtle ? "transparent" : Theme.surface
        border.color: control.primary || control.subtle ? "transparent" : Theme.border
        border.width: control.activeFocus ? 2 : 1
    }
    contentItem: RowLayout {
        spacing: 8
        Icon { visible: control.iconName !== ""; name: control.iconName; implicitWidth: 17; implicitHeight: 17; tint: control.primary ? "#201a17" : Theme.text }
        Text { text: control.text; color: control.primary ? "#201a17" : Theme.text; font.family: Theme.family; font.pixelSize: 12; font.weight: Font.DemiBold }
    }
}
