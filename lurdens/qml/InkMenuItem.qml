import QtQuick 2.15
import QtQuick.Controls 2.15

MenuItem {
    id: mi
    property string iconName: ""
    property string shortcutText: ""
    property bool marked: false          // marca de seleção controlada por binding

    implicitWidth: 250
    implicitHeight: visible ? 36 : 0
    leftPadding: 12
    rightPadding: 12

    indicator: Item {}
    arrow: Item {}

    contentItem: Item {
        implicitHeight: 36
        InkGlyph {
            id: glyph
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            width: 17; height: 17
            name: mi.marked ? "check" : mi.iconName
            visible: name !== ""
            color: mi.highlighted ? Theme.paper : (mi.enabled ? Theme.ink : Theme.muted)
        }
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 28
            anchors.right: sc.left
            anchors.verticalCenter: parent.verticalCenter
            text: mi.text
            elide: Text.ElideRight
            color: mi.highlighted ? Theme.paper : (mi.enabled ? Theme.ink : Theme.muted)
            font.pixelSize: 13
            font.weight: Font.DemiBold
        }
        Text {
            id: sc
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: mi.shortcutText
            color: mi.highlighted ? Theme.paper : Theme.muted
            font.pixelSize: 11
        }
    }

    background: Rectangle {
        implicitWidth: 250
        implicitHeight: 36
        color: mi.highlighted ? Theme.ink : "transparent"
    }
}
