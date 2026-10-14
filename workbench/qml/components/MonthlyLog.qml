import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: log
    objectName: "monthlyLog"
    Layout.fillWidth: true
    spacing: 10
    property string expandedMonth: ""
    function closeOptions(row) {
        let choices=[]
        for(let cell of row.cells) if(cell.module!=="manifiestos" && cell.status!=="missing") choices.push({target:cell.module,label:({detalles:"Detalles",duas_transito:"Tránsito",talon:"Talón",xmovimientos:"XMovimientos",bls:"BLs"})[cell.module],manual:!!cell.manual})
        let flows=["tabla","conocimientos","duas","movimientos","contenedores"]
        let names=["Listado","Conocimientos","DUAs","Movimientos","Contenedores"]
        for(let i=0;i<row.procedures.length;i++) if(row.procedures[i].status!=="missing") choices.push({target:"manifiestos:"+flows[i],label:"Manifiestos · "+names[i],manual:!!row.procedures[i].manual})
        return choices
    }
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Bitácora de descargas"; color: Theme.text; font.family: Theme.family; font.pixelSize: 22; font.weight: Font.DemiBold }
        Item { Layout.fillWidth: true }
        ActionButton { objectName: "refreshMonthly"; text: demo.monthlyBusy ? "Actualizando…" : "Actualizar"; enabled: !demo.monthlyBusy; onClicked: demo.refreshMonthly() }
    }
    Text { text: "Detalles exige todos los DUAs. Los demás admiten omitidos. Al día indica que terminó hasta la última fecha disponible."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Text { visible: !demo.monthlyRows.length; text: demo.monthlyBusy ? "Leyendo descargas guardadas…" : demo.monthlyMessage; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Repeater {
        model: demo.monthlyRows
        delegate: ColumnLayout {
            id: month
            required property var modelData
            Layout.fillWidth: true
            spacing: 8
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }
            RowLayout {
                Layout.fillWidth: true
                Text { text: month.modelData.label; color: Theme.text; font.family: Theme.family; font.pixelSize: 15; font.weight: Font.DemiBold }
                Item { Layout.fillWidth: true }
                Text { text: month.modelData.completed + " / 6 bots completos"+(month.modelData.upToDate ? " · "+month.modelData.upToDate+" al día" : ""); color: Theme.muted; font.family: Theme.family; font.pixelSize: 11 }
                ActionButton { text:"Cierre manual…"; subtle:true; enabled:!demo.monthlyBusy; onClicked:{ manualClose.monthKey=month.modelData.period; manualClose.monthLabel=month.modelData.label; manualClose.options=log.closeOptions(month.modelData); manualClose.open() } }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: log.width < 750 ? 3 : 6
                columnSpacing: 8; rowSpacing: 8
                Repeater {
                    model: month.modelData.cells
                    delegate: Rectangle {
                        id: cell
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 64
                        radius: 7
                        color: hover.hovered ? Theme.hover : Theme.surface
                        border.color: Theme.border
                        property color stateColor: ["completed","up_to_date"].indexOf(modelData.status)>=0 ? Theme.success : modelData.status === "missing" ? Theme.faint : Theme.accent
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 10; spacing: 6
                            Text { text: ({detalles:"Detalles",duas_transito:"Tránsito",talon:"Talón",xmovimientos:"XMovimientos",bls:"BLs",manifiestos:"Manifiestos"})[cell.modelData.module]; color: Theme.text; font.family: Theme.family; font.pixelSize: 11; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                            RowLayout {
                                Rectangle { width: 5; height: 5; radius: 3; color: cell.stateColor }
                                Text { text: cell.modelData.label; color: cell.stateColor; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                        }
                        HoverHandler { id: hover }
                        ToolTip.visible: hover.hovered
                        ToolTip.delay: 300
                        ToolTip.text: cell.modelData.detail
                        Button { anchors.fill: parent; flat: true; background: Item {} Accessible.name: cell.modelData.module + " " + month.modelData.label + ": " + cell.modelData.label; onClicked: demo.navigate(cell.modelData.module) }
                    }
                }
            }
            ActionButton { text: log.expandedMonth === month.modelData.period ? "Ocultar procedimientos de Manifiestos" : "Ver procedimientos de Manifiestos"; subtle: true; onClicked: log.expandedMonth = log.expandedMonth === month.modelData.period ? "" : month.modelData.period }
            Repeater {
                model: log.expandedMonth === month.modelData.period ? month.modelData.procedures : []
                delegate: RowLayout {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    Text { text: ["Manifiestos", "Conocimientos", "DUAs", "Movimientos", "Contenedores"][index]; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.preferredWidth: 125 }
                    Text { text: modelData.label; color: ["completed","up_to_date"].indexOf(modelData.status)>=0 ? Theme.success : Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.preferredWidth: 140 }
                    Text { text: modelData.detail; color: Theme.muted; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                }
            }
        }
    }
    Text { visible: demo.monthlyRows.length > 0; text: demo.monthlyMessage; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Dialog {
        id:manualClose; objectName:"manualMonthClose"
        parent:Overlay.overlay; anchors.centerIn:parent
        modal:true; width:Math.min(520,parent ? parent.width-40 : 520)
        property string monthKey:""
        property string monthLabel:""
        property var options:[]
        title:"Cierre manual · "+monthLabel
        background:Panel { color:Theme.background }
        palette.windowText:Theme.text
        contentItem:ColumnLayout {
            spacing:16
            ComboBox { id:closeTarget; objectName:"manualCloseTarget"; Layout.fillWidth:true; model:manualClose.options; textRole:"label" }
            Text { text:"Marca como completo lo ya descargado. Los pendientes se conservan para reintento. Detalles exige que todos sus DUAs estén guardados."; color:Theme.muted; font.family:Theme.family; font.pixelSize:12; wrapMode:Text.WordWrap; Layout.fillWidth:true }
            Text { visible:closeTarget.currentIndex>=0 && !!manualClose.options[closeTarget.currentIndex].manual; text:"Este cierre se marcó manualmente. Puedes volver a la comprobación automática."; color:Theme.success; font.pixelSize:12; wrapMode:Text.WordWrap; Layout.fillWidth:true }
            RowLayout {
                Layout.fillWidth:true
                ActionButton { objectName:"removeManualMonthClose"; text:"Usar comprobación automática"; enabled:closeTarget.currentIndex>=0; onClicked:{ demo.setMonthComplete(manualClose.monthKey,manualClose.options[closeTarget.currentIndex].target,false); manualClose.close() } }
                Item { Layout.fillWidth:true }
                ActionButton { objectName:"saveManualMonthClose"; text:"Marcar completo"; primary:true; enabled:closeTarget.currentIndex>=0; onClicked:{ demo.setMonthComplete(manualClose.monthKey,manualClose.options[closeTarget.currentIndex].target,true); manualClose.close() } }
            }
            ActionButton { text:"Cancelar"; subtle:true; Layout.alignment:Qt.AlignRight; onClicked:manualClose.close() }
        }
    }
}
