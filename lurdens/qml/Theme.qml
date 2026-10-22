pragma Singleton
import QtQuick 2.15

// Identidade "nanquim": papel e tinta, sem cor de destaque.
// No tema escuro a lógica se inverte (traço claro sobre papel preto).
QtObject {
    readonly property bool dark: app.dark

    readonly property color paper:       dark ? "#141311" : "#F2EDE2"
    readonly property color paperRaised: dark ? "#1D1B18" : "#FBF8F1"
    readonly property color paperSunken: dark ? "#0D0C0B" : "#E7E0D2"
    readonly property color ink:         dark ? "#ECE6D8" : "#161412"
    readonly property color inkSoft:     dark ? "#BDB6A7" : "#3D3934"
    readonly property color muted:       dark ? "#80796D" : "#7B746A"
    readonly property color faint:       dark ? "#3A3732" : "#CFC7B8"
    readonly property color shadowInk:   dark ? "#8C8577" : "#161412"

    readonly property int stroke: 3          // contorno grosso, como nas referências
    readonly property int strokeThin: 2
    readonly property int margin: 22
    readonly property int shadowOffset: 9

    readonly property string fontFamily: app.fontFamily !== "" ? app.fontFamily : Qt.application.font.family

    function rgba(c, a) {
        return "rgba(" + Math.round(c.r * 255) + "," + Math.round(c.g * 255) + ","
               + Math.round(c.b * 255) + "," + (a === undefined ? c.a : a) + ")"
    }
}
