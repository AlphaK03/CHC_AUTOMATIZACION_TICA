import QtQuick
import QtQuick.Controls

Button {
    id: nav
    property string label: ""
    property string iconName: "grid"
    property color iconColor: Theme.muted
    property bool selected: false
    property bool expanded: true
    implicitHeight: 46
    hoverEnabled: true
    Accessible.name: label
    ToolTip.visible: hovered && !expanded
    ToolTip.text: label
    ToolTip.delay: 350
    background: Rectangle {
        radius: 8
        color: nav.selected ? Theme.accentTint : nav.hovered ? Theme.hover : "transparent"
        Rectangle { width: 3; height: 20; radius: 1.5; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; color: Theme.accent; visible: nav.selected }
        border.color: nav.activeFocus ? Theme.accent : "transparent"
    }
    contentItem: Item {
        Icon { x: 13; anchors.verticalCenter: parent.verticalCenter; name: nav.iconName; tint: nav.selected ? Theme.accent : nav.iconColor; width: 21; height: 21 }
        Text { x: 47; anchors.verticalCenter: parent.verticalCenter; width: Math.max(0, parent.width - 64); text: nav.label; visible: nav.expanded; elide: Text.ElideRight; color: nav.selected ? Theme.accent : Theme.muted; font.family: Theme.family; font.pixelSize: 13; font.weight: nav.selected ? Font.DemiBold : Font.Normal }
    }
}
