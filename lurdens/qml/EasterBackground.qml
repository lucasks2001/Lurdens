import QtQuick 2.15

// Easter egg: fundo hachurado derivado de "Bring icon.png", ativo enquanto
// "Ludens" (Bring Me The Horizon) toca. Pausado = rastro discreto.
// A imagem só é carregada na primeira ativação e fica em cache depois;
// a transição é só de opacidade (barata, sem animação contínua).
Item {
    id: bg
    readonly property string mode: session.easterMode
    property bool everActive: false

    clip: true
    opacity: mode === "playing" ? (Theme.dark ? 0.26 : 0.2)
           : mode === "paused" ? 0.07 : 0
    visible: opacity > 0.001
    Behavior on opacity { NumberAnimation { duration: 1200; easing.type: Easing.InOutQuad } }

    onModeChanged: if (mode !== "off") everActive = true
    Component.onCompleted: if (mode !== "off") everActive = true

    Image {
        id: art
        anchors.centerIn: parent
        // a estrela é vertical: ocupa a altura e transborda a largura no formato retrato
        width: Math.max(parent.width, parent.height) * 1.04
        height: width
        source: bg.everActive && session.easterAvailable
                ? resourcesUrl + "easter/ludens-hatch-" + (Theme.dark ? "light" : "dark") + ".png" : ""
        sourceSize.width: 1200
        sourceSize.height: 1200
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        cache: true
        smooth: true
        mipmap: true
        objectName: "ludensArt"
    }
}
