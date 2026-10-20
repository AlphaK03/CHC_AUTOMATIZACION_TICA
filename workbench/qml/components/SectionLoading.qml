import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Panel {
    id: waiting
    objectName: "sectionLoading"
    property bool loading: false
    property string title: ""
    visible: loading
    implicitHeight: 270
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(440,parent.width-40)
        spacing: 14
        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 68; implicitHeight: 68
            BusyIndicator { anchors.fill: parent; running: waiting.loading && waiting.visible; palette.dark: Theme.accent }
            BrandMark { anchors.centerIn: parent; width: 32; height: 32 }
        }
        Text { text: "Cargando " + waiting.title; color: Theme.text; font.family: Theme.family; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
        Text { text: "Preparando las bases y el progreso guardado.\nPuedes seguir usando las demás secciones."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap }
    }
}
