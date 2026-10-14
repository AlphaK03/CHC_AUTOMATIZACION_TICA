import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

Dialog {
    id: calendarDialog
    property var moduleBridge: null
    property var worker: moduleBridge || details
    objectName: "detailsDailyCalendar"
    title: "Calendario de " + worker.moduleTitle
    modal: true; padding: 20
    palette.windowText: Theme.text; palette.buttonText: Theme.text; palette.button: Theme.raised
    background: Panel {}
    property var selectedDay: ({})
    property string initialStart: ""
    property string initialEnd: ""
    property string rangeStart: ""
    property string rangeEnd: ""
    property bool choosingEnd: false
    signal rangeSelected(string start, string end)
    onOpened: { rangeStart = initialStart; rangeEnd = initialEnd; choosingEnd = false }
    function chooseDay(item) {
        selectedDay = item
        if(worker.busy || !item.available) return
        if(!choosingEnd) { rangeStart = item.date; rangeEnd = ""; choosingEnd = true }
        else {
            const first = rangeStart
            rangeStart = item.date < first ? item.date : first
            rangeEnd = item.date < first ? first : item.date
            choosingEnd = false
        }
    }
    function inRange(day) { return !!day && !!rangeStart && day >= rangeStart && day <= (rangeEnd || rangeStart) }
    function applyRange() {
        if(worker.busy || !rangeStart || !rangeEnd) return
        rangeSelected(rangeStart, rangeEnd)
        close()
    }
    header: Rectangle {
        implicitHeight: 44; color: Theme.surface
        Text { anchors.left: parent.left; anchors.leftMargin: 20; anchors.verticalCenter: parent.verticalCenter; text: calendarDialog.title; color: Theme.text; font.family: Theme.family; font.pixelSize: 13; font.weight: Font.DemiBold }
    }
    footer: RowLayout {
        implicitHeight: 56
        Text { Layout.leftMargin: 20; Layout.fillWidth: true; text: calendarDialog.rangeStart ? calendarDialog.rangeStart + " → " + (calendarDialog.rangeEnd || "…") : ""; color: Theme.text; font.family: Theme.family; font.pixelSize: 11 }
        ActionButton { objectName: "detailsApplyCalendarRange"; text: "Usar rango"; primary: true; enabled: !worker.busy && !!calendarDialog.rangeStart && !!calendarDialog.rangeEnd; onClicked: calendarDialog.applyRange() }
        ActionButton { text: "Cerrar"; Layout.rightMargin: 20; onClicked: calendarDialog.close() }
    }
    Connections {
        target: worker
        function onChanged() {
            if(calendarDialog.selectedDay.date) {
                for(let item of worker.daily.days) if(item.date === calendarDialog.selectedDay.date) { calendarDialog.selectedDay = item; break }
            }
        }
    }
    function shiftMonth(amount) {
        const parts = worker.daily.month.split("-")
        const date = new Date(Number(parts[0]), Number(parts[1]) - 1 + amount, 1)
        worker.loadCalendar(date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2,"0"))
        selectedDay = ({})
    }
    contentItem: ColumnLayout {
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ActionButton { text: "‹"; enabled: worker.ready; onClicked: calendarDialog.shiftMonth(-1) }
            Text { text: worker.daily.monthLabel; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
            ActionButton { text: "›"; enabled: worker.ready; onClicked: calendarDialog.shiftMonth(1) }
        }
        GridLayout {
            columns: 7; columnSpacing: 7; rowSpacing: 7; Layout.fillWidth: true
            Repeater {
                model: ["L", "M", "X", "J", "V", "S", "D"]
                Text { required property string modelData; text: modelData; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
            }
            Repeater {
                model: worker.daily.days
                Button {
                    id: dayButton
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredHeight: 43
                    enabled: !!modelData.day && modelData.available === true
                    opacity: !modelData.day || modelData.available === true ? 1 : .35
                    text: modelData.day ? String(modelData.day) : ""
                    background: Rectangle {
                        radius: 7
                        color: !dayButton.modelData.day ? "transparent" : calendarDialog.inRange(dayButton.modelData.date) ? Theme.accentTint : dayButton.modelData.state === "completed" ? Qt.alpha(Theme.success,.18) : ["downloading", "processing", "omitted"].indexOf(dayButton.modelData.state) >= 0 ? Theme.accentTint : Theme.raised
                        border.color: calendarDialog.inRange(dayButton.modelData.date) ? Theme.accent : dayButton.modelData.state === "completed" ? Theme.success : calendarDialog.selectedDay.date === dayButton.modelData.date ? Theme.accent : "transparent"
                    }
                    contentItem: Text { text: dayButton.text; color: dayButton.modelData.state === "completed" ? Theme.success : Theme.text; font.family: Theme.family; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: calendarDialog.chooseDay(modelData)
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 16
            Text { text: "● Completado"; color: Theme.success; font.family: Theme.family; font.pixelSize: 11 }
            Text { text: "● En curso"; color: Theme.accent; font.family: Theme.family; font.pixelSize: 11 }
            Text { text: "● Pendiente"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
            Text { text: "● Omitido"; color: Theme.accent; font.family: Theme.family; font.pixelSize: 11 }
        }
        RowLayout {
            Layout.fillWidth:true
            ActionButton { objectName:"retryCalendarDay"; text:"Reintentar día"; enabled:worker.ready && !worker.busy && !!calendarDialog.selectedDay.date && calendarDialog.selectedDay.available; onClicked:worker.retryDay(calendarDialog.selectedDay.date) }
            ActionButton { objectName:"retryCalendarMonth"; text:"Reintentar mes"; enabled:worker.ready && !worker.busy; onClicked:worker.retryMonth(worker.daily.month) }
        }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            text: calendarDialog.selectedDay.date ? calendarDialog.selectedDay.date + " · " + ({completed:"Completado",downloading:"Descargando base",processing:"Procesando",pending:"Pendiente",omitted:"Omitido: pendientes para revisión manual",future:"Todavía no disponible",outside:"Sin ejecutar"})[calendarDialog.selectedDay.state] + (calendarDialog.selectedDay.total ? " · " + calendarDialog.selectedDay.succeeded + " / " + calendarDialog.selectedDay.total + " guardados" + (calendarDialog.selectedDay.empty ? " · " + calendarDialog.selectedDay.empty + " vacíos" : "") : "") + (calendarDialog.selectedDay.error ? "\n" + calendarDialog.selectedDay.error : "") : "Elige el primer y último día del rango."
            color: Theme.muted; font.family: Theme.family; font.pixelSize: 11
        }
    }
}
