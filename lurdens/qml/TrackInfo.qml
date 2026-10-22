import QtQuick 2.15

// Título, artista e álbum — ou o estado vazio quando não há o que mostrar.
Column {
    id: info
    property bool centered: true
    property string size: "normal"      // small | normal | large
    property bool animate: true
    readonly property real titleSize: size === "large" ? 30 : (size === "small" ? 16 : 21)
    readonly property int hAlign: centered ? Text.AlignHCenter : Text.AlignLeft

    spacing: size === "small" ? 2 : 5

    readonly property bool showTrack: player.hasTrack
    readonly property string emptyTitle: !player.busAvailable ? "Sem acesso ao D-Bus"
                                        : player.connected ? "Nada tocando"
                                        : player.launching ? "Abrindo o Spotify…"
                                        : player.spotifyInstalled ? "Spotify fechado" : "Spotify não encontrado"
    readonly property string emptyText: !player.busAvailable ? "O barramento de sessão não respondeu. Veja Configurações › Sistema."
                                       : player.connected ? "Escolha uma música no Spotify para começar."
                                       : player.launching ? "A música aparece aqui assim que ele estiver pronto."
                                       : player.spotifyInstalled ? "Abra o Spotify para ver e controlar o que está tocando."
                                       : "Instale o Spotify (RPM ou Flatpak) para usar o Lurdens."

    MarqueeText {
        width: info.width
        text: info.showTrack ? (player.title || "Faixa sem título") : info.emptyTitle
        centered: info.centered
        animate: info.animate
        color: Theme.ink
        font.pixelSize: info.titleSize
        font.weight: Font.Black
        font.letterSpacing: -0.3
    }

    Text {
        width: info.width
        visible: info.showTrack ? player.artist !== "" : info.size !== "small"
        text: info.showTrack ? player.artist : info.emptyText
        color: info.showTrack ? Theme.inkSoft : Theme.muted
        horizontalAlignment: info.hAlign
        elide: info.showTrack ? Text.ElideRight : Text.ElideNone
        wrapMode: info.showTrack ? Text.NoWrap : Text.WordWrap
        maximumLineCount: info.showTrack ? 1 : 3
        textFormat: Text.PlainText
        font.pixelSize: info.size === "large" ? 18 : (info.size === "small" ? 13 : 15)
        font.weight: info.showTrack ? Font.DemiBold : Font.Normal
    }

    Text {
        width: info.width
        visible: info.showTrack && player.album !== "" && info.size !== "small"
        text: player.album.toUpperCase()
        color: Theme.muted
        horizontalAlignment: info.hAlign
        elide: Text.ElideRight
        textFormat: Text.PlainText
        font.pixelSize: 11
        font.weight: Font.Bold
        font.letterSpacing: 1.8
        topPadding: 2
    }
}
