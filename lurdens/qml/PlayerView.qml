import QtQuick 2.15
import QtQuick.Window 2.15

// Área principal. Escolhe a composição pelo formato da janela:
//  - retrato (padrão, ~420×720): capa, informações e controles empilhados;
//  - amplo (maximizada/paisagem): capa à esquerda, controles à direita;
//  - mini (altura pequena / modo compacto): faixa horizontal.
Item {
    id: view
    signal diagnosticsRequested()

    property real positionMs: 0
    readonly property string mode: height < 330 ? "mini"
                                 : (width >= 700 && width > height * 1.15 ? "wide" : "portrait")

    function syncPosition() { positionMs = player.positionMs() }

    Connections {
        target: player
        function onChanged() { view.syncPosition() }
    }

    // Só atualiza o relógio enquanto toca e a janela está visível.
    Timer {
        interval: 250
        repeat: true
        running: player.playing && view.visible
                 && view.Window.visibility !== Window.Minimized
                 && view.Window.visibility !== Window.Hidden
        onTriggered: view.syncPosition()
    }

    Loader {
        anchors.fill: parent
        sourceComponent: view.mode === "mini" ? miniLayout
                       : view.mode === "wide" ? wideLayout : portraitLayout
    }

    // ------------------------------------------------------------ retrato
    Component {
        id: portraitLayout
        Item {
            id: p
            readonly property real contentW: Math.min(width - 2 * Theme.margin, 600)
            readonly property real belowH: info.height + progress.height + transport.height
                                           + (volume.visible ? volume.height + col.spacing : 0)
                                           + (actions.visible ? actions.height + col.spacing : 0)
                                           + col.spacing * 3
            readonly property real coverSize: Math.max(110, Math.min(contentW - 10, height - belowH - 40, 640))

            Column {
                id: col
                width: p.contentW
                anchors.horizontalCenter: parent.horizontalCenter
                y: Math.max(12, (p.height - height) / 2)
                spacing: 14

                CoverArt {
                    id: cover
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.horizontalCenterOffset: offset / 2
                    size: p.coverSize
                    source: player.artUrl
                    paused: player.hasTrack && !player.playing
                }
                TrackInfo {
                    id: info
                    width: parent.width
                    centered: true
                }
                EmptyActions {
                    id: actions
                    anchors.horizontalCenter: parent.horizontalCenter
                    onDiagnosticsRequested: view.diagnosticsRequested()
                }
                ProgressBarInk {
                    id: progress
                    width: parent.width
                    positionMs: view.positionMs
                    lengthMs: player.lengthMs
                    seekable: player.canSeek
                    onSeekRequested: function(ms) { player.seek(ms); view.positionMs = ms }
                }
                TransportControls {
                    id: transport
                    anchors.horizontalCenter: parent.horizontalCenter
                }
                VolumeControl {
                    id: volume
                    visible: player.hasVolume
                    width: Math.min(parent.width, 280)
                    anchors.horizontalCenter: parent.horizontalCenter
                }
            }
        }
    }

    // --------------------------------------------------------------- amplo
    Component {
        id: wideLayout
        Item {
            id: w
            readonly property real pad: Theme.margin * 1.6
            readonly property real gap: Math.max(36, width * 0.045)
            readonly property real coverSize: Math.max(200, Math.min(height - 2 * pad - 14, (width - 2 * pad) * 0.52, 860))
            readonly property real columnW: Math.max(260, Math.min(600, width - 2 * pad - coverSize - 14 - gap))

            Row {
                anchors.centerIn: parent
                spacing: w.gap

                CoverArt {
                    anchors.verticalCenter: parent.verticalCenter
                    size: w.coverSize
                    source: player.artUrl
                    paused: player.hasTrack && !player.playing
                }

                Column {
                    width: w.columnW
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 20

                    TrackInfo {
                        width: parent.width
                        centered: false
                        size: w.coverSize > 440 ? "large" : "normal"
                    }
                    EmptyActions {
                        onDiagnosticsRequested: view.diagnosticsRequested()
                    }
                    ProgressBarInk {
                        width: parent.width
                        positionMs: view.positionMs
                        lengthMs: player.lengthMs
                        seekable: player.canSeek
                        onSeekRequested: function(ms) { player.seek(ms); view.positionMs = ms }
                    }
                    TransportControls {
                        playDiameter: 76
                    }
                    VolumeControl {
                        visible: player.hasVolume
                        width: Math.min(parent.width, 320)
                    }
                }
            }
        }
    }

    // ----------------------------------------------------------------- mini
    Component {
        id: miniLayout
        Item {
            id: mi
            readonly property real coverSize: Math.max(56, Math.min(height - 30, 170))

            CoverArt {
                id: miniCover
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                size: mi.coverSize
                source: player.artUrl
                showStamp: false
            }

            Column {
                x: miniCover.x + miniCover.width + 14
                width: mi.width - x - 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                TrackInfo {
                    width: parent.width
                    centered: false
                    size: "small"
                }
                ProgressBarInk {
                    width: parent.width
                    compact: true
                    showTimes: mi.height > 150
                    positionMs: view.positionMs
                    lengthMs: player.lengthMs
                    seekable: player.canSeek
                    onSeekRequested: function(ms) { player.seek(ms); view.positionMs = ms }
                }
                Row {
                    spacing: 4
                    TransportControls { small: true; anchors.verticalCenter: parent.verticalCenter }
                    InkButton {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: player.busAvailable && !player.connected && player.spotifyInstalled
                        enabled: !player.launching
                        icon: "open"
                        size: 34
                        glyphSize: 17
                        tip: "Abrir o Spotify"
                        onClicked: player.launchSpotify()
                    }
                }
            }
        }
    }
}
