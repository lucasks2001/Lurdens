import QtQuick 2.15
import QtQuick.Controls 2.15

// Temporizador para dormir: pausa o Spotify quando o tempo acabar.
Rectangle {
    id: page
    property bool open: false
    property int customMinutes: 20
    signal closeRequested()

    color: Theme.paper
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: function(w) { w.accepted = false } }

    PageHeader {
        id: header
        width: parent.width
        title: "TEMPORIZADOR"
        onBack: page.closeRequested()
    }

    Flickable {
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        contentHeight: col.height + 40
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: col
            x: Math.max(Theme.margin, (parent.width - width) / 2)
            width: Math.min(page.width - 2 * Theme.margin, 420)
            y: 22
            spacing: 18

            // mostrador
            Item {
                width: parent.width
                height: 132
                HatchCanvas {
                    x: 6; y: 6
                    width: parent.width - 6; height: parent.height - 6
                    pattern: session.sleepActive ? "cross" : "diagonal"
                    spacing: 5
                    lineWidth: 1.2
                    color: Theme.shadowInk
                }
                Rectangle {
                    width: parent.width - 6
                    height: parent.height - 6
                    color: Theme.paperRaised
                    border.width: Theme.stroke
                    border.color: Theme.ink
                    Column {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: session.sleepActive ? session.sleepRemainingText : "--:--"
                            color: session.sleepActive ? Theme.ink : Theme.muted
                            font.pixelSize: 46
                            font.weight: Font.Black
                            font.letterSpacing: 1
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: session.sleepActive ? "PARA PAUSAR O SPOTIFY" : "DESLIGADO"
                            color: Theme.muted
                            font.pixelSize: 10
                            font.weight: Font.Bold
                            font.letterSpacing: 2
                        }
                    }
                }
            }

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Ao terminar, o Lurdens envia “pausar” ao Spotify. Nada é encerrado e o computador não é desligado. "
                      + "Continua contando com a janela oculta ou minimizada."
                color: Theme.inkSoft
                font.pixelSize: 12
                lineHeight: 1.1
            }

            // opções rápidas
            Text {
                text: session.sleepActive ? "TROCAR PARA" : "PAUSAR EM"
                color: Theme.ink
                font.pixelSize: 11
                font.weight: Font.Black
                font.letterSpacing: 2
            }
            Grid {
                columns: 4
                spacing: 8
                width: parent.width
                Repeater {
                    model: [15, 30, 45, 60]
                    delegate: InkTextButton {
                        width: (col.width - 3 * 8) / 4
                        text: modelData + " MIN"
                        primary: session.sleepActive && session.sleepDuration === modelData * 60
                        onClicked: session.startSleep(modelData)
                    }
                }
            }

            // duração personalizada
            Row {
                spacing: 8
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Outro:"
                    color: Theme.ink
                    font.pixelSize: 13
                    font.weight: Font.Bold
                }
                InkButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "previous"; size: 34; glyphSize: 14
                    tip: "−5 min"
                    enabled: page.customMinutes > 5
                    onClicked: page.customMinutes = Math.max(1, page.customMinutes - 5)
                }
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 84; height: 34
                    color: Theme.paperRaised
                    border.width: Theme.strokeThin
                    border.color: Theme.ink
                    TextInput {
                        id: minutesInput
                        anchors.fill: parent
                        horizontalAlignment: TextInput.AlignHCenter
                        verticalAlignment: TextInput.AlignVCenter
                        text: page.customMinutes
                        color: Theme.ink
                        font.pixelSize: 14
                        font.weight: Font.Bold
                        selectByMouse: true
                        validator: IntValidator { bottom: 1; top: 720 }
                        onEditingFinished: page.customMinutes = Math.max(1, Math.min(720, parseInt(text) || 1))
                        Keys.onShortcutOverride: function(event) { event.accepted = activeFocus }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "min"
                    color: Theme.muted
                    font.pixelSize: 12
                }
                InkButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "next"; size: 34; glyphSize: 14
                    tip: "+5 min"
                    onClicked: page.customMinutes = Math.min(720, page.customMinutes + 5)
                }
            }
            InkTextButton {
                text: "INICIAR " + page.customMinutes + " MIN"
                icon: "moon"
                onClicked: {
                    page.customMinutes = Math.max(1, Math.min(720, parseInt(minutesInput.text) || page.customMinutes))
                    session.startSleep(page.customMinutes)
                }
            }

            // controles do temporizador ativo
            Row {
                visible: session.sleepActive
                spacing: 8
                InkTextButton { text: "+5 MIN"; onClicked: session.extendSleep(5) }
                InkTextButton { text: "REINICIAR"; onClicked: session.restartSleep() }
                InkTextButton { text: "CANCELAR"; primary: true; onClicked: session.cancelSleep() }
            }
        }
    }
}
