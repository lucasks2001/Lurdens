import QtQuick 2.15

// Seletor de opções exclusivas (ex.: tema escuro / claro / sistema).
Row {
    id: seg
    property var options: []          // [{ value: "dark", label: "Escuro" }, ...]
    property string current: ""
    signal selected(string value)

    spacing: -Theme.strokeThin

    Repeater {
        model: seg.options
        delegate: Rectangle {
            readonly property bool isOn: modelData.value === seg.current
            width: Math.max(74, label.implicitWidth + 24)
            height: 32
            color: isOn ? Theme.ink : (hover.containsMouse ? Theme.paperRaised : Theme.paper)
            border.width: Theme.strokeThin
            border.color: Theme.ink
            Text {
                id: label
                anchors.centerIn: parent
                text: modelData.label
                color: parent.isOn ? Theme.paper : Theme.ink
                font.pixelSize: 12
                font.weight: Font.Bold
            }
            MouseArea {
                id: hover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: function(mouse) { seg.selected(modelData.value) }
            }
        }
    }
}
