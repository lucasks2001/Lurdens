import QtQuick 2.15

// Ações do estado vazio: abrir/mostrar o Spotify ou ir ao diagnóstico.
Row {
    id: ea
    signal diagnosticsRequested()
    spacing: 10
    visible: !player.hasTrack

    InkTextButton {
        visible: player.busAvailable && !player.connected && player.spotifyInstalled
        enabled: !player.launching
        primary: true
        icon: "open"
        text: player.launching ? "ABRINDO…" : "ABRIR SPOTIFY"
        onClicked: player.launchSpotify()
    }
    InkTextButton {
        visible: player.connected && !player.hasTrack
        icon: "open"
        text: "MOSTRAR SPOTIFY"
        onClicked: player.canRaise ? player.raisePlayer() : player.launchSpotify()
    }
    InkTextButton {
        visible: !player.busAvailable || (!player.connected && !player.spotifyInstalled)
        icon: "info"
        text: "DIAGNÓSTICO"
        onClicked: ea.diagnosticsRequested()
    }
}
