import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    property string placeholder: "Seleccionar…"
    implicitHeight: 38
    palette.text: Theme.text
    palette.buttonText: Theme.text
    palette.base: Theme.surface
    palette.highlight: Theme.accentTint
    palette.highlightedText: Theme.accent
    font.family: Theme.family
    font.pixelSize: 12
    contentItem: Text { text: control.displayText || control.placeholder; color: control.displayText ? Theme.text : Theme.faint; font: control.font; verticalAlignment: Text.AlignVCenter; leftPadding: 11; rightPadding: 30; elide: Text.ElideRight }
    background: Rectangle { radius: 7; color: Theme.raised; border.color: control.activeFocus ? Theme.accent : Theme.border }
    indicator: Icon { x: control.width - 25; anchors.verticalCenter: parent.verticalCenter; width: 15; height: 15; rotation: 90; name: "chevron"; tint: Theme.muted }
}
