import QtQuick 2.15
import QtQuick.Controls 2.15

// Campo que grava um atalho: clique, pressione a combinação.
// Esc cancela, Backspace/Delete remove o atalho. Exige Ctrl, Alt ou Meta
// para não capturar letras soltas do teclado inteiro.
Rectangle {
    id: f
    property string actionId: ""
    property string keyText: ""
    property bool conflict: false
    property bool recording: false
    property string hint: ""

    implicitWidth: 150
    implicitHeight: 32
    color: recording ? Theme.ink : (ma.containsMouse ? Theme.paperRaised : Theme.paper)
    border.width: Theme.strokeThin
    border.color: conflict ? Theme.muted : Theme.ink
    opacity: enabled ? 1 : 0.4

    Accessible.role: Accessible.Button
    Accessible.name: "Atalho: " + (keyText || "nenhum")

    function stop() { recording = false; hint = ""; focus = false }

    Text {
        anchors.centerIn: parent
        width: parent.width - 12
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: f.recording ? (f.hint || "pressione…") : (f.keyText || (f.conflict ? "em uso" : "—"))
        color: f.recording ? Theme.paper : (f.keyText ? Theme.ink : Theme.muted)
        font.pixelSize: 12
        font.weight: Font.Bold
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) {
            if (f.recording) { f.stop(); return }
            f.recording = true
            f.forceActiveFocus()
        }
    }

    onActiveFocusChanged: if (!activeFocus) stop()

    // impede que os atalhos da janela (Espaço, setas…) disparem enquanto grava
    Keys.onShortcutOverride: function(event) { event.accepted = f.recording }
    Keys.onPressed: function(event) {
        if (!f.recording) return
        event.accepted = true
        var k = event.key
        if (k === Qt.Key_Escape) { f.stop(); return }
        if (k === Qt.Key_Backspace || k === Qt.Key_Delete) {
            session.setShortcut(f.actionId, 0); f.stop(); return
        }
        if (k === Qt.Key_Shift || k === Qt.Key_Control || k === Qt.Key_Alt || k === Qt.Key_Meta
            || k === Qt.Key_AltGr || k === Qt.Key_Super_L || k === Qt.Key_Super_R || k === Qt.Key_unknown)
            return
        var mods = event.modifiers & (Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
        if (!(mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
            f.hint = "use Ctrl, Alt ou Meta"
            return
        }
        session.setShortcut(f.actionId, k | mods)
        f.stop()
    }

    ToolTip.visible: ma.containsMouse && !f.recording
    ToolTip.delay: 600
    ToolTip.text: f.conflict ? "A combinação padrão já é usada por outro programa. Clique para escolher outra."
                             : "Clique e pressione a nova combinação (Esc cancela, Backspace remove)"
}
