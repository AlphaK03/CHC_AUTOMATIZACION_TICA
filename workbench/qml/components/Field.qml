import QtQuick
import QtQuick.Controls

TextField {
    id: control
    implicitHeight: 38
    color: Theme.text
    placeholderTextColor: Theme.faint
    font.family: Theme.family
    font.pixelSize: 12
    padding: 11
    selectByMouse: true
    background: Rectangle { radius: 7; color: Theme.raised; border.color: control.activeFocus ? Theme.accent : Theme.border }
}
