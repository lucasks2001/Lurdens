import QtQuick 2.15
import QtQuick.Controls 2.15

// Botão principal: um disco de tinta com sombra hachurada, como as esferas
// sombreadas das referências. Ao pressionar ele "afunda" sobre a sombra.
Item {
    id: pb
    property bool playing: false
    property real diameter: 72
    readonly property real offset: Math.round(diameter * 0.09)
    signal clicked()

    implicitWidth: diameter + offset
    implicitHeight: diameter + offset

    Accessible.role: Accessible.Button
    Accessible.name: playing ? "Pausar" : "Reproduzir"

    // sombra: hachura recortada em círculo
    Canvas {
        id: shadow
        x: pb.offset; y: pb.offset
        width: pb.diameter; height: pb.diameter
        visible: pb.enabled
        property color ink: Theme.shadowInk
        onInkChanged: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var r = width / 2
            ctx.save()
            ctx.beginPath()
            ctx.arc(r, r, r - 0.5, 0, Math.PI * 2)
            ctx.clip()
            ctx.strokeStyle = Theme.rgba(ink)
            ctx.lineWidth = 1.3
            ctx.beginPath()
            for (var k = -width; k < width * 2; k += 4.2) {
                ctx.moveTo(k, height)
                ctx.lineTo(k + height, 0)
            }
            ctx.stroke()
            ctx.restore()
            ctx.beginPath()
            ctx.arc(r, r, r - 1, 0, Math.PI * 2)
            ctx.lineWidth = 1.6
            ctx.stroke()
        }
    }

    Rectangle {
        id: disc
        width: pb.diameter
        height: pb.diameter
        radius: width / 2
        x: ma.pressed ? pb.offset * 0.8 : 0
        y: x
        color: pb.enabled ? Theme.ink : Theme.faint
        scale: ma.containsMouse && !ma.pressed ? 1.03 : 1.0
        Behavior on scale { NumberAnimation { duration: 120 } }

        // anel fino interno, como o reflexo das esferas
        Rectangle {
            anchors.fill: parent
            anchors.margins: 5
            radius: width / 2
            color: "transparent"
            border.width: 1.5
            border.color: Theme.paper
            opacity: ma.containsMouse ? 0.55 : 0.0
            Behavior on opacity { NumberAnimation { duration: 140 } }
        }

        InkGlyph {
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: pb.playing ? 0 : pb.diameter * 0.03
            width: pb.diameter * 0.46
            height: width
            name: pb.playing ? "pause" : "play"
            color: pb.enabled ? Theme.paper : Theme.muted
        }
    }

    MouseArea {
        id: ma
        anchors.fill: disc
        hoverEnabled: true
        enabled: pb.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) { pb.clicked() }
    }

    ToolTip.visible: ma.containsMouse
    ToolTip.delay: 650
    ToolTip.text: (playing ? "Pausar" : "Reproduzir") + "  (Espaço)"
}
