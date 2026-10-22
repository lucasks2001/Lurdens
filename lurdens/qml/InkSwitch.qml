import QtQuick 2.15

// Interruptor quadrado. Não muda sozinho: emite toggled() e o dono
// atualiza a configuração, que volta pelo binding de "checked".
Item {
    id: sw
    property bool checked: false
    signal toggled(bool value)

    implicitWidth: 46
    implicitHeight: 24
    opacity: enabled ? 1 : 0.4

    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: checked

    Rectangle {
        anchors.fill: parent
        color: sw.checked ? Theme.ink : Theme.paperRaised
        border.width: Theme.strokeThin
        border.color: Theme.ink
    }
    Rectangle {
        width: 14
        height: 14
        anchors.verticalCenter: parent.verticalCenter
        x: sw.checked ? parent.width - width - 5 : 5
        color: sw.checked ? Theme.paper : Theme.ink
        Behavior on x { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
    }
    MouseArea {
        anchors.fill: parent
        anchors.margins: -4
        enabled: sw.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) { sw.toggled(!sw.checked) }
    }
}
