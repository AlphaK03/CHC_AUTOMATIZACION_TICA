import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as Native
import "components"

AppDialog {
    id: dialog
    property var service: null
    property bool picking: false
    property bool browseOnly: false
    property bool showActivity: false
    property bool savingFolder: false
    property string driveId: ""
    property string expectedFolder: ""
    property string selectedSite: ""
    property string libraryName: ""
    property var sites: []
    property var ancestors: []
    title: "SharePoint"; modal: true
    width: Math.min(980,parent ? parent.width-48 : 980)
    height: Math.min(760,parent ? parent.height-32 : 760)
    anchors.centerIn: parent; padding: 24; standardButtons: Dialog.NoButton
    background: Panel { color:Theme.background }
    header: Text { text:dialog.title; color:Theme.text; font.family:Theme.family; font.pixelSize:22; font.weight:Font.DemiBold; leftPadding:24; topPadding:20; bottomPadding:8 }
    footer: Item {
        implicitHeight:56
        Text { anchors.left:parent.left; anchors.leftMargin:24; anchors.verticalCenter:parent.verticalCenter; text:service && service.busy ? "Consultando…" : "Tus descargas continúan de forma independiente"; color:Theme.faint; font.family:Theme.family; font.pixelSize:10 }
        ActionButton { anchors.right:parent.right; anchors.rightMargin:24; anchors.verticalCenter:parent.verticalCenter; text:"Cerrar"; onClicked:dialog.close() }
    }
    onOpened: { picking=false; if(service) service.refresh() }
    function startPicker(readOnly=false) {
        browseOnly=readOnly; picking=true; driveId=""; expectedFolder=""; selectedSite=""; libraryName=""; ancestors=[]
        service.searchSites("https://chcconsultorescr.sharepoint.com","")
    }
    function exploreDestination() {
        if(!service.destination.folderId) { startPicker(true); return }
        browseOnly=true; picking=true; ancestors=[]; driveId=service.destination.driveId; expectedFolder=service.destination.folderId
        selectedSite=service.destination.folderName || "Destino de resultados"; libraryName=""; service.openDestination()
    }
    function folderReady() { return !!service && !!driveId && service.browse.driveId===driveId && !!service.browse.folder && (!expectedFolder || expectedFolder==="root" || service.browse.folder.id===expectedFolder) }
    // Cambiar el modelo destruye delegados: navegar siempre desde el diálogo.
    function chooseLocation(isLibrary,itemId,itemName,itemUrl) {
        driveId=""; expectedFolder=""; ancestors=[]
        if(isLibrary) { driveId=itemId; expectedFolder="root"; libraryName=itemName; service.openFolder(itemId,"root") }
        else { selectedSite=itemName; libraryName=""; service.openSite(itemUrl) }
    }
    function chooseFolder(itemId) { ancestors=ancestors.concat([{id:service.browse.folder.id,name:service.browse.folder.name}]); expectedFolder=itemId; service.openFolder(driveId,itemId) }
    function chooseEntry(itemId,isFolder,url) { if(isFolder) chooseFolder(itemId); else service.openOnline(url) }
    function goUp() { let stack=ancestors.slice();let up=stack.pop();ancestors=stack;expectedFolder=up.id;service.openFolder(driveId,up.id) }
    function searchLocations() { selectedSite="";libraryName="";driveId="";expectedFolder="";ancestors=[];service.searchSites("https://chcconsultorescr.sharepoint.com",siteSearch.text) }
    function dateText(value) { let date=new Date(value);return isNaN(date.getTime()) ? "" : date.toLocaleString(Qt.locale("es_CR"),"dd/MM/yyyy HH:mm") }
    function sizeText(value) { return value >= 1048576 ? (value/1048576).toFixed(1)+" MB" : value >= 1024 ? (value/1024).toFixed(1)+" KB" : (value || 0)+" B" }
    function stateText(state) { return ({pending:"Pendiente",uploading:"Subiendo",synced:"En SharePoint",error:"Por revisar",paused:"En pausa"})[state] || state }
    function filteredTasks() {
        const chosen=["","pending","error","synced","paused"][activityFilter.currentIndex], query=activitySearch.text.trim().toLowerCase()
        return service ? service.tasks.filter(task => (!chosen || task.state===chosen || chosen==="pending" && task.state==="uploading") && task.filename.toLowerCase().indexOf(query)>=0) : []
    }
    Connections {
        target:dialog.service
        function onChanged() {
            if(service.browse.sites) dialog.sites=service.browse.sites
            if(dialog.browseOnly && dialog.driveId && service.browse.site) {
                dialog.selectedSite=service.browse.site.displayName || service.browse.site.name || dialog.selectedSite
                const library=(service.browse.drives || []).find(item => item.id===dialog.driveId)
                if(library) dialog.libraryName=library.name
            }
            if(dialog.savingFolder && !service.busy) { dialog.savingFolder=false; if(!service.error) dialog.picking=false }
        }
    }
    contentItem: ColumnLayout {
        spacing:14
        RowLayout {
            visible:!dialog.picking
            Layout.fillWidth:true; spacing:14
            AccountAvatar { Layout.preferredWidth:52; Layout.preferredHeight:52; connected:!!service && service.connected; displayName:service ? service.profile.displayName || service.account : ""; photoUrl:service ? service.profile.photoUrl || "" : "" }
            ColumnLayout {
                Layout.fillWidth:true; spacing:4
                Text { objectName:"sharePointDisplayName"; text:service && service.connected ? service.profile.displayName || service.account : "Conecta tu cuenta CHC"; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:17; font.weight:Font.DemiBold; Layout.fillWidth:true; elide:Text.ElideRight }
                Text { text:service && service.connected ? service.profile.email || service.account : "Publica tus resultados en un único destino"; textFormat:Text.PlainText; color:Theme.muted; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideRight }
                Text { text:service && service.connected ? "● Cuenta conectada" : "El guardado local está disponible sin conexión"; color:service && service.connected ? Theme.success : Theme.muted; font.family:Theme.family; font.pixelSize:10 }
            }
            BusyIndicator { running:!!service && service.busy; visible:running; Layout.preferredWidth:26; Layout.preferredHeight:26 }
            ActionButton { objectName:"connectSharePoint"; text:service && service.connected ? "Cuenta" : "Conectar"; primary:!service || !service.connected; enabled:!!service && service.enabled && !service.busy; onClicked:service && service.connected ? accountMenu.popup() : service.connectAccount() }
            Menu {
                id:accountMenu
                MenuItem { text:"Actualizar perfil"; onTriggered:service.refreshProfile() }
                MenuItem { text:"Cambiar cuenta…"; onTriggered:service.connectAccount() }
                MenuItem { text:"Desconectar"; onTriggered:service.disconnectAccount() }
            }
        }
        Text { visible:!!service && (!!service.error || !!service.profileWarning); text:service ? service.error || service.profileWarning : ""; textFormat:Text.PlainText; color:Theme.warning; font.family:Theme.family; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
        RowLayout {
            Layout.fillWidth:true; spacing:6
            ActionButton { text:"Resultados"; primary:!dialog.picking && !dialog.showActivity; onClicked:{dialog.picking=false;dialog.showActivity=false} }
            ActionButton { objectName:"exploreSharePoint"; text:"Archivos"; primary:dialog.picking; enabled:!!service && service.connected && !service.busy; onClicked:dialog.exploreDestination() }
            ActionButton { objectName:"sharePointActivityTab"; text:"Actividad"; primary:!dialog.picking && dialog.showActivity; onClicked:{dialog.picking=false;dialog.showActivity=true} }
            Item { Layout.fillWidth:true }
            ActionButton { text:"Actualizar"; subtle:true; enabled:!!service && !service.busy; onClicked:dialog.picking && dialog.folderReady() ? service.openFolder(dialog.driveId,service.browse.folder.id) : service.refresh() }
        }
        Rectangle { Layout.fillWidth:true; implicitHeight:1; color:Theme.border }
        StackLayout {
            currentIndex:dialog.picking ? 1 : 0; Layout.fillWidth:true; Layout.fillHeight:true
            ScrollView {
                id:cloudScroll; objectName:"sharePointResultsScroll"; clip:true
                contentWidth:availableWidth; ScrollBar.horizontal.policy:ScrollBar.AlwaysOff; ScrollBar.vertical.active:true
                ColumnLayout {
                    width:cloudScroll.availableWidth; spacing:16
                    RowLayout {
                        Layout.fillWidth:true; spacing:32
                        Repeater {
                            model:[{value:service ? service.queueCounts.synced || 0 : 0,label:"En SharePoint",tint:Theme.success},{value:service ? (service.queueCounts.pending || 0)+(service.queueCounts.uploading || 0) : 0,label:"En cola",tint:Theme.text},{value:service ? service.queueCounts.error || 0 : 0,label:"Por revisar",tint:Theme.warning}]
                            ColumnLayout {
                                required property var modelData; spacing:3
                                Text { text:modelData.value; color:modelData.tint; font.family:Theme.family; font.pixelSize:25; font.weight:Font.DemiBold }
                                Text { text:modelData.label; color:Theme.muted; font.family:Theme.family; font.pixelSize:10 }
                            }
                        }
                        Item { Layout.fillWidth:true }
                        ActionButton { visible:dialog.showActivity; text:"Reintentar envíos"; enabled:!!service && service.connected && !service.busy && (service.queueCounts.error || 0)>0; onClicked:service.retry() }
                    }
                    Panel {
                        visible:!dialog.showActivity; Layout.fillWidth:true; implicitHeight:destinations.implicitHeight+32
                        ColumnLayout {
                            id:destinations; anchors.left:parent.left; anchors.right:parent.right; anchors.top:parent.top; anchors.margins:16; spacing:12
                            RowLayout {
                                Layout.fillWidth:true
                                Icon { name:"folder"; tint:Theme.accent; width:20; height:20 }
                                Text { text:"Destino en SharePoint"; color:Theme.text; font.family:Theme.family; font.pixelSize:14; font.weight:Font.DemiBold; Layout.fillWidth:true }
                                ActionButton { objectName:"chooseSharePointFolder"; text:service && service.destination.folderId ? "Cambiar carpeta" : "Elegir carpeta"; enabled:!!service && service.connected && !service.busy; onClicked:dialog.startPicker() }
                            }
                            Text { text:service && service.destination.folderId ? service.destination.folderName || "Carpeta seleccionada" : "Elige dónde guardar los resultados de todos los bots"; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:16; font.weight:Font.DemiBold; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                            Text { text:service && service.destination.webUrl ? service.destination.webUrl : "Se crearán carpetas por bot, procedimiento y mes."; textFormat:Text.PlainText; color:Theme.muted; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideMiddle; ToolTip.visible:destinationHover.hovered; ToolTip.text:text; HoverHandler{id:destinationHover} }
                            RowLayout {
                                Layout.fillWidth:true
                                ActionButton { text:"Explorar archivos"; subtle:true; enabled:!!service && service.connected && !!service.destination.folderId && !service.busy; onClicked:dialog.exploreDestination() }
                                ActionButton { text:"Abrir en navegador"; subtle:true; enabled:!!service && !!service.destination.webUrl; onClicked:service.openOnline(service.destination.webUrl) }
                                Item { Layout.fillWidth:true }
                                ActionButton { text:"Quitar destino"; subtle:true; visible:!!service && !!service.destination.folderId; enabled:!!service && !service.busy; onClicked:service.removeDestination() }
                            }
                            Rectangle { Layout.fillWidth:true; implicitHeight:1; color:Theme.border }
                            RowLayout {
                                Layout.fillWidth:true
                                ColumnLayout {
                                    Layout.fillWidth:true; spacing:4
                                    Text { text:"Carpeta local"; color:Theme.muted; font.family:Theme.family; font.pixelSize:10 }
                                    Text { text:service ? service.localRoot : ""; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideMiddle }
                                }
                                ActionButton { text:"Abrir"; subtle:true; enabled:!!service && !!service.localRoot; onClicked:service.openLocalRoot() }
                                ActionButton { text:"Cambiar"; subtle:true; enabled:!!service && !service.busy; onClicked:localFolder.open() }
                            }
                        }
                    }
                    Panel {
                        visible:!dialog.showActivity; Layout.fillWidth:true; implicitHeight:publication.implicitHeight+32
                        ColumnLayout {
                            id:publication; anchors.left:parent.left; anchors.right:parent.right; anchors.top:parent.top; anchors.margins:16; spacing:12
                            Text { text:"Publicar resultados"; color:Theme.text; font.family:Theme.family; font.pixelSize:16; font.weight:Font.DemiBold }
                            RowLayout {
                                Layout.fillWidth:true
                                Select { id:monthBox; objectName:"sharePointMonth"; Layout.fillWidth:true; model:service ? service.months : []; textRole:"label"; placeholder:"Sin meses listos para subir"; enabled:!!service && !service.busy && count>0 }
                                ActionButton { objectName:"uploadSharePointMonth"; text:"Subir a SharePoint"; primary:true; enabled:!!service && service.connected && !!service.destination.folderId && !service.busy && monthBox.count>0 && monthBox.currentIndex>=0; onClicked:service.uploadMonth(service.months[monthBox.currentIndex].period) }
                            }
                            Text { text:service && monthBox.currentIndex>=0 && service.months[monthBox.currentIndex] ? service.months[monthBox.currentIndex].files+" CSV de "+(service.months[monthBox.currentIndex].bots || 1)+" bots o procedimientos listos para publicar" : "Completa o cierra el mes en Vista general y exporta sus resultados."; color:Theme.muted; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                            Text { text:"Solo se envían resultados confirmados. Las nuevas versiones actualizan el mismo archivo del lote, mes y modalidad."; color:Theme.faint; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                        }
                    }
                    Text { visible:!dialog.showActivity; text:"Las subidas se inician únicamente cuando las solicitas."; color:Theme.muted; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                    RowLayout {
                        visible:dialog.showActivity; Layout.fillWidth:true
                        Field { id:activitySearch; Layout.fillWidth:true; placeholderText:"Buscar archivo" }
                        Select { id:activityFilter; objectName:"sharePointActivityFilter"; Layout.preferredWidth:150; model:["Todos","Pendientes","Por revisar","En SharePoint","En pausa"] }
                    }
                    Text { visible:dialog.showActivity; text:"Últimos 50 envíos registrados"; color:Theme.faint; font.family:Theme.family; font.pixelSize:10 }
                    Text { visible:dialog.showActivity && dialog.filteredTasks().length===0; text:"No hay envíos para mostrar con este filtro."; color:Theme.muted; font.family:Theme.family; font.pixelSize:12; Layout.fillWidth:true }
                    Repeater {
                        model:dialog.showActivity ? dialog.filteredTasks() : []
                        Panel {
                            required property var modelData
                            objectName:"sharePointTaskRow"; Layout.fillWidth:true; implicitHeight:taskColumn.implicitHeight+24
                            ColumnLayout {
                                id:taskColumn; anchors.left:parent.left; anchors.right:parent.right; anchors.top:parent.top; anchors.margins:12; spacing:6
                                RowLayout {
                                    Layout.fillWidth:true; spacing:10
                                    Rectangle { width:6; height:6; radius:3; color:modelData.state==="synced" ? Theme.success : modelData.state==="error" ? Theme.warning : Theme.muted }
                                    Text { text:modelData.filename; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideMiddle }
                                    Text { text:dialog.stateText(modelData.state); color:modelData.state==="synced" ? Theme.success : modelData.state==="error" ? Theme.warning : Theme.muted; font.family:Theme.family; font.pixelSize:11 }
                                }
                                Text { text:dialog.dateText(modelData.updated)+" · "+modelData.name; textFormat:Text.PlainText; color:Theme.faint; font.family:Theme.family; font.pixelSize:10 }
                                Text { visible:!!modelData.error; text:modelData.error; textFormat:Text.PlainText; color:Theme.warning; font.family:Theme.family; font.pixelSize:11; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                spacing:12
                RowLayout {
                    Field { id:siteSearch; objectName:"sharePointSiteSearch"; Layout.fillWidth:true; placeholderText:"Buscar un sitio"; onAccepted:dialog.searchLocations() }
                    ActionButton { objectName:"searchSharePointSites"; text:"Buscar"; enabled:!!service && !service.busy; onClicked:dialog.searchLocations() }
                    ActionButton { text:"Volver"; subtle:true; enabled:!!service && !service.busy; onClicked:dialog.picking=false }
                }
                RowLayout {
                    Layout.fillWidth:true; Layout.fillHeight:true; spacing:12
                    Panel {
                        Layout.preferredWidth:220; Layout.fillHeight:true
                        ColumnLayout {
                            anchors.fill:parent; anchors.margins:14; spacing:10
                            RowLayout {
                                Text { text:dialog.selectedSite ? "BIBLIOTECAS" : "SITIOS"; color:Theme.muted; font.family:Theme.family; font.pixelSize:10; font.weight:Font.DemiBold; Layout.fillWidth:true }
                                ActionButton { text:"Sitios"; subtle:true; visible:!!dialog.selectedSite; enabled:!!service && !service.busy; onClicked:{dialog.selectedSite="";dialog.driveId="";dialog.expectedFolder=""} }
                            }
                            ListView {
                                id:sitesList; objectName:"sharePointLocationList"; Layout.fillWidth:true; Layout.fillHeight:true; clip:true; spacing:5
                                model:dialog.selectedSite ? service && service.browse.drives ? service.browse.drives : [] : dialog.sites
                                ScrollBar.vertical:ScrollBar {}
                                delegate: Button {
                                    id:locationButton; required property var modelData
                                    objectName:dialog.selectedSite ? "sharePointLibrary" : "sharePointKnownSite"
                                    width:sitesList.width; height:Math.max(48,locationText.implicitHeight+16); hoverEnabled:true
                                    text:modelData.name; enabled:!!service && !service.busy
                                    background:Rectangle { radius:7; color:parent.hovered ? Theme.hover : "transparent" }
                                    contentItem:Text { id:locationText; text:locationButton.text; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:12; wrapMode:Text.Wrap; verticalAlignment:Text.AlignVCenter }
                                    onClicked:dialog.chooseLocation(!!dialog.selectedSite,modelData.id || "",modelData.name,modelData.url || "")
                                }
                            }
                        }
                    }
                    Panel {
                        Layout.fillWidth:true; Layout.fillHeight:true
                        ColumnLayout {
                            anchors.fill:parent; anchors.margins:16; spacing:10
                            RowLayout {
                                Layout.fillWidth:true
                                ActionButton { text:"Subir"; subtle:true; enabled:!!service && !service.busy && dialog.ancestors.length>0; onClicked:dialog.goUp() }
                                Text { text:dialog.folderReady() ? service.browse.folder.name : "Selecciona una biblioteca"; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:14; font.weight:Font.DemiBold; Layout.fillWidth:true; Layout.minimumWidth:0; elide:Text.ElideRight }
                                ActionButton { objectName:"newSharePointFolder"; text:"Nueva carpeta"; subtle:true; enabled:dialog.folderReady() && !!service && !service.busy; onClicked:{newFolderName.text="";newFolder.open()} }
                            }
                            Text { text:dialog.selectedSite+(dialog.libraryName ? " / "+dialog.libraryName : ""); textFormat:Text.PlainText; color:Theme.muted; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; elide:Text.ElideMiddle }
                            Rectangle { implicitHeight:1; color:Theme.border; Layout.fillWidth:true }
                            ListView {
                                id:folderList; objectName:"sharePointFolderList"; Layout.fillWidth:true; Layout.fillHeight:true; clip:true; spacing:4
                                model:dialog.folderReady() ? (service.browse.folders || []).concat(service.browse.files || []) : []
                                ScrollBar.vertical:ScrollBar {}
                                delegate: Button {
                                    id:fileEntry; required property var modelData
                                    readonly property bool isFolder:!modelData.file
                                    objectName:isFolder ? "sharePointFolderRow" : "sharePointFileRow"
                                    width:folderList.width; height:isFolder ? 44 : 60; hoverEnabled:true; text:modelData.name; enabled:!!service && !service.busy
                                    background:Rectangle { radius:7; color:parent.hovered ? Theme.hover : "transparent" }
                                    contentItem:RowLayout {
                                        spacing:10
                                        Icon { name:fileEntry.isFolder ? "folder" : "document"; tint:fileEntry.isFolder ? Theme.accent : Theme.muted; width:18; height:18 }
                                        ColumnLayout {
                                            Layout.fillWidth:true; spacing:4
                                            Text { text:modelData.name; textFormat:Text.PlainText; color:Theme.text; font.family:Theme.family; font.pixelSize:12; Layout.fillWidth:true; elide:Text.ElideMiddle }
                                            Text { visible:!fileEntry.isFolder; text:dialog.sizeText(modelData.size)+" · "+dialog.dateText(modelData.lastModifiedDateTime); color:Theme.muted; font.family:Theme.family; font.pixelSize:10 }
                                        }
                                        Icon { name:fileEntry.isFolder ? "chevron" : "arrow"; tint:Theme.muted; width:15; height:15 }
                                    }
                                    onClicked:dialog.chooseEntry(modelData.id,fileEntry.isFolder,modelData.webUrl || "")
                                }
                            }
                            Text { visible:dialog.folderReady() && folderList.count===0 && !!service && !service.busy; text:"Esta carpeta está vacía. Puedes elegirla como destino."; color:Theme.faint; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth:true
                    Text { text:dialog.folderReady() ? dialog.browseOnly ? "Abre un archivo para verlo en SharePoint." : "Todos los bots guardarán dentro de «"+service.browse.folder.name+"»." : "Elige sitio, biblioteca y carpeta."; textFormat:Text.PlainText; color:Theme.muted; font.family:Theme.family; font.pixelSize:11; Layout.fillWidth:true; Layout.minimumWidth:0; wrapMode:Text.WordWrap }
                    ActionButton { visible:dialog.browseOnly; text:"Abrir en navegador"; enabled:dialog.folderReady() && !!service.browse.folder.webUrl; onClicked:service.openOnline(service.browse.folder.webUrl) }
                    ActionButton { objectName:"saveSharePointFolder"; visible:!dialog.browseOnly; text:"Usar esta carpeta para todos"; primary:true; enabled:dialog.folderReady() && !!service && !service.busy; onClicked:{dialog.savingFolder=true;service.saveDestination(dialog.driveId,service.browse.folder.id)} }
                }
            }
        }
    }
    AppDialog {
        id:newFolder; title:"Nueva carpeta"; anchors.centerIn:parent; width:Math.min(440,dialog.width-40); standardButtons:Dialog.NoButton
        contentItem:ColumnLayout {
            spacing:12
            Text { text:"Crear dentro de «"+(dialog.folderReady() ? service.browse.folder.name : "")+"»"; textFormat:Text.PlainText; color:Theme.muted; font.family:Theme.family; font.pixelSize:12; Layout.fillWidth:true; wrapMode:Text.WordWrap }
            Field { id:newFolderName; objectName:"sharePointNewFolderName"; Layout.fillWidth:true; placeholderText:"Nombre de la carpeta"; maximumLength:120 }
            RowLayout {
                Layout.fillWidth:true
                Item { Layout.fillWidth:true }
                ActionButton { text:"Cancelar"; onClicked:newFolder.close() }
                ActionButton { objectName:"createSharePointFolder"; text:"Crear carpeta"; primary:true; enabled:newFolderName.text.trim().length>0 && dialog.folderReady() && !service.busy; onClicked:{service.createFolder(dialog.driveId,service.browse.folder.id,newFolderName.text.trim());newFolder.close()} }
            }
        }
    }
    Native.FolderDialog {
        id:localFolder; title:"Carpeta local para todos los bots"
        onAccepted:{let value=decodeURIComponent(selectedFolder.toString().replace(/^file:\/\//,""));if(/^\/[A-Za-z]:/.test(value))value=value.slice(1);service.setLocalRoot(value)}
    }
}
