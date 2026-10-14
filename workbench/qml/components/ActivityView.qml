import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ListView {
    id: activity
    objectName: "activityView"
    clip: true
    spacing: 6
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
        Text { text: parent.eventData.time || ""; color: Theme.faint; font.family: "Consolas"; font.pixelSize: 10; Layout.preferredWidth: 65 }
        Text { text: parent.eventData.message || ""; color: parent.eventData.level === "SUCCESS" ? Theme.success : parent.eventData.level === "WARNING" ? Theme.accent : ["ERROR","CRITICAL"].indexOf(parent.eventData.level)>=0 ? "#ef9ea2" : Theme.muted; font.family: Theme.family; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }
}
