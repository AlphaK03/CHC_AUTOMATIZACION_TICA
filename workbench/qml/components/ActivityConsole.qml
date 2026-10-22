import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: terminal
    objectName: "activityConsole"
    property var activityModel
    property var monitor: null
    property string activeText: ""
    property string activeObjectName: ""
    property bool expanded: false
    signal clearRequested()
    color: "#101923"; radius: 8; border.color: "#304354"
    implicitHeight: expanded ? 420 : 270
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 12; spacing: 7
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Rectangle { implicitWidth: 6; implicitHeight: 6; radius: 3; color: terminal.monitor && terminal.monitor.running ? "#71d9b4" : "#738399" }
            Text { text: "Actividad"; color: "#f2f6fb"; font.pixelSize: 12; font.weight: Font.DemiBold }
            Text { text: terminal.monitor ? terminal.monitor.status : ""; color: "#a8bbcd"; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
            ToolButton {
                id: expandButton; text: terminal.expanded ? "Reducir" : "Ampliar"; implicitHeight: 26
                onClicked: terminal.expanded = !terminal.expanded
                background: Rectangle { radius: 4; color: expandButton.hovered ? "#2c4054" : "#1b2a39" }
                contentItem: Text { text: expandButton.text; color: "#c6dcf0"; font.pixelSize: 11; verticalAlignment: Text.AlignVCenter }
            }
            ToolButton {
                id: clearButton; text: "Limpiar"; implicitHeight: 26; onClicked: terminal.clearRequested()
                background: Rectangle { radius: 4; color: clearButton.hovered ? "#2c4054" : "#1b2a39" }
                contentItem: Text { text: clearButton.text; color: "#c6dcf0"; font.pixelSize: 11; verticalAlignment: Text.AlignVCenter }
            }
        }
        Text {
            objectName: terminal.activeObjectName
            visible: terminal.activeText !== ""; text: terminal.activeText
            color: "#8fd1ed"; font.family: "Consolas"; font.pixelSize: 11
            Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText
        }
        ListView {
            id: operations
            objectName: "activityOperations"
            visible: count > 0
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(contentHeight,terminal.expanded ? 130 : 76)
            model: terminal.monitor ? terminal.monitor.operationModel : null
            clip: true; spacing: 3; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: Text {
                required property var operation
                width: ListView.view.width-14
                text: "› " + operation.label + (operation.subject ? " · " + operation.subject : "") + " · " + operation.elapsed + " s"
                textFormat: Text.PlainText; wrapMode: Text.WordWrap
                color: "#9de4cc"; font.family: "Consolas"; font.pixelSize: 12
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: "#304354" }
        ActivityView {
            id: history
            Layout.fillWidth: true; Layout.fillHeight: true
            model: terminal.activityModel; consoleStyle: true
            Text { anchors.centerIn: parent; visible: history.count === 0; text: "Las etapas y los mensajes del motor aparecerán aquí."; color: "#9aafc2"; font.pixelSize: 11; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap }
        }
        Text { text: "Más reciente arriba · El tiempo indica espera; los resultados se confirman por separado."; color: "#8c9fb1"; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    }
}
