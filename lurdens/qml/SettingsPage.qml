import QtQuick 2.15
import QtQuick.Controls 2.15

// Configurações em uma página que cobre a janela (cabe no formato compacto).
Rectangle {
    id: page
    property bool open: false
    property string focusSection: ""
    signal closeRequested()

    color: Theme.paper
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    function scrollToSystem() { flick.contentY = Math.max(0, systemSection.y - 8) }
    onOpenChanged: if (open && focusSection === "system") Qt.callLater(scrollToSystem)

    // bloqueia cliques para a tela de baixo
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: function(w) { w.accepted = false } }

    Rectangle {
        id: header
        width: parent.width
        height: 46
        color: Theme.paper
        InkButton {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            icon: "back"
            size: 38
            glyphSize: 20
            tip: "Voltar  (Esc)"
            onClicked: page.closeRequested()
        }
        Text {
            anchors.centerIn: parent
            text: "CONFIGURAÇÕES"
            color: Theme.ink
            font.pixelSize: 13
            font.weight: Font.Black
            font.letterSpacing: 3
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.strokeThin; color: Theme.ink }
    }

    Flickable {
        id: flick
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        contentHeight: content.height + 40
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: content
            x: Math.max(Theme.margin, (flick.width - width) / 2)
            width: Math.min(flick.width - 2 * Theme.margin, 560)
            y: 8
            spacing: 2

            // ------------------------------------------------ aparência
            SectionHeader { width: parent.width; text: "Aparência" }
            SettingRow {
                width: parent.width
                title: "Tema"
                description: app.theme === "auto" ? ("Seguindo o sistema (" + (app.systemDark ? "escuro" : "claro") + ")") : ""
                InkSegmented {
                    current: app.theme
                    options: [{ value: "dark", label: "Escuro" }, { value: "light", label: "Claro" }, { value: "auto", label: "Sistema" }]
                    onSelected: function(value) { app.theme = value }
                }
            }
            SettingRow {
                width: parent.width
                title: "Fonte"
                description: app.fontIsJetBrains ? "JetBrains Mono"
                             : "JetBrains Mono não instalada — usando " + app.fontFamily
                               + ". Instale com: sudo dnf install jetbrains-mono-fonts-all"
                Text {
                    text: app.fontIsJetBrains ? "Aa 0123" : "Aa"
                    color: app.fontIsJetBrains ? Theme.ink : Theme.muted
                    font.pixelSize: 15
                    font.weight: Font.Black
                }
            }
            SettingRow {
                width: parent.width
                title: "Modo compacto"
                description: "Mini player horizontal (≈420×184) para deixar num canto da tela. Ctrl+M alterna."
                InkSwitch { checked: app.compactMode; onToggled: function(v) { app.compactMode = v } }
            }

            // --------------------------------------------- comportamento
            SectionHeader { width: parent.width; text: "Comportamento" }
            SettingRow {
                width: parent.width
                title: "Sempre no topo"
                description: app.keepAboveMessage !== "" ? app.keepAboveMessage
                             : (app.isWayland ? "No Wayland é aplicado por um script do KWin." : "")
                InkSwitch { checked: app.alwaysOnTop; onToggled: function(v) { app.alwaysOnTop = v } }
            }
            SettingRow {
                width: parent.width
                title: "Abrir o Spotify junto com o Lurdens"
                description: player.spotifyInstalled ? player.spotifyLabel : "Spotify não encontrado neste sistema"
                enabled: player.spotifyInstalled
                InkSwitch { checked: app.launchSpotifyOnStart; onToggled: function(v) { app.launchSpotifyOnStart = v } }
            }
            SettingRow {
                width: parent.width
                title: "Ícone na bandeja do sistema"
                description: app.trayAvailable ? "Mostra/oculta a janela e controla a reprodução pela bandeja."
                                               : "Bandeja do sistema indisponível nesta sessão."
                enabled: app.trayAvailable
                InkSwitch { checked: app.trayEnabled; onToggled: function(v) { app.trayEnabled = v } }
            }
            SettingRow {
                width: parent.width
                title: "Fechar para a bandeja"
                description: "O botão fechar oculta a janela em vez de encerrar. Use Sair no menu para encerrar."
                enabled: app.trayAvailable && app.trayEnabled
                InkSwitch { checked: app.closeToTray; onToggled: function(v) { app.closeToTray = v } }
            }
            SettingRow {
                width: parent.width
                title: "Iniciar minimizado na bandeja"
                enabled: app.trayAvailable && app.trayEnabled
                InkSwitch { checked: app.startMinimized; onToggled: function(v) { app.startMinimized = v } }
            }

            SettingRow {
                width: parent.width
                title: "Iniciar com o KDE"
                description: "Abre o Lurdens na bandeja ao entrar na sessão. Nunca abre duas cópias."
                InkSwitch { checked: session.autostartEnabled; onToggled: function(v) { session.autostartEnabled = v } }
            }

            // ------------------------------------------------ notificações
            SectionHeader { width: parent.width; text: "Notificações" }
            SettingRow {
                width: parent.width
                title: "Avisar quando a música mudar"
                description: "Capa, título e artista pelas notificações do Plasma (respeita “Não perturbe”). "
                             + "Não avisa ao abrir o app nem com a janela do Lurdens em foco."
                InkSwitch { checked: session.notifyTracks; onToggled: function(v) { session.notifyTracks = v } }
            }
            InkTextButton {
                text: "PREFERÊNCIAS DO KDE"
                icon: "open"
                onClicked: session.openNotificationSettings()
            }

            // ----------------------------------------------------- atalhos
            SectionHeader { width: parent.width; text: "Atalhos globais" }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: session.shortcutsAvailable
                      ? "Funcionam com o Lurdens em segundo plano. Clique num atalho e pressione a nova combinação."
                      : "Indisponíveis: " + session.shortcutsStatus + ". Os atalhos dentro da janela continuam funcionando."
                color: session.shortcutsAvailable ? Theme.inkSoft : Theme.muted
                font.pixelSize: 12
                topPadding: 4
            }
            Repeater {
                model: session.shortcuts
                delegate: SettingRow {
                    width: content.width
                    title: modelData.label
                    description: modelData.conflict ? "Padrão (" + modelData.defaultText + ") já usado por outro programa" : ""
                    enabled: session.shortcutsAvailable
                    ShortcutField {
                        actionId: modelData.id
                        keyText: modelData.text
                        conflict: modelData.conflict
                    }
                }
            }
            Row {
                spacing: 10
                visible: session.shortcutsAvailable
                InkTextButton { text: "RESTAURAR PADRÕES"; onClicked: session.resetShortcuts() }
                InkTextButton { text: "ATALHOS DO KDE"; icon: "keyboard"; onClicked: session.openSystemShortcuts() }
            }

            // ---------------------------------------------------- histórico
            SectionHeader { width: parent.width; text: "Histórico" }
            SettingRow {
                width: parent.width
                title: "Guardar entre sessões"
                description: session.historyPersist ? "Salvo localmente em " + session.historyFile
                                                    : "Desligado: o histórico some ao fechar o Lurdens."
                InkSwitch { checked: session.historyPersist; onToggled: function(v) { session.historyPersist = v } }
            }

            // ------------------------------------------------- tempo de uso
            SectionHeader { width: parent.width; text: "Tempo de uso" }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Quanto tempo o Lurdens fica aberto (inclusive oculto na bandeja). "
                      + "Não é o tempo de música tocando. Períodos com o computador suspenso não contam. "
                      + "Nada sai do seu computador."
                color: Theme.inkSoft
                font.pixelSize: 12
                topPadding: 4
                bottomPadding: 6
            }
            Repeater {
                model: [
                    ["Sessão atual", session.usageSession],
                    ["Hoje", session.usageEnabled ? session.usageToday : "registro desligado"],
                    ["Início da sessão", session.usageStart]
                ]
                delegate: Row {
                    width: content.width
                    spacing: 10
                    Text {
                        width: 150
                        text: modelData[0]
                        color: Theme.muted
                        font.pixelSize: 12
                        font.weight: Font.Bold
                    }
                    Text {
                        width: parent.width - 160
                        text: modelData[1]
                        color: Theme.ink
                        font.pixelSize: 13
                        font.weight: Font.Black
                    }
                }
            }
            Item { width: 1; height: 4 }
            SettingRow {
                width: parent.width
                title: "Registrar o total do dia"
                description: "Guarda só o dia atual em " + session.usageFile + "; recomeça à meia-noite."
                InkSwitch { checked: session.usageEnabled; onToggled: function(v) { session.usageEnabled = v } }
            }
            InkTextButton { text: "REINICIAR CONTADOR DA SESSÃO"; onClicked: session.resetUsageSession() }

            // ---------------------------------------------------- sistema
            SectionHeader { id: systemSection; width: parent.width; text: "Sistema" }
            Column {
                width: parent.width
                spacing: 6
                topPadding: 6
                Repeater {
                    model: [
                        ["D-Bus", player.busAvailable ? "conectado" : "indisponível"],
                        ["Spotify", !player.busAvailable ? "—" : player.connected ? ("conectado · " + (player.status === "Playing" ? "tocando" : player.status === "Paused" ? "pausado" : "parado")) : "não está aberto"],
                        ["Serviço MPRIS", player.busName || "—"],
                        ["Instalação", player.spotifyLabel],
                        ["Recursos", player.connected ? ((player.canSeek ? "busca · " : "") + (player.hasVolume ? "volume · " : "") + (player.hasShuffle ? "aleatório · " : "") + (player.hasLoop ? "repetição" : "")).replace(/ · $/, "") || "básicos" : "—"],
                        ["Sessão gráfica", app.platformName],
                        ["Versão", "Lurdens " + app.version]
                    ]
                    delegate: Row {
                        width: content.width
                        spacing: 10
                        Text {
                            width: 112
                            text: modelData[0]
                            color: Theme.muted
                            font.pixelSize: 12
                            font.weight: Font.Bold
                        }
                        Text {
                            width: parent.width - 122
                            text: modelData[1]
                            color: Theme.ink
                            font.pixelSize: 12
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
            Item { width: 1; height: 12 }
            Text {
                width: parent.width
                text: "<b>Diagnóstico</b><br>"
                      + "• Spotify aberto mas não detectado: feche e abra o Spotify; confira com "
                      + "<i>busctl --user list | grep mpris</i>.<br>"
                      + "• Flatpak: o Spotify precisa da permissão padrão de nome MPRIS (já vem no pacote do Flathub).<br>"
                      + "• Capas não aparecem: verifique a conexão com i.scdn.co.<br>"
                      + "• Volume, aleatório ou repetição desabilitados: a versão do Spotify não os expõe via MPRIS.<br>"
                      + "• Terminal: <i>lurdens --debug</i> mostra mensagens detalhadas."
                textFormat: Text.StyledText
                color: Theme.inkSoft
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                lineHeight: 1.15
            }
            Item { width: 1; height: 10 }
            Row {
                spacing: 10
                InkTextButton { text: "COPIAR DIAGNÓSTICO"; icon: "info"; onClicked: app.copyDiagnostics() }
                InkTextButton { text: "RECONECTAR"; onClicked: player.refresh() }
            }
            Item { width: 1; height: 6 }
            Text {
                width: parent.width
                text: "Configurações salvas em " + app.configPath
                color: Theme.muted
                font.pixelSize: 11
                wrapMode: Text.WrapAnywhere
            }
        }
    }
}
