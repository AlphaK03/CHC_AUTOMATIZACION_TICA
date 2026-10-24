import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: progress
    property string title: "Avance"
    property string unit: "consultas"
    property int total: 0
    property int succeeded: 0
    property int pending: 0
    property int running: 0
    property int invalid: 0
    property int excluded: 0
    property int empty: 0
    property int rows: -1
    property bool emptyAddsToCompleted: false
    property bool showEmpty: false
    property bool busy: false
    property bool compact: false
    property bool showMetrics: true
    readonly property int completed: succeeded + (emptyAddsToCompleted ? empty : 0)
    readonly property real fraction: total > 0 ? Math.min(1,Math.max(0,completed / total)) : 0
    readonly property string statusText: total === 0 ? "Sin iniciar" : completed === total ? "Completado" :
        completed + excluded === total ? "Con exclusiones" : running > 0 ? "Descargando" :
        busy ? "En espera" : "Con pendientes"
    readonly property color statusColor: completed === total && total > 0 ? Theme.success :
        running > 0 || busy ? Theme.accent : Theme.muted
    readonly property var segments: [
        {value:completed,label:"Confirmados",color:Theme.success},
        {value:running,label:"En curso",color:Theme.accent},
        {value:invalid,label:"Por revisar",color:Theme.warning},
        {value:excluded,label:"Excluidos",color:Theme.faint}
    ]
    readonly property var metrics: [
        {label:"Guardados",value:succeeded,color:Theme.success,shown:!compact},
        {label:"Pendientes",value:pending,color:Theme.muted,shown:true},
        {label:"En curso",value:running,color:running ? Theme.accent : Theme.muted,shown:true},
        {label:"Por revisar",value:invalid,color:Theme.warning,shown:invalid > 0},
        {label:"Excluidos",value:excluded,color:Theme.faint,shown:excluded > 0},
        {label:emptyAddsToCompleted ? "Vacíos" : "Sin líneas",value:empty,color:Theme.muted,shown:showEmpty},
        {label:"Filas confirmadas",value:rows,color:Theme.text,shown:rows >= 0}
    ]
    implicitHeight: content.implicitHeight
    Accessible.role: Accessible.ProgressBar
    Accessible.name: title + ": " + completed + "/" + total + " " + unit + ", " + statusText
    function number(value) { return Number(value).toLocaleString(Qt.locale("es"),"f",0) }
    function segmentWidth(index) {
        if (total <= 0) return 0
        let before = 0
        for(let i = 0; i < index; ++i) before += segments[i].value
        return Math.max(0,Math.min(segments[index].value,total - before)) / total
    }

    ColumnLayout {
        id: content
        width: parent.width; spacing: progress.compact ? 7 : 9
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Text {
                text: progress.title; color: progress.compact ? Theme.text : Theme.muted
                font.family: Theme.family; font.pixelSize: 12; font.weight: Font.DemiBold
                Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight
                ToolTip.visible: titleHover.hovered; ToolTip.text: text
                HoverHandler { id: titleHover }
            }
            Text {
                objectName: "progressModeCount"; visible: progress.compact
                text: progress.number(progress.completed) + "/" + progress.number(progress.total)
                color: Theme.text; font.family: Theme.family; font.pixelSize: 18; font.weight: Font.DemiBold
            }
            Rectangle {
                implicitWidth: stateLabel.implicitWidth + 16; implicitHeight: 23; radius: 6
                color: Qt.rgba(progress.statusColor.r,progress.statusColor.g,progress.statusColor.b,0.10)
                Text {
                    id: stateLabel; objectName: "progressStatus"; anchors.centerIn: parent
                    text: progress.statusText; color: progress.statusColor
                    font.family: Theme.family; font.pixelSize: 10; font.weight: Font.DemiBold
                }
            }
        }
        RowLayout {
            visible: !progress.compact; Layout.fillWidth: true; spacing: 8
            Text {
                objectName: "progressCount"; text: progress.number(progress.completed)
                color: Theme.text; font.family: Theme.family; font.pixelSize: 30; font.weight: Font.DemiBold
            }
            Text { text: "/ " + progress.number(progress.total); color: Theme.muted; font.family: Theme.family; font.pixelSize: 18 }
            Text { text: progress.unit; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight }
            Text { text: (100 * progress.fraction).toFixed(1) + "%"; color: Theme.success; font.family: Theme.family; font.pixelSize: 18; font.weight: Font.DemiBold }
        }
        Rectangle {
            id: track; objectName: "progressTrack"
            Layout.fillWidth: true; implicitHeight: progress.compact ? 5 : 7
            radius: height / 2; color: Theme.raised; clip: true
            Row {
                height: parent.height
                Repeater {
                    model: progress.segments
                    Rectangle {
                        required property var modelData
                        required property int index
                        width: track.width * progress.segmentWidth(index); height: track.height; radius: height / 2
                        color: modelData.color
                    }
                }
            }
            ToolTip.visible: trackHover.hovered
            ToolTip.text: progress.completed + " confirmados · " + progress.pending + " pendientes · " + progress.running + " en curso" +
                (progress.invalid ? " · " + progress.invalid + " por revisar" : "") + (progress.excluded ? " · " + progress.excluded + " excluidos" : "")
            HoverHandler { id: trackHover }
        }
        Flow {
            visible: progress.showMetrics
            Layout.fillWidth: true; Layout.preferredHeight: implicitHeight
            spacing: progress.compact ? 12 : 24
            Repeater {
                model: progress.metrics
                Item {
                    required property var modelData
                    visible: modelData.shown
                    implicitWidth: progress.compact ? inlineMetric.implicitWidth : Math.max(metricValue.implicitWidth,metricLabel.implicitWidth)
                    implicitHeight: progress.compact ? 18 : 38
                    Row {
                        id: inlineMetric; visible: progress.compact; spacing: 4
                        Text { text: progress.number(modelData.value); color: modelData.color; font.family: Theme.family; font.pixelSize: 12; font.weight: Font.DemiBold }
                        Text { text: modelData.label.toLowerCase(); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                    }
                    Text { id: metricValue; visible: !progress.compact; text: progress.number(modelData.value); color: modelData.color; font.family: Theme.family; font.pixelSize: 19; font.weight: Font.DemiBold }
                    Text { id: metricLabel; visible: !progress.compact; y: 25; text: modelData.label; color: Theme.muted; font.family: Theme.family; font.pixelSize: 10 }
                }
            }
        }
    }
}
