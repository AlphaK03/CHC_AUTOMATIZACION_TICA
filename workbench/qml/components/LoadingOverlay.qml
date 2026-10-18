import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: waiting
    objectName: "baseLoadingOverlay"
    property bool loading: false
    property var moduleNames: []
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(440, parent ? parent.width - 40 : 440)
    padding: 28
    modal: true
    dim: true
    focus: true
    closePolicy: Popup.NoAutoClose
    visible: loading
    z: 10000
    Overlay.modal: Rectangle { color: Theme.dark ? "#b30a0e14" : "#990f172a" }
    background: Rectangle { color: Theme.surface; radius: 16; border.color: Theme.border }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 180 }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: 180; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 140 } }
    contentItem: ColumnLayout {
        Accessible.role: Accessible.AlertMessage
        Accessible.name: "Cargando bases de datos"
        spacing: 16
        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 76; implicitHeight: 76
            BusyIndicator { anchors.fill: parent; running: waiting.visible; palette.dark: Theme.accent }
            BrandMark { anchors.centerIn: parent; width: 36; height: 36 }
        }
        Text {
            text: "Cargando bases de datos"
            color: Theme.text; font.family: Theme.family; font.pixelSize: 20; font.weight: Font.DemiBold
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        }
        Text {
            objectName: "baseLoadingModules"
            text: waiting.moduleNames.join(" · ")
            color: Theme.accent; font.family: Theme.family; font.pixelSize: 13
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            Layout.minimumHeight: 38
        }
        Text {
            text: "Espera un momento. Todo estará listo para continuar al terminar la carga."
            color: Theme.muted; font.family: Theme.family; font.pixelSize: 12
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        }
    }
}
