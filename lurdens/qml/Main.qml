import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

ApplicationWindow {
    id: win
    // a janela é exibida pelo Python depois de restaurar tamanho e posição
    visible: false
    width: 420
    height: 720
    minimumWidth: 320
    minimumHeight: 160
    title: player.hasTrack ? (player.title + " · Lurdens") : "Lurdens"
    color: Theme.paper

    property bool settingsOpen: false
    property bool aboutOpen: false
    property bool changelogOpen: false
    property bool historyOpen: false
    property bool sleepOpen: false
    readonly property bool overlayOpen: settingsOpen || aboutOpen || changelogOpen || historyOpen || sleepOpen
    readonly property bool fullScreen: visibility === Window.FullScreen

    font.family: Theme.fontFamily

    function toggleFullScreen() {
        if (fullScreen) showNormal(); else showFullScreen()
    }
    function closeOverlays() {
        settingsOpen = false; aboutOpen = false; changelogOpen = false
        historyOpen = false; sleepOpen = false
    }
    function openChangelog() { closeOverlays(); changelogOpen = true }
    function openHistory() { closeOverlays(); historyOpen = true }
    function openSleep() { closeOverlays(); sleepOpen = true }
    function openSettings(section) {
        closeOverlays()
        settings.focusSection = section || ""
        settingsOpen = true
    }

    onClosing: function(close) { close.accepted = app.handleClose() }

    Connections {
        target: app
        function onNotify(message) { toast.show(message) }
    }

    TopBar {
        id: topBar
        width: parent.width
        slim: playerView.mode === "mini"
        onSettingsClicked: win.openSettings("")
        onVersionClicked: win.openChangelog()
        onSleepClicked: win.openSleep()
        onHistoryClicked: win.openHistory()
        onMenuClicked: mainMenu.popup(topBar.menuAnchor, topBar.menuAnchor.width - mainMenu.width, topBar.menuAnchor.height)
    }

    // easter egg "Ludens": fica atrás do player, nunca sobre os controles
    EasterBackground {
        anchors.top: topBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
    }

    PlayerView {
        id: playerView
        anchors.top: topBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        onDiagnosticsRequested: win.openSettings("system")
    }

    SettingsPage {
        id: settings
        anchors.fill: parent
        open: win.settingsOpen
        onCloseRequested: win.settingsOpen = false
    }

    AboutPage {
        anchors.fill: parent
        open: win.aboutOpen
        onCloseRequested: win.aboutOpen = false
    }

    HistoryPage {
        anchors.fill: parent
        open: win.historyOpen
        onCloseRequested: win.historyOpen = false
    }

    SleepTimerPage {
        anchors.fill: parent
        open: win.sleepOpen
        onCloseRequested: win.sleepOpen = false
    }

    ChangelogPage {
        anchors.fill: parent
        open: win.changelogOpen
        onCloseRequested: win.changelogOpen = false
    }

    Toast {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 18
    }

    Menu {
        id: mainMenu
        topPadding: 6
        bottomPadding: 6
        background: Rectangle {
            implicitWidth: 250
            color: Theme.paperRaised
            border.width: Theme.strokeThin
            border.color: Theme.ink
        }

        InkMenuItem { text: "Histórico"; iconName: "history"; shortcutText: "Ctrl+Y"; onTriggered: win.openHistory() }
        InkMenuItem {
            text: session.sleepActive ? "Temporizador · " + session.sleepRemainingText : "Temporizador para dormir"
            iconName: "moon"; shortcutText: "Ctrl+T"
            onTriggered: win.openSleep()
        }
        InkMenuItem { text: "Configurações"; iconName: "settings"; shortcutText: "Ctrl+,"; onTriggered: win.openSettings("") }
        InkMenuItem {
            text: "Modo compacto"; iconName: "compact"; shortcutText: "Ctrl+M"
            marked: app.compactMode
            onTriggered: app.compactMode = !app.compactMode
        }
        InkMenuItem {
            text: "Sempre no topo"; iconName: "pin"
            marked: app.alwaysOnTop
            onTriggered: app.alwaysOnTop = !app.alwaysOnTop
        }
        InkMenuItem {
            text: win.fullScreen ? "Sair da tela cheia" : "Tela cheia"; iconName: "fullscreen"; shortcutText: "F11"
            onTriggered: win.toggleFullScreen()
        }
        MenuSeparator {
            contentItem: Rectangle { implicitHeight: 1; implicitWidth: 230; color: Theme.faint }
        }
        InkMenuItem {
            text: "Ocultar na bandeja"; iconName: "tray"; shortcutText: "Ctrl+H"
            visible: app.trayAvailable && app.trayEnabled
            onTriggered: app.hideToTray()
        }
        InkMenuItem { text: "Novidades da versão " + app.version; iconName: "check"; onTriggered: win.openChangelog() }
        InkMenuItem { text: "Sobre o Lurdens"; iconName: "info"; onTriggered: { win.closeOverlays(); win.aboutOpen = true } }
        InkMenuItem { text: "Sair"; iconName: "power"; shortcutText: "Ctrl+Q"; onTriggered: app.quit() }
    }

    // ------------------------------------------------------------- atalhos
    Shortcut { sequence: "Space"; enabled: !win.overlayOpen; onActivated: player.playPause() }
    Shortcut { sequence: "Ctrl+Right"; onActivated: player.next() }
    Shortcut { sequence: "Ctrl+Left"; onActivated: player.previous() }
    Shortcut { sequence: "Right"; enabled: !win.overlayOpen; onActivated: player.seekRelative(5000) }
    Shortcut { sequence: "Left"; enabled: !win.overlayOpen; onActivated: player.seekRelative(-5000) }
    Shortcut { sequence: "Up"; enabled: !win.overlayOpen && player.hasVolume; onActivated: player.setVolume(Math.min(1, player.volume + 0.05)) }
    Shortcut { sequence: "Down"; enabled: !win.overlayOpen && player.hasVolume; onActivated: player.setVolume(Math.max(0, player.volume - 0.05)) }
    Shortcut { sequence: "S"; enabled: !win.overlayOpen; onActivated: player.toggleShuffle() }
    Shortcut { sequence: "R"; enabled: !win.overlayOpen; onActivated: player.cycleLoop() }
    Shortcut { sequence: "F11"; onActivated: win.toggleFullScreen() }
    Shortcut { sequence: "Ctrl+M"; onActivated: app.compactMode = !app.compactMode }
    Shortcut { sequence: "Ctrl+,"; onActivated: win.openSettings("") }
    Shortcut { sequence: "Ctrl+H"; enabled: app.trayAvailable && app.trayEnabled; onActivated: app.hideToTray() }
    Shortcut { sequence: "Ctrl+Q"; onActivated: app.quit() }
    Shortcut { sequence: "Ctrl+Y"; onActivated: win.historyOpen ? win.historyOpen = false : win.openHistory() }
    Shortcut { sequence: "Ctrl+T"; onActivated: win.sleepOpen ? win.sleepOpen = false : win.openSleep() }
    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (win.historyOpen) win.historyOpen = false
            else if (win.sleepOpen) win.sleepOpen = false
            else if (win.changelogOpen) win.changelogOpen = false
            else if (win.aboutOpen) win.aboutOpen = false
            else if (win.settingsOpen) win.settingsOpen = false
            else if (win.fullScreen) win.showNormal()
        }
    }
}
