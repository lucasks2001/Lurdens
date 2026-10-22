import QtQuick 2.15

Rectangle {
    id: toast
    function show(msg) { label.text = msg; opacity = 1; timer.restart() }

    width: label.implicitWidth + 28
    height: label.implicitHeight + 16
    color: Theme.ink
    opacity: 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 180 } }

    Text {
        id: label
        anchors.centerIn: parent
        color: Theme.paper
        font.pixelSize: 12
        font.weight: Font.Bold
    }
    Timer { id: timer; interval: 2200; onTriggered: toast.opacity = 0 }
}
