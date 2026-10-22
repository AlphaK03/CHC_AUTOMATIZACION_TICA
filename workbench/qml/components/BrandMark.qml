import QtQuick

Rectangle {
    implicitWidth: 40
    implicitHeight: 40
    color: "#ffffff"
    radius: width * 0.22
    Accessible.role: Accessible.Graphic
    Accessible.name: "CHC Consultores"

    Image {
        objectName: "chcBrandImage"
        anchors.fill: parent
        anchors.margins: parent.width * 0.08
        source: "../../assets/branding/chc-symbol.svg"
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }
}
