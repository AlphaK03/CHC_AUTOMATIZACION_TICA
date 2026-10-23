import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"

ApplicationWindow {
    id: window
    objectName: "workbenchWindow"
    width: 1280
    height: 820
    minimumWidth: 1000
    minimumHeight: 680
    visible: true
    title: details.enabled ? "CHC Workbench" : "CHC Workbench · Demostración"
    color: Theme.background
    property bool sidebarExpanded: true
    property bool compact: width < 1120
    property bool initialDark: true
    property QtObject demoBackend: demo
    property string toastMessage: ""
    property string pageTitle: demo.route === "overview" ? "Vista general" : demo.selectedModule.title || "Módulo"
    Component.onCompleted: Theme.dark = initialDark
    function toggleTheme() { Theme.dark = !Theme.dark; preferences.setDark(Theme.dark) }
    property var transitBridge: typeof transit !== 'undefined' ? transit : null
    property var talonBridge: typeof talon !== 'undefined' ? talon : null
    property var movementsBridge: typeof movements !== 'undefined' ? movements : null
    property var manifestsBridge: typeof manifests !== 'undefined' ? manifests : null
    property var blsBridge: typeof bls !== 'undefined' ? bls : null
    property var cloudBridge: typeof sharepoint !== 'undefined' ? sharepoint : null
    property bool closingRequested: false
    function workersClosed() { return [details,transitBridge,talonBridge,movementsBridge,manifestsBridge,blsBridge,cloudBridge].every(bridge => !bridge || !bridge.enabled || bridge.isClosed) }
    onClosing: function(close) {
        demo.csvExports.cancel()
        window.closingRequested = true
        if (!workersClosed()) {
            close.accepted = false
            window.toastMessage = "Guardando pendientes y cerrando módulos…"
            if(details.enabled) details.shutdown()
            if(transitBridge && transitBridge.enabled) transitBridge.shutdown()
            if(talonBridge && talonBridge.enabled) talonBridge.shutdown()
            if(movementsBridge && movementsBridge.enabled) movementsBridge.shutdown()
            if(manifestsBridge && manifestsBridge.enabled) manifestsBridge.shutdown()
            if(blsBridge && blsBridge.enabled) blsBridge.shutdown()
            if(cloudBridge && cloudBridge.enabled) cloudBridge.shutdown()
        }
    }
    Connections { target: details; function onClosed() { if (details.closing && window.workersClosed()) Qt.callLater(window.close) } }
    Connections { target: window.transitBridge; function onClosed() { if(window.transitBridge.closing && window.workersClosed()) Qt.callLater(window.close) } }
    Connections { target: window.talonBridge; function onClosed() { if(window.talonBridge.closing && window.workersClosed()) Qt.callLater(window.close) } }
    Connections { target: window.movementsBridge; function onClosed() { if(window.movementsBridge.closing && window.workersClosed()) Qt.callLater(window.close) } }
    Connections { target: window.manifestsBridge; function onClosed() { if(window.manifestsBridge.closing && window.workersClosed()) Qt.callLater(window.close) } }
    Connections { target: window.blsBridge; function onClosed() { if(window.blsBridge.closing && window.workersClosed()) Qt.callLater(window.close) } }
    Connections { target: window.cloudBridge; function onClosed() { if(window.closingRequested && window.workersClosed()) Qt.callLater(window.close) } }

    Shortcut { sequence: "Ctrl+K"; onActivated: searchInput.forceActiveFocus() }
    Shortcut { sequence: "Ctrl+B"; onActivated: window.sidebarExpanded = !window.sidebarExpanded }
    Shortcut { sequence: "Escape"; onActivated: { searchInput.text = ""; searchInput.focus = false } }

    Connections {
        target: demo
        function onToast(message) { window.toastMessage = message; toastTimer.restart() }
    }
    Timer { id: toastTimer; interval: 4000; onTriggered: window.toastMessage = "" }

    RowLayout {
        objectName: "workbenchControls"
        anchors.fill: parent
        spacing: 0
        Rectangle {
            id: sidebar
            objectName: "sidebar"
            Layout.preferredWidth: window.sidebarExpanded ? (window.compact ? 220 : 244) : 80
            Layout.fillHeight: true
            color: Theme.sidebar
            clip: true
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 200; easing.type: Easing.InOutCubic } }
            Rectangle { width: 1; anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.right: parent.right; color: Theme.border }
            ScrollView {
                id:navigationScroll; objectName:"navigationScroll"
                anchors.fill:parent; anchors.margins:15
                contentWidth:availableWidth; clip:true
                ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                ScrollBar.vertical.active:true
            ColumnLayout {
                width:navigationScroll.availableWidth
                height:Math.max(navigationScroll.availableHeight,implicitHeight)
                spacing: 6
                Item {
                    Layout.fillWidth: true; implicitHeight: 68
                    BrandMark { x: 5; y: 7; width: 40; height: 40 }
                    Column {
                        x: 57; y: 8; spacing: 2; visible: window.sidebarExpanded
                        Text { text: "CHC"; color: Theme.text; font.family: Theme.family; font.pixelSize: 19; font.weight: Font.Bold; font.letterSpacing: 1 }
                        Text { text: "W O R K B E N C H"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 8; font.weight: Font.DemiBold }
                    }
                }
                Text { text: "ESPACIO DE TRABAJO"; visible: window.sidebarExpanded; color: Theme.faint; font.family: Theme.family; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2; Layout.leftMargin: 13; Layout.topMargin: 9; Layout.bottomMargin: 5 }
                NavItem { Layout.fillWidth: true; label: "Vista general"; iconName: "grid"; expanded: window.sidebarExpanded; selected: demo.route === "overview"; onClicked: { searchInput.text = ""; demo.navigate("overview") } }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border; Layout.topMargin: 13; Layout.bottomMargin: 12; Layout.leftMargin: 11; Layout.rightMargin: 11 }
                Text { text: "AUTOMATIZACIONES"; visible: window.sidebarExpanded; color: Theme.faint; font.family: Theme.family; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 1.2; Layout.leftMargin: 13; Layout.bottomMargin: 6 }
                Repeater {
                    model: demo.modules
                    NavItem {
                        required property var modelData
                        Layout.fillWidth: true
                        label: modelData.title; iconName: modelData.icon; iconColor: modelData.color
                        selected: demo.route === modelData.id; expanded: window.sidebarExpanded
                        onClicked: { searchInput.text = ""; demo.navigate(modelData.id) }
                    }
                }
                Item { Layout.fillHeight: true }
                Text { visible: window.sidebarExpanded; text: details.enabled ? "Módulos independientes" : "Modo demostración"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 10; Layout.leftMargin: 13; Layout.bottomMargin: 6 }
                NavItem { Layout.fillWidth: true; label: "Acerca del Workbench"; iconName: "info"; expanded: window.sidebarExpanded; onClicked: aboutDialog.open() }
                NavItem { objectName:"sharePointNavigation"; Layout.fillWidth:true; label:"SharePoint"; iconName:"folder"; expanded:window.sidebarExpanded; onClicked:sharePointDialog.open() }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border; Layout.topMargin: 7; Layout.bottomMargin: 7 }
                RowLayout {
                    Layout.fillWidth: true
                    Item {
                        visible: window.sidebarExpanded
                        Layout.fillWidth: true; implicitHeight: 27
                        Row { anchors.verticalCenter: parent.verticalCenter; spacing: 7; Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 5; height: 5; radius: 2.5; color: Theme.accent } Text { text: details.enabled ? "WORKBENCH  /  0.2" : "DEMO  /  0.2"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 9; font.letterSpacing: 0.8 } }
                    }
                    Button {
                        id: collapseButton
                        objectName: "collapseButton"
                        implicitWidth: 42; implicitHeight: 36; hoverEnabled: true
                        Accessible.name: window.sidebarExpanded ? "Contraer navegación" : "Expandir navegación"
                        ToolTip.visible: hovered; ToolTip.text: Accessible.name + " · Ctrl+B"; ToolTip.delay: 500
                        background: Rectangle { radius: 6; color: collapseButton.hovered ? Theme.hover : "transparent" }
                        contentItem: Icon { name: window.sidebarExpanded ? "collapse" : "expand"; width: 19; height: 19; tint: Theme.muted }
                        onClicked: window.sidebarExpanded = !window.sidebarExpanded
                    }
                }
            }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Rectangle {
                Layout.fillWidth: true; implicitHeight: window.height < 740 ? 56 : 73; color: Theme.background
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: window.compact ? 20 : 32; anchors.rightMargin: window.compact ? 20 : 32; spacing: window.compact ? 12 : 18
                    RowLayout {
                        Layout.fillWidth: true; spacing: 10
                        Text { text: "Workbench"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 12 }
                        Icon { name: "chevron"; width: 12; height: 12; tint: Theme.faint }
                        Text { text: window.pageTitle; color: Theme.text; font.family: Theme.family; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.fillWidth:true; Layout.minimumWidth:0; elide:Text.ElideRight }
                    }
                    Rectangle {
                        Layout.preferredWidth: window.compact ? 180 : 240; height: 35; radius: 7; color: Theme.surface; border.color: searchInput.activeFocus ? Theme.accent : Theme.border
                        Icon { x: 11; anchors.verticalCenter: parent.verticalCenter; name: "search"; width: 16; height: 16; tint: Theme.faint }
                        TextField {
                            id: searchInput
                            objectName: "moduleSearch"
                            anchors.fill: parent; anchors.leftMargin: 32; anchors.rightMargin: 47
                            font.family: Theme.family; font.pixelSize: 11; color: Theme.text
                            placeholderText: "Buscar un módulo"; placeholderTextColor: Theme.faint
                            padding: 0
                            background: Item {}
                            onTextChanged: demo.search(text)
                        }
                        Text { anchors.right: parent.right; anchors.rightMargin: 9; anchors.verticalCenter: parent.verticalCenter; text: "Ctrl K"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 9 }
                    }
                    Button {
                        id: themeButton
                        objectName: "themeButton"
                        implicitWidth: 35; implicitHeight: 35; hoverEnabled: true
                        Accessible.name: Theme.dark ? "Cambiar a tema claro" : "Cambiar a tema oscuro"
                        ToolTip.text: Accessible.name; ToolTip.visible: hovered; ToolTip.delay: 400
                        background: Rectangle { radius: 7; color: themeButton.hovered ? Theme.hover : "transparent" }
                        contentItem: Icon { name: Theme.dark ? "sun" : "moon"; tint: Theme.muted; width: 18; height: 18 }
                        onClicked: window.toggleTheme()
                    }
                    Button {
                        id: profileButton; objectName:"accountProfileButton"; implicitWidth:36; implicitHeight:36
                        hoverEnabled:true; padding:0; background:Item {}
                        Accessible.name: window.cloudBridge && window.cloudBridge.connected ? "Cuenta de " + (window.cloudBridge.profile.displayName || window.cloudBridge.account) : "Conectar cuenta de SharePoint"
                        ToolTip.visible:hovered; ToolTip.text:Accessible.name; ToolTip.delay:350
                        contentItem:AccountAvatar {
                            objectName:"headerAccountAvatar"
                            connected:!!window.cloudBridge && window.cloudBridge.connected
                            displayName:window.cloudBridge ? window.cloudBridge.profile.displayName || window.cloudBridge.account : ""
                            photoUrl:window.cloudBridge ? window.cloudBridge.profile.photoUrl || "" : ""
                        }
                        onClicked: profileMenu.popup()
                        Menu {
                            id:profileMenu; objectName:"accountProfileMenu"; width:280
                            MenuItem { text:window.cloudBridge && window.cloudBridge.connected ? window.cloudBridge.profile.displayName || window.cloudBridge.account : "Sin cuenta conectada"; enabled:false }
                            MenuItem { visible:!!window.cloudBridge && window.cloudBridge.connected; text:window.cloudBridge ? window.cloudBridge.account : ""; enabled:false }
                            MenuSeparator {}
                            MenuItem { text:"SharePoint"; onTriggered:sharePointDialog.open() }
                            MenuItem { text:window.cloudBridge && window.cloudBridge.connected ? "Cambiar cuenta…" : "Conectar cuenta…"; enabled:!!window.cloudBridge && window.cloudBridge.enabled && !window.cloudBridge.busy; onTriggered:window.cloudBridge.connectAccount() }
                            MenuItem { text:"Actualizar perfil"; visible:!!window.cloudBridge && window.cloudBridge.connected; enabled:!!window.cloudBridge && !window.cloudBridge.busy; onTriggered:window.cloudBridge.refreshProfile() }
                            MenuItem { text:"Desconectar"; visible:!!window.cloudBridge && window.cloudBridge.connected; enabled:!!window.cloudBridge && !window.cloudBridge.busy; onTriggered:window.cloudBridge.disconnectAccount() }
                        }
                    }
                }
                Rectangle { height: 1; color: Theme.border; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom }
            }
            Item {
                Layout.fillWidth: true; Layout.fillHeight: true
                Loader {
                    id: pageLoader
                    anchors.fill: parent; anchors.margins: window.compact ? 20 : 32; anchors.bottomMargin: 20
                    sourceComponent: demo.route === "overview" ? dashboardComponent : demo.route === "detalles" && details.enabled ? detailsComponent : demo.route === "duas_transito" && window.transitBridge && window.transitBridge.enabled ? transitComponent : demo.route === "talon" && window.talonBridge && window.talonBridge.enabled ? talonComponent : demo.route === "xmovimientos" && window.movementsBridge && window.movementsBridge.enabled ? movementsComponent : demo.route === "manifiestos" && window.manifestsBridge && window.manifestsBridge.enabled ? manifestsComponent : demo.route === "bls" && window.blsBridge && window.blsBridge.enabled ? blsComponent : demoComponent
                    Component { id: dashboardComponent; Dashboard {} }
                    Component { id: detailsComponent; DetallesPage { moduleBridge: details } }
                    Component { id: transitComponent; DetallesPage { moduleBridge: window.transitBridge } }
                    Component { id: talonComponent; DetallesPage { moduleBridge: window.talonBridge } }
                    Component { id: movementsComponent; DetallesPage { moduleBridge: window.movementsBridge } }
                    Component { id: manifestsComponent; ManifiestosPage { moduleBridge: window.manifestsBridge } }
                    Component { id: blsComponent; ManifiestosPage { moduleBridge: window.blsBridge } }
                    Component { id: demoComponent; BotPage {} }
                }
                Rectangle {
                    visible: window.toastMessage !== ""
                    anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 23
                    width: Math.min(parent.width - 50, toastLabel.implicitWidth + 62); height: 48; radius: 9
                    color: Theme.dark ? "#2d3a3b" : "#e3f2eb"; border.color: Theme.success; z: 10
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 15; spacing: 10
                        Icon { name: "check"; tint: Theme.success; width: 18; height: 18 }
                        Text { id: toastLabel; text: window.toastMessage; color: Theme.text; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                    }
                }
            }
        }
    }

    SharePointDialog { id:sharePointDialog; objectName:"sharePointDialog"; service:window.cloudBridge }

    AppDialog {
        id: aboutDialog
        objectName:"aboutDialog"
        title: "Acerca de CHC Workbench"
        anchors.centerIn: parent
        width: 460
        modal: true
        standardButtons: Dialog.Close
        padding: 24
        palette.windowText: Theme.text
        palette.buttonText: Theme.text
        palette.button: Theme.raised
        background: Panel {}
        contentItem: ColumnLayout {
            spacing: 15
            RowLayout {
                spacing: 12
                BrandMark { Layout.preferredWidth: 48; Layout.preferredHeight: 48 }
                Text { text: "CHC Consultores"; color: Theme.text; font.family: Theme.family; font.pixelSize: 19; font.weight: Font.DemiBold }
            }
            Text { text: "Un solo espacio para toda tu operación."; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Text { text: details.enabled ? "Los módulos tienen motores independientes y almacenamiento propio. Manifiestos incluye cinco procedimientos y preparación de bases para BLs." : "Modo de demostración: los espacios usan datos sintéticos y no realizan consultas a TICA."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Text { text: "Versión 0.2 · Integración modular\nCtrl+K: buscar  ·  Ctrl+B: contraer navegación"; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
    }
    AppDialog {
        id: roadmapDialog
        objectName:"roadmapDialog"
        title: "Bases e integraciones"
        anchors.centerIn: parent
        width: 460
        modal: true
        standardButtons: Dialog.Close
        padding: 24
        palette.windowText: Theme.text
        palette.buttonText: Theme.text
        palette.button: Theme.raised
        background: Panel {}
        contentItem: ColumnLayout {
            spacing: 15
            Icon { name: "database"; tint: Theme.accent; width: 32; height: 32 }
            Text { text: "El siguiente paso: bases integradas."; color: Theme.text; font.family: Theme.family; font.pixelSize: 17; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Text { text: "Aquí podrás preparar y administrar las bases que consumen los bots. La integración de DUAS_SCRAPPING y otros generadores se realizará en una etapa posterior."; color: Theme.muted; font.family: Theme.family; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Text { text: "Esta sección presenta el objetivo futuro y todavía no carga archivos ni ejecuta procesos."; color: Theme.faint; font.family: Theme.family; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
    }
}
