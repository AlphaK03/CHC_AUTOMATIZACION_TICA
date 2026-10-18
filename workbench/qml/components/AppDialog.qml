import QtQuick
import QtQuick.Controls

Dialog {
    id: dialog
    parent: Overlay.overlay
    height: Math.min(implicitHeight, parent ? parent.height - 32 : implicitHeight)
    palette.window: Theme.surface
    palette.windowText: Theme.text
    palette.text: Theme.text
    palette.base: Theme.raised
    palette.button: Theme.raised
    palette.buttonText: Theme.text
    background: Panel {}
    header: Text {
        text: dialog.title; visible: text.length > 0
        textFormat: Text.PlainText
        leftPadding: dialog.leftPadding; rightPadding: dialog.rightPadding
        topPadding: 16; bottomPadding: 8
        color: Theme.text; font.family: Theme.family
        font.pixelSize: 15; font.weight: Font.DemiBold
        elide: Text.ElideRight
    }
    footer: DialogButtonBox {
        id: buttons
        visible: dialog.standardButtons !== Dialog.NoButton
        standardButtons: dialog.standardButtons
        alignment: Qt.AlignRight
        padding: 12
        background: Rectangle { color: Theme.surface }
        function translateClose() {
            const close = buttons.standardButton(DialogButtonBox.Close)
            if (close) close.text = "Cerrar"
        }
        onStandardButtonsChanged: Qt.callLater(translateClose)
        Component.onCompleted: Qt.callLater(translateClose)
    }
}
