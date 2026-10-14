import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

ScrollView {
    id: page
    objectName: "modulePage"
    property var info: demo.selectedModule
    property string statusText: info.status === "running" ? "En simulación" : info.status === "paused" ? "Pausado" : info.status === "completed" ? "Completado" : info.loaded ? "Listo para simular" : "Sin base de prueba"
    property real ratio: info.total ? info.progress / info.total : 0
    clip: true
    contentWidth: availableWidth
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ColumnLayout {
        width: page.availableWidth
        spacing: 22
        RowLayout {
            Layout.fillWidth: true; spacing: 16
            Rectangle {
                width: 56; height: 56; radius: 14; color: Qt.alpha(page.info.color || "#8da4bc", 0.12)
                Icon { anchors.centerIn: parent; name: page.info.icon || "grid"; tint: page.info.color || Theme.accent; width: 29; height: 29 }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                Text { text: page.info.title || ""; color: Theme.text; font.family: Theme.family; font.pixelSize: 29; font.weight: Font.DemiBold }
                Text { text: page.info.description || ""; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
            ActionButton { text: "Reiniciar"; iconName: "reset"; onClicked: demo.resetDemo(); enabled: page.info.loaded || false }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 46; radius: 8; color: Theme.accentTint
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16; spacing: 10
                Icon { name: "info"; width: 18; height: 18; tint: Theme.accent }
                Text { text: "Espacio de prueba. Las acciones usan datos de ejemplo y no realizan consultas a TICA."; color: Theme.accent; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 18; Layout.alignment: Qt.AlignTop
            Panel {
                Layout.preferredWidth: 310; Layout.maximumWidth: 350; Layout.fillWidth: true; implicitHeight: 366; Layout.alignment: Qt.AlignTop
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 22; spacing: 16
                    RowLayout {
                        Text { text: "Preparar simulación"; color: Theme.text; font.family: Theme.family; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        Icon { name: "settings"; width: 18; height: 18 }
                    }
                    Text { text: page.info.inputLabel || "Base de prueba"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: 91; radius: 8; color: Theme.raised; border.color: page.info.loaded ? Qt.alpha(Theme.success, 0.5) : Theme.border
                        Column {
                            anchors.centerIn: parent; spacing: 7
                            Icon { anchors.horizontalCenter: parent.horizontalCenter; name: page.info.loaded ? "check" : "folder"; tint: page.info.loaded ? Theme.success : Theme.faint; width: 22; height: 22 }
                            Text { text: page.info.loaded ? "Base de ejemplo cargada" : "Selecciona una base de prueba"; color: page.info.loaded ? Theme.success : Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; text: page.info.loaded ? "240 registros · datos sintéticos" : page.info.format || ""; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10 }
                        }
                    }
                    ActionButton { Layout.fillWidth: true; text: page.info.loaded ? "Volver a cargar ejemplo" : "Cargar base de ejemplo"; iconName: "plus"; enabled: page.info.status !== "running"; onClicked: demo.loadSample() }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                    RowLayout {
                        Text { text: "Trabajadores de prueba"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true }
                        Text { text: String(page.info.workers || 2).padStart(2, "0"); color: Theme.text; font.family: Theme.family; font.pixelSize: 13; font.weight: Font.DemiBold }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Repeater {
                            model: 4
                            Button {
                                required property int index
                                Layout.fillWidth: true; implicitHeight: 30; text: String(index + 1)
                                enabled: page.info.status !== "running"
                                background: Rectangle { radius: 6; color: page.info.workers === parent.index + 1 ? Theme.accentTint : Theme.raised; border.color: page.info.workers === parent.index + 1 ? Theme.accent : Theme.border }
                                contentItem: Text { text: parent.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: Theme.text; font.family: Theme.family; font.pixelSize: 11 }
                                onClicked: demo.setWorkers(index + 1)
                            }
                        }
                    }
                    Text { text: "Cada módulo conserva su propio estado de prueba."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                }
            }
            Panel {
                Layout.fillWidth: true; implicitHeight: 366; Layout.alignment: Qt.AlignTop
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 24; spacing: 15
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Estado de la ejecución"; color: Theme.text; font.family: Theme.family; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        Rectangle {
                            implicitWidth: statusLabel.implicitWidth + 22; implicitHeight: 26; radius: 6; color: page.info.status === "running" ? Theme.accentTint : Theme.raised
                            Text { id: statusLabel; anchors.centerIn: parent; text: page.statusText; color: page.info.status === "running" ? Theme.accent : Theme.muted; font.family: Theme.family; font.pixelSize: 10 }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; Layout.topMargin: 6
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 2
                            Text { text: String(page.info.progress || 0); color: Theme.text; font.family: Theme.family; font.pixelSize: 51; font.weight: Font.DemiBold }
                            Text { text: "de " + (page.info.loaded ? page.info.total : "—") + " registros de ejemplo"; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12 }
                        }
                        Rectangle {
                            width: 84; height: 84; radius: 42; color: "transparent"; border.width: 4; border.color: page.info.status === "completed" ? Theme.success : Theme.border
                            Text { anchors.centerIn: parent; text: Math.round(page.ratio * 100) + "%"; color: page.info.status === "completed" ? Theme.success : Theme.text; font.family: Theme.family; font.pixelSize: 22; font.weight: Font.DemiBold }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true; height: 6; radius: 3; color: Theme.raised
                        Rectangle { width: parent.width * page.ratio; height: parent.height; radius: 3; color: page.info.status === "completed" ? Theme.success : Theme.accent; Behavior on width { NumberAnimation { duration: 220 } } }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 30
                        ColumnLayout {
                            Text { text: "Confirmados"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10 }
                            Text { text: String(page.info.progress || 0); color: Theme.success; font.family: Theme.family; font.pixelSize: 20; font.weight: Font.DemiBold }
                        }
                        ColumnLayout {
                            Text { text: "Pendientes"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10 }
                            Text { text: page.info.loaded ? String(page.info.total - page.info.progress) : "—"; color: Theme.text; font.family: Theme.family; font.pixelSize: 20; font.weight: Font.DemiBold }
                        }
                        ColumnLayout {
                            Text { text: "Errores"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10 }
                            Text { text: "0"; color: Theme.text; font.family: Theme.family; font.pixelSize: 20; font.weight: Font.DemiBold }
                        }
                        Item { Layout.fillWidth: true }
                    }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 10
                        ActionButton { Layout.fillWidth: true; primary: true; text: page.info.status === "paused" ? "Continuar demo" : "Iniciar demo"; iconName: "play"; enabled: (page.info.loaded || false) && page.info.status !== "running" && page.info.status !== "completed"; onClicked: demo.startDemo() }
                        ActionButton { text: "Pausar"; iconName: "pause"; enabled: page.info.status === "running"; onClicked: demo.pauseDemo() }
                    }
                }
            }
        }
        Panel {
            Layout.fillWidth: true; implicitHeight: resultsColumn.implicitHeight + 40
            ColumnLayout {
                id: resultsColumn
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 20; spacing: 14
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 4
                        Text { text: "Vista de resultados"; color: Theme.text; font.family: Theme.family; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Muestra de los primeros 8 registros sintéticos"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
                    }
                    ActionButton { text: "Exportar demo"; iconName: "download"; enabled: page.info.progress > 0; onClicked: demo.exportDemo() }
                }
                Rectangle {
                    Layout.fillWidth: true; height: 33; radius: 5; color: Theme.raised
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                        Text { text: "Nº"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.preferredWidth: 38 }
                        Text { text: "IDENTIFICADOR"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.preferredWidth: 170 }
                        Text { text: "TIPO DE REGISTRO"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.fillWidth: true }
                        Text { text: "ESTADO"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.preferredWidth: 125 }
                        Text { text: "TIEMPO"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.preferredWidth: 65 }
                    }
                }
                Item {
                    visible: !page.info.loaded
                    Layout.fillWidth: true; implicitHeight: 103
                    Column {
                        anchors.centerIn: parent; spacing: 9
                        Icon { anchors.horizontalCenter: parent.horizontalCenter; name: "database"; width: 25; height: 25; tint: Theme.faint }
                        Text { text: "Carga una base de ejemplo para explorar los resultados."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12 }
                    }
                }
                Repeater {
                    model: demo.previewRows
                    ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true; spacing: 9
                        RowLayout {
                            Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12
                            Text { text: parent.parent.modelData.number; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; Layout.preferredWidth: 38 }
                            Text { text: parent.parent.modelData.identifier; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; Layout.preferredWidth: 170 }
                            Text { text: parent.parent.modelData.category; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            Text { text: parent.parent.modelData.status; color: text === "Confirmado" ? Theme.success : text === "En proceso" ? Theme.accent : Theme.faint; font.family: Theme.family; font.pixelSize: 11; Layout.preferredWidth: 125 }
                            Text { text: parent.parent.modelData.time; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; Layout.preferredWidth: 65 }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
                    }
                }
            }
        }
        Panel {
            Layout.fillWidth: true; implicitHeight: logColumn.implicitHeight + 40
            ColumnLayout {
                id: logColumn
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 20; spacing: 12
                Text { text: "Registro de actividad"; color: Theme.text; font.family: Theme.family; font.pixelSize: 15; font.weight: Font.DemiBold }
                Text { text: "Aún no hay actividad en este módulo."; visible: !page.info.events || page.info.events.length === 0; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11 }
                ActivityView {
                    Layout.fillWidth: true; Layout.preferredHeight: 160
                    model: demo.selectedActivityModel
                }
            }
        }
    }
}
