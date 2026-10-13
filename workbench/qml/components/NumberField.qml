import QtQuick
import QtQuick.Controls

SpinBox {
    id:control
    implicitHeight:38
    implicitWidth:115
    editable:true
    palette.text:Theme.text
    palette.buttonText:Theme.text
    palette.base:Theme.raised
    textFromValue:function(value,locale) { return value.toString() }
    valueFromText:function(text,locale) { return parseInt(text) || 0 }
    background:Rectangle { color:Theme.raised; radius:7; border.color:Theme.border }
    contentItem:TextInput {
        text:control.displayText
        font.family:Theme.family; font.pixelSize:12; color:Theme.text
        horizontalAlignment:Qt.AlignHCenter; verticalAlignment:Qt.AlignVCenter
        readOnly:!control.editable; validator:control.validator
        selectionColor:Theme.accentTint; selectedTextColor:Theme.text
    }
    up.indicator:Rectangle {
        x:control.width-width; width:28; height:control.height; color:"transparent"
        Text { anchors.centerIn:parent; text:"+"; color:Theme.muted; font.pixelSize:18 }
    }
    down.indicator:Rectangle {
        width:28; height:control.height; color:"transparent"
        Text { anchors.centerIn:parent; text:"−"; color:Theme.muted; font.pixelSize:18 }
    }
}
