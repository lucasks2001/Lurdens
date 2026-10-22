import QtQuick 2.15
import QtQuick.Controls 2.15

// Histórico da sessão: uma linha por reprodução, a mais recente no topo.
Rectangle {
    id: page
    property bool open: false
    signal closeRequested()

    color: Theme.paper
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 140 } }

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: function(w) { w.accepted = false } }

    PageHeader {
        id: header
        width: parent.width
        title: "HISTÓRICO"
        onBack: page.closeRequested()
        InkButton {
            icon: "trash"
            size: 38
            glyphSize: 19
            enabled: session.historyCount > 0
            tip: "Limpar histórico da sessão"
            onClicked: session.clearHistory()
        }
    }

    Text {
        id: summary
        anchors.top: header.bottom
        anchors.topMargin: 10
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: Theme.margin
        anchors.rightMargin: Theme.margin
        text: (session.historyCount === 1 ? "1 faixa" : session.historyCount + " faixas")
              + (session.historyPersist ? " · salvo entre sessões" : " · nesta sessão")
        color: Theme.muted
        font.pixelSize: 11
        font.weight: Font.Bold
        font.letterSpacing: 1.2
    }

    ListView {
        id: list
        anchors.top: summary.bottom
        anchors.topMargin: 8
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true
        model: session.history
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        cacheBuffer: 400

        delegate: Item {
            width: list.width
            height: 68

            Rectangle {
                id: thumbFrame
                x: Theme.margin
                anchors.verticalCenter: parent.verticalCenter
                width: 50; height: 50
                color: Theme.paperSunken
                border.width: Theme.strokeThin
                border.color: Theme.ink
                Image {
                    anchors.fill: parent
                    anchors.margins: Theme.strokeThin
                    source: modelData.artUrl !== "" ? modelData.artUrl : resourcesUrl + "placeholder-cover.png"
                    sourceSize.width: 96
                    sourceSize.height: 96
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    smooth: true
                    onStatusChanged: if (status === Image.Error) source = resourcesUrl + "placeholder-cover.png"
                }
            }

            Column {
                anchors.left: thumbFrame.right
                anchors.leftMargin: 12
                anchors.right: timeLabel.left
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    width: parent.width
                    text: modelData.title
                    color: Theme.ink
                    font.pixelSize: 13
                    font.weight: Font.Black
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                }
                Text {
                    width: parent.width
                    text: modelData.artist
                    visible: text !== ""
                    color: Theme.inkSoft
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                }
                Text {
                    width: parent.width
                    text: modelData.album
                    visible: text !== ""
                    color: Theme.muted
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                }
            }

            Column {
                id: timeLabel
                anchors.right: parent.right
                anchors.rightMargin: Theme.margin
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    anchors.right: parent.right
                    text: modelData.time
                    color: Theme.ink
                    font.pixelSize: 12
                    font.weight: Font.Bold
                }
                Text {
                    anchors.right: parent.right
                    text: modelData.day
                    color: Theme.muted
                    font.pixelSize: 10
                }
            }

            HatchCanvas {
                anchors.bottom: parent.bottom
                x: Theme.margin
                width: parent.width - 2 * Theme.margin
                height: 3
                visible: index < list.count - 1
                pattern: "dash"
                spacing: 3
                lineWidth: 1.1
                jitter: 0.1
                color: Theme.faint
            }
        }

        // estado vazio
        Column {
            visible: list.count === 0
            anchors.centerIn: parent
            width: Math.min(parent.width - 2 * Theme.margin, 320)
            spacing: 10
            InkGlyph {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 34; height: 34
                name: "history"
                color: Theme.muted
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: "Nada por aqui ainda.\nAs músicas tocadas no Spotify aparecem nesta lista enquanto o Lurdens estiver aberto."
                color: Theme.muted
                font.pixelSize: 12
            }
        }
    }
}
