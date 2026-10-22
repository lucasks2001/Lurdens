import QtQuick 2.15

// Capa com moldura de tinta e sombra hachurada deslocada.
// O tamanho total inclui o deslocamento da sombra.
Item {
    id: cover
    property string source: ""
    property real size: 300
    property bool paused: false
    property bool showStamp: true
    readonly property real offset: Math.max(5, Math.round(size * 0.026))
    readonly property bool hasArt: source !== "" && art.status === Image.Ready

    width: size + offset
    height: size + offset
    implicitWidth: width
    implicitHeight: height

    HatchCanvas {
        x: cover.offset
        y: cover.offset
        width: cover.size
        height: cover.size
        pattern: "diagonal"
        spacing: 5
        lineWidth: 1.4
        color: Theme.shadowInk
    }

    Rectangle {
        id: frame
        width: cover.size
        height: cover.size
        color: Theme.paperSunken
        border.width: cover.size > 160 ? Theme.stroke : Theme.strokeThin
        border.color: Theme.ink

        Image {
            id: placeholder
            anchors.fill: parent
            anchors.margins: frame.border.width
            source: resourcesUrl + "placeholder-cover.png"
            fillMode: Image.PreserveAspectCrop
            sourceSize.width: 640
            sourceSize.height: 640
            smooth: true
            mipmap: true
            visible: !cover.hasArt || art.opacity < 1
        }

        Image {
            id: art
            anchors.fill: parent
            anchors.margins: frame.border.width
            source: cover.source
            fillMode: Image.PreserveAspectFit   // nunca distorce nem corta a arte
            asynchronous: true
            cache: true
            smooth: true
            mipmap: true
            sourceSize.width: 640
            sourceSize.height: 640
            opacity: 0
            onSourceChanged: opacity = 0
            onStatusChanged: {
                if (status === Image.Ready)
                    fadeIn.restart()
                else if (status === Image.Error)
                    opacity = 0     // erro de leitura: fica a capa alternativa
            }
            NumberAnimation { id: fadeIn; target: art; property: "opacity"; from: 0; to: 1; duration: 260 }
        }

        // selo "pausado", carimbado no canto
        Rectangle {
            visible: cover.paused && cover.showStamp && cover.size >= 180
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: 12
            width: stamp.implicitWidth + 14
            height: stamp.implicitHeight + 8
            color: Theme.ink
            rotation: -3
            Text {
                id: stamp
                anchors.centerIn: parent
                text: "EM PAUSA"
                color: Theme.paper
                font.pixelSize: 11
                font.weight: Font.Black
                font.letterSpacing: 2
            }
        }
    }
}
