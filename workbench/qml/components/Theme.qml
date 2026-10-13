pragma Singleton
import QtQuick

QtObject {
    property bool dark: true
    readonly property color background: dark ? "#10141b" : "#f3f5f7"
    readonly property color sidebar: dark ? "#151a23" : "#ffffff"
    readonly property color surface: dark ? "#1a202a" : "#ffffff"
    readonly property color raised: dark ? "#212935" : "#edf1f5"
    readonly property color hover: dark ? "#252e3b" : "#e7edf3"
    readonly property color border: dark ? "#2a323f" : "#e0e6ec"
    readonly property color text: dark ? "#edf0f5" : "#202a3a"
    readonly property color muted: dark ? "#99a6b8" : "#64748b"
    readonly property color faint: dark ? "#66758a" : "#8a98aa"
    readonly property color accent: dark ? "#f2aa83" : "#bc6339"
    readonly property color accentTint: dark ? "#332b29" : "#faece4"
    readonly property color success: dark ? "#7ed3b6" : "#258267"
    readonly property string family: "Segoe UI"
}
