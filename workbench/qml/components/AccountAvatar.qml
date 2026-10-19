import QtQuick

Rectangle {
    id: avatar
    property string displayName: ""
    property string photoUrl: ""
    property bool connected: false
    property bool photoReady: false
    readonly property string initials: {
        const words = displayName.trim().split(/\s+/).filter(word => word.length > 0)
        if (!words.length) return ""
        if (words.length > 1) return (words[0][0] + words[words.length - 1][0]).toUpperCase()
        return words[0].split("@")[0].slice(0,2).toUpperCase()
    }
    implicitWidth: 38; implicitHeight: 38; radius: width / 2
    color: connected ? Theme.accentTint : Theme.raised
    border.color: connected ? Theme.accent : Theme.border
    onPhotoUrlChanged: { photoReady=false; if(photoUrl) portrait.loadImage(photoUrl); portrait.requestPaint() }
    Canvas {
        id: portrait; anchors.fill: parent; anchors.margins: 1
        Component.onCompleted: { if(avatar.photoUrl) loadImage(avatar.photoUrl) }
        onImageLoaded: { avatar.photoReady=isImageLoaded(avatar.photoUrl); requestPaint() }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx=getContext("2d");ctx.reset()
            if(!avatar.photoReady) return
            ctx.save();ctx.beginPath();ctx.arc(width/2,height/2,Math.min(width,height)/2,0,2*Math.PI);ctx.clip()
            ctx.drawImage(avatar.photoUrl,0,0,width,height);ctx.restore()
        }
    }
    Text {
        visible: !avatar.photoReady && avatar.connected && avatar.initials.length > 0
        anchors.centerIn: parent; text: avatar.initials; textFormat: Text.PlainText
        color: Theme.accent; font.family: Theme.family; font.pixelSize: Math.round(avatar.width*0.32); font.weight: Font.DemiBold
    }
    Icon { visible:!avatar.photoReady && (!avatar.connected || avatar.initials.length===0); anchors.centerIn:parent; name:"user"; tint:Theme.muted; width:avatar.width*0.55; height:width }
}
