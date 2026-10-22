import QtQuick 2.15

// Cabeçalho das páginas sobrepostas (voltar · título · ação opcional à direita).
Rectangle {
    id: h
    property string title: ""
    default property alias trailing: right.data
    signal back()

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
        onClicked: h.back()
    }
    Text {
        anchors.centerIn: parent
        text: h.title
        color: Theme.ink
        font.pixelSize: 13
        font.weight: Font.Black
        font.letterSpacing: 2.4
    }
    Row {
        id: right
        anchors.right: parent.right
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
    }
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.strokeThin; color: Theme.ink }
}
