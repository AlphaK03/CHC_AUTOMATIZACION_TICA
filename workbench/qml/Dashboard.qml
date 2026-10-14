import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

ScrollView {
    id: dashboard
    objectName: "dashboardPage"
    clip: true
    contentWidth: availableWidth
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ColumnLayout {
        width: dashboard.availableWidth; spacing: 18
        MonthStart { Layout.fillWidth: true }
        MonthlyLog { Layout.fillWidth: true }
        Item { height: 8 }
        Text { text: "Automatizaciones"; color: Theme.text; font.family: Theme.family; font.pixelSize: 25; font.weight: Font.DemiBold }
        Text { text: "Selecciona el bot que quieres usar."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12 }
            GridLayout {
                Layout.fillWidth: true; columns: dashboard.width < 950 ? 2 : 3
                columnSpacing: 14; rowSpacing: 14
                Repeater {
                    model: demo.filteredModules
                    ModuleCard {
                        required property var modelData
                        Layout.fillWidth: true; Layout.minimumWidth: 210
                        info: modelData
                        onOpenModule: function(moduleId) { demo.navigate(moduleId) }
                    }
                }
            }
        Text { visible: demo.filteredModules.length === 0; text: "No se encontraron módulos."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12 }
    }
}
