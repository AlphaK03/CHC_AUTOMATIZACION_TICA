import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as Native
import "components"

Dialog {
    id: dialog
    property var service: null
    property bool picking: false
    property bool showActivity: false
    property bool savingFolder: false
    property string driveId: ""
    property string selectedSite: ""
    property string libraryName: ""
    property var sites: []
    property var ancestors: []
    title: picking ? "Elegir carpeta de SharePoint" : "Cuenta y resultados"
    modal: true
    width: Math.min(900,parent ? parent.width-60 : 900)
    height: Math.min(740,parent ? parent.height-40 : 740)
    anchors.centerIn: parent
    padding: 24
    standardButtons: Dialog.NoButton
    palette.windowText: Theme.text
    palette.buttonText: Theme.text
    palette.button: Theme.raised
    background: Panel { color:Theme.background }
    header: Text {
        text:dialog.title; color:Theme.text; font.family:Theme.family
        font.pixelSize:18; font.weight:Font.DemiBold
        leftPadding:24; topPadding:20; bottomPadding:8
    }
    footer: Item {
        implicitHeight:64
        ActionButton { anchors.right:parent.right; anchors.rightMargin:24; anchors.verticalCenter:parent.verticalCenter; text:"Cerrar"; onClicked:dialog.close() }
    }
    onOpened: { picking=false; if(service) service.refresh() }
    function startPicker() {
        picking=true; driveId=""; selectedSite=""; ancestors=[]
        service.searchSites("https://chcconsultorescr.sharepoint.com","")
    }
    function folderReady() { return !!service && !!driveId && service.browse.driveId===driveId && !!service.browse.folder }
    Connections {
        target:dialog.service
        function onChanged() {
            if(service.browse.sites) dialog.sites=service.browse.sites
            if(dialog.savingFolder && !service.busy) {
                dialog.savingFolder=false
                if(!service.error) dialog.picking=false
            }
        }
    }
    contentItem: ColumnLayout {
        spacing:16
        RowLayout {
            Layout.fillWidth:true
            Rectangle {
                width:42; height:42; radius:12; color:Theme.raised
                Icon { anchors.centerIn:parent; name:"folder"; tint:Theme.accent; width:23; height:23 }
            }
            ColumnLayout {
                Layout.fillWidth:true; spacing:3
                Text { text:service && service.connected ? service.account : "Conecta tu cuenta CHC"; color:Theme.text; font.pixelSize:15; font.weight:Font.DemiBold; Layout.fillWidth:true; elide:Text.ElideRight }
                Text { text:service && service.connected ? "SharePoint conectado" : "El guardado local funciona sin cuenta"; color:service && service.connected ? Theme.success : Theme.muted; font.pixelSize:11 }
            }
            ActionButton { objectName:"connectSharePoint"; text:service && service.connected ? "Cuenta" : "Conectar"; primary:!service || !service.connected; enabled:!!service && service.enabled && !service.busy; onClicked:service && service.connected ? accountMenu.open() : service.connectAccount() }
            Menu {
                id:accountMenu
                MenuItem { text:"Cambiar cuenta"; onTriggered:service.connectAccount() }
                MenuItem { text:"Desconectar"; onTriggered:service.disconnectAccount() }
            }
            BusyIndicator { running:!!service && service.busy; visible:running; Layout.preferredWidth:28; Layout.preferredHeight:28 }
        }
        Text { visible:!!service && !!service.error; text:service ? service.error : ""; color:Theme.accent; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        StackLayout {
            currentIndex:dialog.picking ? 1 : 0
            Layout.fillWidth:true; Layout.fillHeight:true
            ScrollView {
                clip:true
                ColumnLayout {
                    width:dialog.availableWidth; spacing:16
                    Panel {
                        Layout.fillWidth:true; implicitHeight:112
                        ColumnLayout {
                            anchors.fill:parent; anchors.margins:18; spacing:8
                            RowLayout {
                                Text { text:"CARPETA MADRE LOCAL"; color:Theme.muted; font.pixelSize:10; font.weight:Font.DemiBold; font.letterSpacing:1; Layout.fillWidth:true }
                                ActionButton { text:"Cambiar"; subtle:true; enabled:!!service && !service.busy; onClicked:localFolder.open() }
                            }
                            Text { text:service ? service.localRoot : ""; color:Theme.text; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideMiddle }
                            Text { text:"Todos los bots guardan aquí, en carpetas propias por mes."; color:Theme.faint; font.pixelSize:11 }
                        }
                    }
                    Panel {
                        Layout.fillWidth:true; implicitHeight:158
                        ColumnLayout {
                            anchors.fill:parent; anchors.margins:18; spacing:8
                            RowLayout {
                                Text { text:"CARPETA MADRE DE SHAREPOINT"; color:Theme.muted; font.pixelSize:10; font.weight:Font.DemiBold; font.letterSpacing:1; Layout.fillWidth:true }
                                ActionButton { objectName:"chooseSharePointFolder"; text:service && service.destination.folderId ? "Cambiar" : "Elegir carpeta"; primary:true; enabled:!!service && service.connected && !service.busy; onClicked:dialog.startPicker() }
                            }
                            Text { text:service && service.destination.folderId ? service.destination.folderName || "Carpeta seleccionada" : "Elige una carpeta para todos los bots"; color:Theme.text; font.pixelSize:16; font.weight:Font.DemiBold; Layout.fillWidth:true }
                            Text { text:service && service.destination.webUrl ? service.destination.webUrl : "La misma organización del guardado local."; color:Theme.muted; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideMiddle }
                            RowLayout {
                                Text { text:"DETALLES  ·  TALON  ·  BLS  ·  TRANSITO  ·  XMOVIMIENTOS  ·  MANIFIESTOS"; color:Theme.faint; font.pixelSize:10; Layout.fillWidth:true; elide:Text.ElideRight }
                                ActionButton { text:"Quitar"; subtle:true; visible:!!service && !!service.destination.folderId; enabled:!!service && !service.busy; onClicked:service.removeDestination() }
                            }
                        }
                    }
                    Panel {
                        Layout.fillWidth:true; implicitHeight:144
                        ColumnLayout {
                            anchors.fill:parent; anchors.margins:18; spacing:10
                            Text { text:"Subir un mes completo"; color:Theme.text; font.pixelSize:16; font.weight:Font.DemiBold }
                            RowLayout {
                                Layout.fillWidth:true
                                ComboBox { id:monthBox; objectName:"sharePointMonth"; Layout.fillWidth:true; model:service ? service.months : []; textRole:"label"; displayText:count ? currentText : "Sin meses completos exportados"; enabled:!!service && !service.busy && count>0 }
                                ActionButton { objectName:"uploadSharePointMonth"; text:"Subir a SharePoint"; primary:true; enabled:!!service && service.connected && !!service.destination.folderId && !service.busy && monthBox.currentIndex>=0; onClicked:service.uploadMonth(service.months[monthBox.currentIndex].period) }
                            }
                            Text { text:service && service.months.length ? "Solo se enviarán CSV de bots con ese mes completo y verificado." : "Los meses aparecerán al completar y exportar sus resultados."; color:Theme.faint; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                        }
                    }
                    RowLayout {
                        Text { text:"Las subidas se inician únicamente cuando las solicitas."; color:Theme.muted; font.pixelSize:11; Layout.fillWidth:true }
                        ActionButton { text:dialog.showActivity ? "Ocultar actividad" : "Ver actividad"; subtle:true; onClicked:dialog.showActivity=!dialog.showActivity }
                        ActionButton { text:"Actualizar"; subtle:true; enabled:!!service && !service.busy; onClicked:service.refresh() }
                    }
                    ColumnLayout {
                        visible:dialog.showActivity; Layout.fillWidth:true; spacing:8
                        RowLayout {
                            Text { text:service ? service.status : ""; color:Theme.muted; font.pixelSize:12; Layout.fillWidth:true }
                            ActionButton { text:"Reintentar envíos"; enabled:!!service && service.connected && !service.busy && service.pending>0; onClicked:service.retry() }
                        }
                        Repeater {
                            model:service ? service.tasks : []
                            Text { required property var modelData; text:modelData.filename+" · "+({pending:"Pendiente",uploading:"Subiendo",synced:"En SharePoint",error:"Por reintentar",paused:"En pausa"})[modelData.state]+(modelData.error ? "\n"+modelData.error : ""); color:modelData.state==="synced" ? Theme.success : Theme.muted; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                        }
                    }
                }
            }
            ColumnLayout {
                spacing:12
                RowLayout {
                    TextField { id:siteSearch; objectName:"sharePointSiteSearch"; Layout.fillWidth:true; placeholderText:"Buscar un sitio"; selectByMouse:true; color:Theme.text; background:Rectangle { color:Theme.surface; radius:7; border.color:Theme.border } }
                    ActionButton { objectName:"searchSharePointSites"; text:"Buscar"; enabled:!!service && !service.busy; onClicked:service.searchSites("https://chcconsultorescr.sharepoint.com",siteSearch.text) }
                    ActionButton { text:"Volver"; subtle:true; enabled:!!service && !service.busy; onClicked:dialog.picking=false }
                }
                RowLayout {
                    Layout.fillWidth:true; Layout.fillHeight:true; spacing:12
                    Panel {
                        Layout.preferredWidth:265; Layout.fillHeight:true
                        ColumnLayout {
                            anchors.fill:parent; anchors.margins:14; spacing:10
                            RowLayout {
                                Text { text:dialog.selectedSite ? "BIBLIOTECAS" : "SITIOS"; color:Theme.muted; font.pixelSize:10; font.weight:Font.DemiBold; font.letterSpacing:1; Layout.fillWidth:true }
                                ActionButton { text:"Sitios"; subtle:true; visible:!!dialog.selectedSite; enabled:!!service && !service.busy; onClicked:{dialog.selectedSite="";dialog.driveId=""} }
                            }
                            ListView {
                                id:sitesList
                                Layout.fillWidth:true; Layout.fillHeight:true; clip:true; spacing:5
                                model:dialog.selectedSite ? service && service.browse.drives ? service.browse.drives : [] : dialog.sites
                                ScrollBar.vertical:ScrollBar {}
                                delegate: Button {
                                    required property var modelData
                                    objectName:dialog.selectedSite ? "sharePointLibrary" : "sharePointKnownSite"
                                    width:sitesList.width; height:52; hoverEnabled:true
                                    text:modelData.name
                                    enabled:!!service && !service.busy
                                    background:Rectangle { radius:7; color:parent.hovered ? Theme.hover : "transparent" }
                                    contentItem:Text { text:parent.text; color:Theme.text; font.pixelSize:12; wrapMode:Text.WordWrap; verticalAlignment:Text.AlignVCenter }
                                    onClicked: {
                                        dialog.driveId="";dialog.ancestors=[]
                                        if(dialog.selectedSite){dialog.driveId=modelData.id;dialog.libraryName=modelData.name;service.openFolder(modelData.id,"root")}
                                        else {dialog.selectedSite=modelData.name;service.openSite(modelData.url)}
                                    }
                                }
                            }
                        }
                    }
                    Panel {
                        Layout.fillWidth:true; Layout.fillHeight:true
                        ColumnLayout {
                            anchors.fill:parent; anchors.margins:16; spacing:10
                            RowLayout {
                                ActionButton { text:"Subir"; subtle:true; enabled:!!service && !service.busy && dialog.ancestors.length>0; onClicked:{let stack=dialog.ancestors.slice();let up=stack.pop();dialog.ancestors=stack;service.openFolder(dialog.driveId,up.id)} }
                                Text { text:dialog.folderReady() ? service.browse.folder.name : "Selecciona una biblioteca"; color:Theme.text; font.pixelSize:14; font.weight:Font.DemiBold; Layout.fillWidth:true; elide:Text.ElideRight }
                            }
                            Text { text:dialog.selectedSite+(dialog.libraryName ? " / "+dialog.libraryName : ""); color:Theme.muted; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideMiddle }
                            Rectangle { height:1; color:Theme.border; Layout.fillWidth:true }
                            ListView {
                                id:folderList
                                Layout.fillWidth:true; Layout.fillHeight:true; clip:true; spacing:4
                                model:dialog.folderReady() ? service.browse.folders || [] : []
                                ScrollBar.vertical:ScrollBar {}
                                delegate: Button {
                                    required property var modelData
                                    objectName:"sharePointFolderRow"
                                    width:folderList.width; height:44; hoverEnabled:true; text:modelData.name
                                    enabled:!!service && !service.busy
                                    background:Rectangle { radius:7; color:parent.hovered ? Theme.hover : "transparent" }
                                    contentItem:RowLayout { spacing:10; Icon { name:"folder"; tint:Theme.accent; width:18; height:18 } Text { text:modelData.name; color:Theme.text; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideRight } Icon { name:"chevron"; tint:Theme.muted; width:15; height:15 } }
                                    onClicked:{dialog.ancestors=dialog.ancestors.concat([{id:service.browse.folder.id,name:service.browse.folder.name}]);service.openFolder(dialog.driveId,modelData.id)}
                                }
                            }
                            Text { visible:dialog.folderReady() && folderList.count===0 && !!service && !service.busy; text:"Esta carpeta no tiene subcarpetas. Puedes elegirla."; color:Theme.faint; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                        }
                    }
                }
                RowLayout {
                    Text { text:dialog.folderReady() ? "Todos los bots crearán sus carpetas dentro de «"+service.browse.folder.name+"»." : "Elige sitio, biblioteca y carpeta."; color:Theme.muted; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                    ActionButton { objectName:"saveSharePointFolder"; text:"Usar esta carpeta para todos"; primary:true; enabled:dialog.folderReady() && !!service && !service.busy; onClicked:{dialog.savingFolder=true;service.saveDestination(dialog.driveId,service.browse.folder.id)} }
                }
            }
        }
    }
    Native.FolderDialog {
        id:localFolder; title:"Carpeta madre local para todos los bots"
        onAccepted:{let value=decodeURIComponent(selectedFolder.toString().replace(/^file:\/\//,""));if(/^\/[A-Za-z]:/.test(value))value=value.slice(1);service.setLocalRoot(value)}
    }
}
