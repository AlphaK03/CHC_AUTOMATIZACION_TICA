import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

Dialog {
    id: calendarDialog
    objectName: "detailsDailyCalendar"
    title: "Calendario de Detalles"
    modal: true; padding: 20
    palette.windowText: Theme.text; palette.buttonText: Theme.text; palette.button: Theme.raised
    background: Panel {}
    property var selectedDay: ({})
    header: Rectangle {
        implicitHeight: 44; color: Theme.surface
        Text { anchors.left: parent.left; anchors.leftMargin: 20; anchors.verticalCenter: parent.verticalCenter; text: calendarDialog.title; color: Theme.text; font.family: Theme.family; font.pixelSize: 13; font.weight: Font.DemiBold }
    }
    footer: RowLayout {
        implicitHeight: 56
        Item { Layout.fillWidth: true }
        ActionButton { text: "Cerrar"; Layout.rightMargin: 20; onClicked: calendarDialog.close() }
    }
    Connections {
        target: details
        function onChanged() {
            if(calendarDialog.selectedDay.date) {
                for(let item of details.daily.days) if(item.date === calendarDialog.selectedDay.date) { calendarDialog.selectedDay = item; break }
            }
        }
    }
    function shiftMonth(amount) {
        const parts = details.daily.month.split("-")
        const date = new Date(Number(parts[0]), Number(parts[1]) - 1 + amount, 1)
        details.loadCalendar(date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2,"0"))
        selectedDay = ({})
    }
    contentItem: ColumnLayout {
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ActionButton { text: "‹"; enabled: details.ready; onClicked: calendarDialog.shiftMonth(-1) }
            Text { text: details.daily.monthLabel; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
            ActionButton { text: "›"; enabled: details.ready; onClicked: calendarDialog.shiftMonth(1) }
        }
        GridLayout {
            columns: 7; columnSpacing: 7; rowSpacing: 7; Layout.fillWidth: true
            Repeater {
                model: ["L", "M", "X", "J", "V", "S", "D"]
                Text { required property string modelData; text: modelData; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
            }
            Repeater {
                model: details.daily.days
                Button {
                    id: dayButton
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredHeight: 43
                    enabled: !!modelData.day
                    opacity: ["future", "outside"].indexOf(modelData.state) >= 0 ? .35 : 1
                    text: modelData.day ? String(modelData.day) : ""
                    background: Rectangle {
                        radius: 7
                        color: !dayButton.modelData.day ? "transparent" : dayButton.modelData.state === "completed" ? Qt.alpha(Theme.success,.18) : ["downloading", "processing"].indexOf(dayButton.modelData.state) >= 0 ? Theme.accentTint : Theme.raised
                        border.color: dayButton.modelData.state === "completed" ? Theme.success : calendarDialog.selectedDay.date === dayButton.modelData.date ? Theme.accent : "transparent"
                    }
                    contentItem: Text { text: dayButton.text; color: dayButton.modelData.state === "completed" ? Theme.success : Theme.text; font.family: Theme.family; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: calendarDialog.selectedDay = modelData
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 16
            Text { text: "● Completado"; color: Theme.success; font.family: Theme.family; font.pixelSize: 11 }
            Text { text: "● En curso"; color: Theme.accent; font.family: Theme.family; font.pixelSize: 11 }
            Text { text: "● Pendiente"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            text: calendarDialog.selectedDay.date ? calendarDialog.selectedDay.date + " · " + ({completed:"Completado",downloading:"Descargando base",processing:"Procesando",pending:"Pendiente",future:"Todavía no disponible",outside:"Fuera del período elegido"})[calendarDialog.selectedDay.state] + (calendarDialog.selectedDay.total ? " · " + calendarDialog.selectedDay.succeeded + " / " + calendarDialog.selectedDay.total + " guardados" : "") + (calendarDialog.selectedDay.error ? "\n" + calendarDialog.selectedDay.error : "") : "Selecciona un día para ver su estado."
            color: Theme.muted; font.family: Theme.family; font.pixelSize: 11
        }
    }
}
