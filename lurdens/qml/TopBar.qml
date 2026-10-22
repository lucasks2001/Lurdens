import QtQuick 2.15
import QtQuick.Controls 2.15

// Barra superior compacta: marca, estado da conexão, configurações e menu.
// Minimizar/maximizar/fechar ficam na barra de título nativa do KWin.
Rectangle {
    id: bar
    property bool slim: false
    property alias menuAnchor: menuButton
    signal settingsClicked()
    signal menuClicked()
    signal versionClicked()
    signal sleepClicked()
    signal historyClicked()
    readonly property bool narrow: width < 390

    height: slim ? 40 : 46
    color: Theme.paper

    Row {
        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 9

        Image {
            anchors.verticalCenter: parent.verticalCenter
            source: resourcesUrl + "icons/lurdens-64.png"
            width: bar.slim ? 20 : 24
            height: width
            sourceSize.width: 64
            sourceSize.height: 64
            smooth: true
            mipmap: true
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: !bar.narrow
            text: "LURDENS"
            color: Theme.ink
            font.pixelSize: 13
            font.weight: Font.Black
            font.letterSpacing: 3.2
        }
        // indicador de conexão: cheio = conectado; vazado = sem Spotify
        Rectangle {
            id: dot
            anchors.verticalCenter: parent.verticalCenter
            width: 8; height: 8; radius: 4
            color: player.connected ? Theme.ink : "transparent"
            border.width: 1.5
            border.color: player.busAvailable ? Theme.ink : Theme.muted
            MouseArea { id: dotHover; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true }
            ToolTip.visible: dotHover.containsMouse
            ToolTip.delay: 300
            ToolTip.text: !player.busAvailable ? "D-Bus indisponível"
                          : player.connected ? "Conectado ao " + (player.identity || "Spotify")
                          : "Spotify não está aberto"
        }
        VersionBadge {
            anchors.verticalCenter: parent.verticalCenter
            onClicked: bar.versionClicked()
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2

        // temporizador: lua quando desligado, contagem regressiva quando ativo
        InkButton {
            visible: !session.sleepActive
            icon: "moon"
            size: bar.slim ? 34 : 38
            glyphSize: 18
            tip: "Temporizador para dormir  (Ctrl+T)"
            onClicked: bar.sleepClicked()
        }
        Rectangle {
            id: sleepChip
            visible: session.sleepActive
            anchors.verticalCenter: parent.verticalCenter
            width: chipRow.implicitWidth + 14
            height: 26
            color: chipArea.containsMouse ? Theme.paperRaised : Theme.ink
            border.width: Theme.strokeThin
            border.color: Theme.ink
            Row {
                id: chipRow
                anchors.centerIn: parent
                spacing: 5
                InkGlyph {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 13; height: 13
                    name: "moon"
                    color: chipArea.containsMouse ? Theme.ink : Theme.paper
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: session.sleepRemainingText
                    color: chipArea.containsMouse ? Theme.ink : Theme.paper
                    font.pixelSize: 11
                    font.weight: Font.Black
                }
            }
            MouseArea {
                id: chipArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: function(mouse) { bar.sleepClicked() }
            }
            ToolTip.visible: chipArea.containsMouse
            ToolTip.delay: 400
            ToolTip.text: "Pausa o Spotify em " + session.sleepRemainingText
        }
        Item { width: 4; height: 1; visible: sleepChip.visible }
        InkButton {
            icon: "history"
            size: bar.slim ? 34 : 38
            glyphSize: 19
            tip: "Histórico da sessão  (Ctrl+Y)"
            onClicked: bar.historyClicked()
        }
        InkButton {
            icon: "settings"
            size: bar.slim ? 34 : 38
            glyphSize: 19
            tip: "Configurações  (Ctrl+,)"
            onClicked: bar.settingsClicked()
        }
        InkButton {
            id: menuButton
            icon: "menu"
            size: bar.slim ? 34 : 38
            glyphSize: 19
            tip: "Menu"
            onClicked: bar.menuClicked()
        }
    }

    // régua inferior em traço interrompido, como a última faixa das referências
    HatchCanvas {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        height: 4
        pattern: "dash"
        spacing: 4
        lineWidth: 1.4
        jitter: 0.2
        color: Theme.faint
    }
}
