import QtQuick 2.15
import QtQuick.Controls 2.15

// Texto de uma linha que rola devagar apenas quando não cabe.
//
// A posição horizontal é um binding declarativo sobre a largura REAL do
// texto, então a centralização se corrige no mesmo quadro em que o título
// muda. (Na 1.0 a posição era calculada num handler que rodava antes de o
// texto novo ser medido, e o título ficava deslocado até a próxima rolagem.)
Item {
    id: m
    property string text: ""
    property alias font: label.font
    property color color: Theme.ink
    property bool centered: true
    property bool animate: true
    property real scroll: 0             // deslocamento da rolagem (só quando não cabe)
    readonly property real overflow: Math.max(0, label.implicitWidth - width)

    implicitHeight: label.implicitHeight
    clip: true

    Text {
        id: label
        text: m.text
        color: m.color
        textFormat: Text.PlainText
        y: 0
        x: m.overflow > 0 ? -m.scroll
                          : (m.centered ? Math.round((m.width - implicitWidth) / 2) : 0)
    }

    function restart() {
        anim.stop()
        m.scroll = 0
        if (m.overflow > 0 && m.animate && m.visible)
            anim.start()
    }

    // callLater agrupa várias mudanças do mesmo quadro em um único reinício,
    // já com o texto novo medido.
    onTextChanged: Qt.callLater(restart)
    onOverflowChanged: Qt.callLater(restart)
    onVisibleChanged: Qt.callLater(restart)
    onAnimateChanged: Qt.callLater(restart)
    Component.onCompleted: restart()

    SequentialAnimation {
        id: anim
        loops: Animation.Infinite
        PauseAnimation { duration: 2600 }
        NumberAnimation {
            target: m; property: "scroll"; from: 0; to: m.overflow
            duration: Math.max(800, m.overflow * 30)
            easing.type: Easing.InOutSine
        }
        PauseAnimation { duration: 1800 }
        NumberAnimation { target: m; property: "scroll"; to: 0; duration: 450; easing.type: Easing.OutCubic }
    }

    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }
    ToolTip.visible: hover.containsMouse && m.overflow > 0
    ToolTip.delay: 800
    ToolTip.text: m.text
}
