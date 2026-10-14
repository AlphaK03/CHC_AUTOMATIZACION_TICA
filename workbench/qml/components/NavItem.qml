import QtQuick
import QtQuick.Controls

Button {
    id: nav
    property string label: ""
    property string iconName: "grid"
    property color iconColor: Theme.muted
    property bool selected: false
    property bool expanded: true
    property bool horizontal: false
    property string helpText: label
    implicitHeight: 46
    leftPadding: horizontal ? 0 : padding
    rightPadding: horizontal ? 0 : padding
    hoverEnabled: true
    Accessible.name: label
    ToolTip.visible: hovered && (!expanded || horizontal)
    ToolTip.text: helpText
    ToolTip.delay: 350
    background: Rectangle {
        radius: 8
        color: nav.selected ? Theme.accentTint : nav.hovered ? Theme.hover : "transparent"
        Rectangle { width: 3; height: 20; radius: 1.5; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; color: Theme.accent; visible: nav.selected && !nav.horizontal }
        Rectangle { height: 3; radius: 1.5; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.leftMargin: 12; anchors.rightMargin: 12; color: Theme.accent; visible: nav.selected && nav.horizontal }
        border.color: nav.activeFocus ? Theme.accent : "transparent"
    }
    contentItem: Item {
        Icon { x: nav.horizontal ? 10 : 13; anchors.verticalCenter: parent.verticalCenter; name: nav.iconName; tint: nav.selected ? Theme.accent : nav.iconColor; width: nav.horizontal ? 18 : 21; height: width }
        Text { x: nav.horizontal ? 36 : 47; anchors.verticalCenter: parent.verticalCenter; width: Math.max(0, parent.width - (nav.horizontal ? 44 : 64)); text: nav.label; visible: nav.expanded; elide: Text.ElideRight; color: nav.selected ? Theme.accent : Theme.muted; font.family: Theme.family; font.pixelSize: nav.horizontal ? 12 : 13; font.weight: nav.selected ? Font.DemiBold : Font.Normal }
    }
}
