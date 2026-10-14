import QtQuick
import QtQuick.Layouts

RowLayout {
    required property QtObject inspector
    visible: inspector.running || inspector.status !== ""
    spacing: 8
    Text { text: inspector.error || inspector.status; color: inspector.error ? Theme.accent : Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    ActionButton { text: "Cerrar revisión"; visible: inspector.running; onClicked: inspector.stop() }
}
