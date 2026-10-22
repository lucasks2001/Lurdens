import QtQuick 2.15

// Linha de configuração: título, descrição opcional e um controle à direita.
Item {
    id: row
    property string title: ""
    property string description: ""
    default property alias control: slot.data

    implicitHeight: Math.max(texts.implicitHeight, slot.childrenRect.height) + 18
    opacity: enabled ? 1 : 0.45

    Column {
        id: texts
        anchors.left: parent.left
        anchors.right: slot.left
        anchors.rightMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 3
        Text {
            width: parent.width
            text: row.title
            color: Theme.ink
            font.pixelSize: 14
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
        }
        Text {
            width: parent.width
            visible: row.description !== ""
            text: row.description
            color: Theme.muted
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }
    }

    Item {
        id: slot
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: childrenRect.width
        height: childrenRect.height
    }
}
