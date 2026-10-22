import QtQuick 2.15

// Aleatório · anterior · reproduzir/pausar · próxima · repetição
Row {
    id: tc
    property bool small: false
    property real playDiameter: small ? 42 : 70

    spacing: small ? 4 : 12

    InkButton {
        visible: !tc.small
        anchors.verticalCenter: parent.verticalCenter
        icon: "shuffle"
        size: 40
        glyphSize: 20
        checkable: true
        checked: player.hasShuffle && player.shuffle
        available: player.hasShuffle
        enabled: player.connected
        tip: !player.connected ? "Aleatório" :
             player.hasShuffle ? (player.shuffle ? "Aleatório: ligado  (S)" : "Aleatório: desligado  (S)")
                               : "Aleatório não é suportado por esta versão do Spotify"
        onClicked: player.toggleShuffle()
    }

    InkButton {
        anchors.verticalCenter: parent.verticalCenter
        icon: "previous"
        size: tc.small ? 34 : 46
        glyphSize: tc.small ? 17 : 22
        enabled: player.canPrevious
        tip: "Música anterior  (Ctrl+←)"
        onClicked: player.previous()
    }

    PlayButton {
        anchors.verticalCenter: parent.verticalCenter
        diameter: tc.playDiameter
        playing: player.playing
        enabled: player.canPlayPause
        onClicked: player.playPause()
    }

    InkButton {
        anchors.verticalCenter: parent.verticalCenter
        icon: "next"
        size: tc.small ? 34 : 46
        glyphSize: tc.small ? 17 : 22
        enabled: player.canNext
        tip: "Próxima música  (Ctrl+→)"
        onClicked: player.next()
    }

    InkButton {
        visible: !tc.small
        anchors.verticalCenter: parent.verticalCenter
        icon: "repeat"
        size: 40
        glyphSize: 20
        checkable: true
        checked: player.hasLoop && player.loopStatus !== "None"
        badge: player.hasLoop && player.loopStatus === "Track" ? "1" : ""
        available: player.hasLoop
        enabled: player.connected
        tip: !player.connected ? "Repetição" :
             !player.hasLoop ? "Repetição não é suportada por esta versão do Spotify" :
             player.loopStatus === "Track" ? "Repetir: esta música  (R)" :
             player.loopStatus === "Playlist" ? "Repetir: lista/álbum  (R)" : "Repetir: desligado  (R)"
        onClicked: player.cycleLoop()
    }
}
