import QtQuick 2.15
import QtQuick.Controls 2.15

// "Novidades": histórico de versões, a mais recente primeiro.
Rectangle {
    id: page
    property bool open: false
    signal closeRequested()

    color: Theme.paper
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    onOpenChanged: if (open) { flick.contentY = 0; app.markVersionSeen() }

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: function(w) { w.accepted = false } }

    Rectangle {
        id: header
        width: parent.width
        height: 46
        color: Theme.paper
        InkButton {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            icon: "back"
            size: 38
            glyphSize: 20
            tip: "Voltar  (Esc)"
            onClicked: page.closeRequested()
        }
        Text {
            anchors.centerIn: parent
            text: "NOVIDADES"
            color: Theme.ink
            font.pixelSize: 13
            font.weight: Font.Black
            font.letterSpacing: 3
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.strokeThin; color: Theme.ink }
    }

    Flickable {
        id: flick
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        contentHeight: content.height + 40
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: content
            x: Math.max(Theme.margin, (flick.width - width) / 2)
            width: Math.min(flick.width - 2 * Theme.margin, 560)
            y: 18
            spacing: 26

            Repeater {
                model: app.changelog
                delegate: Column {
                    width: content.width
                    spacing: 10
                    readonly property bool current: index === 0

                    Row {
                        spacing: 10
                        // selo da versão, cheio na atual
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: vText.implicitWidth + 16
                            height: 26
                            color: current ? Theme.ink : "transparent"
                            border.width: Theme.strokeThin
                            border.color: Theme.ink
                            Text {
                                id: vText
                                anchors.centerIn: parent
                                text: "v" + modelData.version
                                color: current ? Theme.paper : Theme.ink
                                font.pixelSize: 13
                                font.weight: Font.Black
                                font.letterSpacing: 1
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.date + (current ? "  ·  VERSÃO ATUAL" : "")
                            color: Theme.muted
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            font.letterSpacing: 1.2
                        }
                    }

                    Repeater {
                        model: modelData.changes
                        delegate: Row {
                            width: content.width
                            spacing: 10
                            Rectangle {
                                y: 6
                                width: 6; height: 6
                                color: Theme.ink
                            }
                            Text {
                                width: parent.width - 16
                                text: modelData
                                color: Theme.inkSoft
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                                lineHeight: 1.12
                            }
                        }
                    }

                    HatchCanvas {
                        width: parent.width
                        height: 5
                        visible: index < app.changelog.length - 1
                        pattern: "dash"
                        spacing: 4
                        lineWidth: 1.3
                        jitter: 0.2
                        color: Theme.faint
                    }
                }
            }
        }
    }
}
