import QtQuick 2.15

Item {
    id: h
    property string text: ""
    implicitHeight: 40
    Text {
        id: t
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
        text: h.text.toUpperCase()
        color: Theme.ink
        font.pixelSize: 12
        font.weight: Font.Black
        font.letterSpacing: 2.6
    }
    HatchCanvas {
        anchors.left: t.right
        anchors.leftMargin: 10
        anchors.right: parent.right
        anchors.verticalCenter: t.verticalCenter
        height: 6
        pattern: "diagonal"
        spacing: 3.4
        lineWidth: 1
        jitter: 0.1
        color: Theme.faint
    }
}
