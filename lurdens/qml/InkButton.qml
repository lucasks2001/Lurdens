import QtQuick 2.15
import QtQuick.Controls 2.15

// Botão de ícone. "available" = recurso suportado pelo player: quando falso
// o botão aparece desabilitado mas ainda mostra a dica explicando o motivo.
Item {
    id: b
    property string icon: "none"
    property bool checkable: false
    property bool checked: false
    property bool available: true
    property string badge: ""
    property string tip: ""
    property real size: 40
    property real glyphSize: 22
    readonly property bool active: enabled && available
    signal clicked()

    implicitWidth: size
    implicitHeight: size

    Accessible.role: Accessible.Button
    Accessible.name: tip
    Accessible.checkable: checkable
    Accessible.checked: checked

    // sombra hachurada que aparece no hover, como o deslocamento das referências
    HatchCanvas {
        x: 4; y: 4
        width: parent.width - 4; height: parent.height - 4
        pattern: "diagonal"
        spacing: 3.6
        lineWidth: 1
        jitter: 0.2
        color: Theme.shadowInk
        visible: b.active && (ma.containsMouse || b.checked) && !ma.pressed
    }

    Rectangle {
        id: face
        x: ma.pressed && b.active ? 3 : 0
        y: x
        width: parent.width - 4
        height: parent.height - 4
        color: b.checked ? Theme.ink : (ma.containsMouse && b.active ? Theme.paperRaised : "transparent")
        border.width: (ma.containsMouse && b.active) || b.checked ? Theme.strokeThin : 0
        border.color: Theme.ink

        InkGlyph {
            anchors.centerIn: parent
            width: b.glyphSize
            height: b.glyphSize
            name: b.icon
            color: b.checked ? Theme.paper : (b.active ? Theme.ink : Theme.muted)
        }

        Text {
            visible: b.badge !== ""
            text: b.badge
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 3
            font.pixelSize: 9
            font.weight: Font.Black
            color: b.checked ? Theme.paper : Theme.ink
        }
    }

    opacity: b.enabled ? (b.available ? 1.0 : 0.45) : 0.3

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: b.active ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: function(mouse) { if (b.active) b.clicked() }
    }

    ToolTip.visible: ma.containsMouse && b.tip !== ""
    ToolTip.delay: 650
    ToolTip.text: b.tip
}
