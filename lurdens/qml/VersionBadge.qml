import QtQuick 2.15
import QtQuick.Controls 2.15

// Selo de versão (ex.: "v1.1"). Preenchido de tinta quando há novidades
// ainda não vistas; vazado depois de abrir o histórico.
Item {
    id: vb
    property bool fresh: app.hasUnseenVersion
    signal clicked()

    readonly property string shortVersion: {
        var p = app.version.split(".")
        return "v" + p[0] + "." + p[1] + (p.length > 2 && p[2] !== "0" ? "." + p[2] : "")
    }

    implicitWidth: tag.width + 3
    implicitHeight: tag.height + 3

    Accessible.role: Accessible.Button
    Accessible.name: "Versão " + app.version + ". Ver novidades"

    // sombra deslocada, só no estado "novo"
    Rectangle {
        x: 3; y: 3
        width: tag.width; height: tag.height
        color: Theme.shadowInk
        visible: vb.fresh && !ma.pressed
    }

    Rectangle {
        id: tag
        x: ma.pressed ? 2 : 0
        y: x
        width: row.implicitWidth + 12
        height: 19
        color: vb.fresh || ma.containsMouse ? Theme.ink : "transparent"
        border.width: 1.5
        border.color: Theme.ink

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 4
            // marcador de "novo": um pontinho de papel dentro do selo
            Rectangle {
                visible: vb.fresh
                anchors.verticalCenter: parent.verticalCenter
                width: 5; height: 5; radius: 2.5
                color: Theme.paper
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: vb.shortVersion
                color: vb.fresh || ma.containsMouse ? Theme.paper : Theme.ink
                font.pixelSize: 10
                font.weight: Font.Black
                font.letterSpacing: 0.8
            }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        anchors.margins: -4
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) { vb.clicked() }
    }

    ToolTip.visible: ma.containsMouse
    ToolTip.delay: 400
    ToolTip.text: vb.fresh ? "Lurdens " + app.version + " — veja o que mudou" : "Lurdens " + app.version + " — novidades"
}
