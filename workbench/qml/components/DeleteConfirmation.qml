import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

AppDialog {
    id: dialog
    parent:Overlay.overlay
    property string details: ""
    property bool allowed: true
    signal confirmed(string confirmation)
    title: "Confirmar eliminación"
    modal: true; padding: 24
    palette.windowText: Theme.text
    background: Panel {}
    onOpened: { confirmation.text = ""; confirmation.forceActiveFocus() }
    contentItem: ColumnLayout {
        spacing: 14
        Text { text: dialog.details; textFormat: Text.PlainText; color: Theme.text; font.family: Theme.family; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Text { text: "Se conservará un respaldo antes de cambiar la base.\nEscribe BORRAR para confirmar."; color: Theme.accent; font.family: Theme.family; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Field { id: confirmation; objectName: "deleteConfirmationInput"; Layout.fillWidth: true; placeholderText: "BORRAR"; selectByMouse: true }
    }
    footer: RowLayout {
        ActionButton { objectName: "deleteCancel"; text: "Cancelar"; onClicked: dialog.close() }
        Item { Layout.fillWidth: true }
        ActionButton {
            objectName: "deleteConfirm"; text: "Confirmar eliminación"
            enabled: dialog.allowed && confirmation.text === "BORRAR"
            onClicked: {
                if (!enabled) return
                dialog.confirmed(confirmation.text)
                dialog.close()
            }
        }
    }
}
