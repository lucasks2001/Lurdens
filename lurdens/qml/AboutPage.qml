import QtQuick 2.15

Rectangle {
    id: about
    property bool open: false
    signal closeRequested()

    color: Theme.paper
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    MouseArea { anchors.fill: parent; onClicked: function(m) { about.closeRequested() } }

    HatchCanvas {
        anchors.fill: parent
        pattern: "stipple"
        spacing: 7
        density: 0.5
        lineWidth: 1.4
        color: Theme.faint
    }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 360)
        spacing: 12

        Image {
            anchors.horizontalCenter: parent.horizontalCenter
            source: resourcesUrl + "icons/lurdens-256.png"
            width: Math.min(120, about.height * 0.25)
            height: width
            sourceSize.width: 256
            sourceSize.height: 256
            smooth: true
            mipmap: true
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "LURDENS"
            color: Theme.ink
            font.pixelSize: 26
            font.weight: Font.Black
            font.letterSpacing: 6
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "versão " + app.version
            color: Theme.muted
            font.pixelSize: 12
            font.weight: Font.Bold
            font.letterSpacing: 1.5
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            color: Theme.inkSoft
            font.pixelSize: 13
            text: "Player complementar para o Spotify Desktop no Linux, Windows e macOS. "
                  + "Mostra e controla a música atual via " + player.backendLabel
                  + " — sem contas, senhas ou streaming próprio."
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            color: Theme.muted
            font.pixelSize: 11
            text: "Projeto independente, sem vínculo com o Spotify. Spotify é marca da Spotify AB."
        }
        InkTextButton {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "FECHAR"
            onClicked: about.closeRequested()
        }
    }
}
