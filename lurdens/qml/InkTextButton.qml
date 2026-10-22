import QtQuick 2.15

// Botão retangular com contorno grosso e sombra hachurada (as barras das referências).
Item {
    id: b
    property string text: ""
    property string icon: ""
    property bool primary: false
    readonly property bool inverted: primary !== (ma.containsMouse && enabled)
    signal clicked()

    implicitWidth: row.implicitWidth + 30 + 5
    implicitHeight: 38 + 5
    opacity: enabled ? 1 : 0.4

    Accessible.role: Accessible.Button
    Accessible.name: text

    HatchCanvas {
        x: 5; y: 5
        width: parent.width - 5
        height: parent.height - 5
        pattern: "diagonal"
        spacing: 3.8
        lineWidth: 1.1
        jitter: 0.2
        color: Theme.shadowInk
    }

    Rectangle {
        id: face
        x: ma.pressed ? 4 : 0
        y: x
        width: parent.width - 5
        height: parent.height - 5
        color: b.inverted ? Theme.ink : Theme.paperRaised
        border.width: Theme.strokeThin + 1
        border.color: Theme.ink

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            InkGlyph {
                visible: b.icon !== ""
                anchors.verticalCenter: parent.verticalCenter
                width: 17; height: 17
                name: b.icon
                color: b.inverted ? Theme.paper : Theme.ink
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: b.text
                color: b.inverted ? Theme.paper : Theme.ink
                font.pixelSize: 13
                font.weight: Font.Black
                font.letterSpacing: 1
            }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        enabled: b.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) { b.clicked() }
    }
}
