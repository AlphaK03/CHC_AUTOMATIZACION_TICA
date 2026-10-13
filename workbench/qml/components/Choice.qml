import QtQuick
import QtQuick.Controls

CheckBox {
    id:control
    spacing:8
    implicitHeight:32
    font.family:Theme.family; font.pixelSize:12
    indicator:Rectangle {
        x:control.leftPadding; y:(control.height-height)/2
        width:18; height:18; radius:4
        color:control.checked ? Theme.accent : Theme.raised
        border.color:control.checked ? Theme.accent : Theme.border
        Text { anchors.centerIn:parent; text:"✓"; visible:control.checked; color:"#201a17"; font.pixelSize:14 }
    }
    contentItem:Text {
        text:control.text; font:control.font; color:control.enabled ? Theme.text : Theme.faint
        leftPadding:control.indicator.width+control.spacing
        verticalAlignment:Text.AlignVCenter; elide:Text.ElideRight
    }
}
