import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ListView {
    id: activity
    objectName: "activityView"
    clip: true
    spacing: 6
    property bool consoleStyle: false
    boundsBehavior: Flickable.StopAtBounds
    property bool followLatest: true
    property bool restoreQueued: false
    function cancelFollowing() {
        followLatest = false
        followTimer.stop()
        restoreQueued = false
    }
    onMovementStarted: cancelFollowing()
    function followTop() {
        activity.forceLayout()
        activity.positionViewAtBeginning()
    }
    Timer {
        id: followTimer
        interval: 0
        onTriggered: {
            activity.restoreQueued = false
            if (activity.followLatest && !activity.moving && !verticalBar.pressed) activity.followTop()
        }
    }
    Connections {
        target: activity.model
        function onBeforeChange() {
            if (!activity.restoreQueued) activity.followLatest = activity.atYBeginning && !activity.moving && !verticalBar.pressed
        }
        function onAfterChange() {
            if (activity.restoreQueued) return
            activity.restoreQueued = true
            // Un Timer hijo se cancela al abandonar/cerrar esta página.
            followTimer.start()
        }
    }
    ScrollBar.vertical: ScrollBar {
        id: verticalBar
        onPressedChanged: if (pressed) activity.cancelFollowing()
    }
    delegate: RowLayout {
        required property var eventData
        width: ListView.view.width - 12
        Text { text: parent.eventData.time || ""; color: activity.consoleStyle ? "#94acc2" : Theme.faint; font.family: "Consolas"; font.pixelSize: activity.consoleStyle ? 11 : 10; Layout.preferredWidth: 60; Layout.alignment: Qt.AlignTop; textFormat: Text.PlainText }
        Text { visible: activity.consoleStyle; text: parent.eventData.level || "INFO"; color: ["ERROR","CRITICAL"].indexOf(text)>=0 ? "#ffadb5" : text === "WARNING" ? "#f0c783" : "#8bb8e0"; font.family: "Consolas"; font.pixelSize: 10; Layout.preferredWidth: 52; Layout.alignment: Qt.AlignTop; textFormat: Text.PlainText }
        Text { text: parent.eventData.message || ""; color: parent.eventData.level === "SUCCESS" ? "#80dcba" : parent.eventData.level === "WARNING" ? "#f0c783" : ["ERROR","CRITICAL"].indexOf(parent.eventData.level)>=0 ? "#ffadb5" : activity.consoleStyle ? "#d4e0ed" : Theme.muted; font.family: activity.consoleStyle ? "Consolas" : Theme.family; font.pixelSize: activity.consoleStyle ? 12 : 11; wrapMode: Text.WordWrap; Layout.fillWidth: true; textFormat: Text.PlainText }
    }
}
