import QtQuick 2.15
import QtQuick.Controls 2.15

// Volume via MPRIS. Só aparece quando o Spotify expõe a propriedade Volume.
Row {
    id: vol
    property real lastNonZero: 0.6
    property real dragValue: 0
    readonly property bool dragging: area.pressed
    readonly property real shown: dragging ? dragValue : player.volume

    spacing: 8
    height: 30

    function setTo(v) {
        v = Math.max(0, Math.min(1, v))
        if (v > 0.01) lastNonZero = v
        player.setVolume(v)
    }

    InkButton {
        anchors.verticalCenter: parent.verticalCenter
        size: 30
        glyphSize: 18
        icon: vol.shown <= 0.001 ? "mute" : (vol.shown < 0.5 ? "volumeLow" : "volume")
        tip: vol.shown <= 0.001 ? "Restaurar volume" : "Silenciar"
        onClicked: vol.setTo(vol.shown <= 0.001 ? vol.lastNonZero : 0)
    }

    Item {
        id: track
        width: vol.width - 30 - vol.spacing - pct.width - vol.spacing
        height: 9
        anchors.verticalCenter: parent.verticalCenter

        Rectangle {
            anchors.fill: parent
            color: Theme.paperRaised
            border.width: Theme.strokeThin
            border.color: Theme.ink
        }
        Item {
            x: Theme.strokeThin; y: Theme.strokeThin
            height: parent.height - 2 * Theme.strokeThin
            width: Math.max(0, (parent.width - 2 * Theme.strokeThin) * vol.shown)
            clip: true
            HatchCanvas {
                width: track.width
                height: parent.height
                pattern: "diagonal"
                spacing: 3.2
                lineWidth: 1
                jitter: 0.15
                color: Theme.ink
            }
        }
        Rectangle {
            width: 4
            height: 17
            anchors.verticalCenter: parent.verticalCenter
            x: Math.max(0, Math.min(track.width - width, track.width * vol.shown - width / 2))
            color: Theme.ink
        }
        MouseArea {
            id: area
            anchors.fill: parent
            anchors.margins: -9
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            function valueAt(mx) { return Math.max(0, Math.min(1, (mx - 9) / Math.max(1, track.width))) }
            onPressed: function(mouse) { vol.dragValue = valueAt(mouse.x); vol.setTo(vol.dragValue) }
            onPositionChanged: function(mouse) { if (pressed) { vol.dragValue = valueAt(mouse.x); vol.setTo(vol.dragValue) } }
            onWheel: function(wheel) { vol.setTo(player.volume + (wheel.angleDelta.y > 0 ? 0.05 : -0.05)) }
        }
    }

    Text {
        id: pct
        width: 34
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: Text.AlignRight
        text: Math.round(vol.shown * 100) + "%"
        color: Theme.muted
        font.pixelSize: 11
        font.weight: Font.Bold
    }
}
