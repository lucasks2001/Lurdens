import QtQuick 2.15
import QtQuick.Controls 2.15

// Barra de progresso: moldura de tinta, preenchimento em hachura cruzada.
Item {
    id: bar
    property real positionMs: 0
    property real lengthMs: 0
    property bool seekable: false
    property bool showTimes: true
    property bool compact: false
    signal seekRequested(real ms)

    readonly property bool dragging: area.pressed && seekable
    property real dragMs: 0
    readonly property real shownMs: dragging ? dragMs : positionMs
    readonly property real frac: lengthMs > 0 ? Math.max(0, Math.min(1, shownMs / lengthMs)) : 0

    implicitHeight: track.height + 12 + (showTimes ? times.implicitHeight + 4 : 0)

    function fmt(ms) {
        if (!(ms >= 0)) return "–:––"
        var t = Math.floor(ms / 1000), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60
        var ss = (s < 10 ? "0" : "") + s
        if (h > 0) return h + ":" + (m < 10 ? "0" : "") + m + ":" + ss
        return m + ":" + ss
    }

    Item {
        id: track
        y: 6
        width: parent.width
        height: bar.compact ? 9 : 13

        Rectangle {
            anchors.fill: parent
            color: Theme.paperRaised
            border.width: Theme.strokeThin
            border.color: bar.lengthMs > 0 ? Theme.ink : Theme.faint
        }

        Item {
            x: Theme.strokeThin
            y: Theme.strokeThin
            height: parent.height - 2 * Theme.strokeThin
            width: Math.max(0, (parent.width - 2 * Theme.strokeThin) * bar.frac)
            clip: true
            HatchCanvas {
                width: track.width
                height: parent.height
                pattern: "cross"
                spacing: 4.2
                lineWidth: 1.1
                jitter: 0.25
                color: Theme.ink
            }
        }

        Rectangle {
            id: knob
            visible: bar.seekable
            width: area.containsMouse || bar.dragging ? 7 : 5
            height: track.height + (bar.compact ? 8 : 12)
            x: Math.max(0, Math.min(track.width - width, track.width * bar.frac - width / 2))
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.ink
            border.width: 1
            border.color: Theme.paper
        }
    }

    MouseArea {
        id: area
        x: -8
        y: 0
        width: track.width + 16
        height: track.y + track.height + 8
        enabled: bar.seekable
        hoverEnabled: true
        cursorShape: bar.seekable ? Qt.PointingHandCursor : Qt.ArrowCursor
        function msAt(mx) {
            return Math.max(0, Math.min(1, (mx - 8) / Math.max(1, track.width))) * bar.lengthMs
        }
        onPressed: function(mouse) { bar.dragMs = msAt(mouse.x) }
        onPositionChanged: function(mouse) { if (pressed) bar.dragMs = msAt(mouse.x) }
        onReleased: function(mouse) { bar.seekRequested(bar.dragMs) }
    }

    ToolTip {
        parent: knob
        visible: bar.dragging
        text: bar.fmt(bar.dragMs)
        y: -height - 6
    }

    Item {
        id: times
        visible: bar.showTimes
        anchors.top: track.bottom
        anchors.topMargin: 6
        width: parent.width
        implicitHeight: elapsed.implicitHeight
        Text {
            id: elapsed
            text: bar.lengthMs > 0 || bar.positionMs > 0 ? bar.fmt(bar.shownMs) : "–:––"
            color: Theme.inkSoft
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
        Text {
            anchors.right: parent.right
            text: bar.lengthMs > 0 ? bar.fmt(bar.lengthMs) : "–:––"
            color: Theme.muted
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
    }
}
