import QtQuick 2.15
import QtQuick.Shapes 1.15

// Ícones vetoriais desenhados em uma grade de 24×24, coloridos pelo tema.
Item {
    id: g
    property string name: "play"
    property color color: Theme.ink
    property real strokeWidth: 2.2

    implicitWidth: 24
    implicitHeight: 24

    readonly property var glyphs: ({
        "none":     { f: "M0 0", s: "M0 0" },
        "play":     { f: "M8 4.8 L19.5 12 L8 19.2 Z", s: "M0 0" },
        "pause":    { f: "M6.5 5 H10.5 V19 H6.5 Z M13.5 5 H17.5 V19 H13.5 Z", s: "M0 0" },
        "next":     { f: "M4.5 5 L14.5 12 L4.5 19 Z M16 5 H19.5 V19 H16 Z", s: "M0 0" },
        "previous": { f: "M19.5 5 L9.5 12 L19.5 19 Z M4.5 5 H8 V19 H4.5 Z", s: "M0 0" },
        "shuffle":  { f: "M0 0", s: "M3 7 H6.5 L16 17 H20.5 M3 17 H6.5 L9.3 14.2 M13.4 9.9 L16 7 H20.5 M17.5 4 L20.5 7 L17.5 10 M17.5 14 L20.5 17 L17.5 20" },
        "repeat":   { f: "M0 0", s: "M4 12.5 V9.5 Q4 7 6.5 7 H19 M16 4 L19 7 L16 10 M20 11.5 V14.5 Q20 17 17.5 17 H5 M8 14 L5 17 L8 20" },
        "volume":   { f: "M3.5 9.2 H7.2 L12 5.5 V18.5 L7.2 14.8 H3.5 Z", s: "M15.4 9.2 Q16.8 12 15.4 14.8 M18 6.6 Q21.4 12 18 17.4" },
        "volumeLow":{ f: "M3.5 9.2 H7.2 L12 5.5 V18.5 L7.2 14.8 H3.5 Z", s: "M15.4 9.2 Q16.8 12 15.4 14.8" },
        "mute":     { f: "M3.5 9.2 H7.2 L12 5.5 V18.5 L7.2 14.8 H3.5 Z", s: "M15.5 9.5 L20.5 14.5 M20.5 9.5 L15.5 14.5" },
        "settings": { f: "M7.5 5 H11 V9 H7.5 Z M13.5 10 H17 V14 H13.5 Z M6 15 H9.5 V19 H6 Z", s: "M3.5 7 H20.5 M3.5 12 H20.5 M3.5 17 H20.5" },
        "menu":     { f: "M10.3 4 H13.7 V7.4 H10.3 Z M10.3 10.3 H13.7 V13.7 H10.3 Z M10.3 16.6 H13.7 V20 H10.3 Z", s: "M0 0" },
        "back":     { f: "M0 0", s: "M14.5 5 L7.5 12 L14.5 19" },
        "close":    { f: "M0 0", s: "M6 6 L18 18 M18 6 L6 18" },
        "open":     { f: "M0 0", s: "M13.5 4 H20 V10.5 M20 4 L11 13 M17.5 14 V20 H4 V6.5 H10" },
        "fullscreen": { f: "M0 0", s: "M4 9 V4 H9 M15 4 H20 V9 M20 15 V20 H15 M9 20 H4 V15" },
        "compact":  { f: "M0 0", s: "M3.5 8 H20.5 V16 H3.5 Z M7 12 H13" },
        "pin":      { f: "M0 0", s: "M8 4 H16 M9.5 4 V10 L6.5 14 H17.5 L14.5 10 V4 M12 14 V20.5" },
        "tray":     { f: "M0 0", s: "M4 14 V19 H20 V14 M12 4 V14 M8 10 L12 14 L16 10" },
        "info":     { f: "M10.6 6 H13.4 V8.8 H10.6 Z", s: "M12 11 V18.5 M9.5 18.5 H14.5 M9.5 11 H12" },
        "power":    { f: "M0 0", s: "M12 3.5 V11 M7.2 6.5 Q4 9 4.5 13 Q5.5 20 12 20 Q18.5 20 19.5 13 Q20 9 16.8 6.5" },
        "check":    { f: "M0 0", s: "M5 12.5 L10 17.5 L19 7" },
        "moon":     { f: "M14.5 3.2 A8.8 8.8 0 1 0 20.8 15.6 A7.2 7.2 0 0 1 14.5 3.2 Z", s: "M0 0" },
        "history":  { f: "M0 0", s: "M4.6 12 A7.6 7.6 0 1 0 6.8 6.6 M3.8 3.6 V7.4 H7.6 M12 7.8 V12 L15 14.2" },
        "trash":    { f: "M0 0", s: "M4.5 6.5 H19.5 M9.5 6.5 V4 H14.5 V6.5 M6.5 6.5 L7.5 20 H16.5 L17.5 6.5 M10 10 V16.5 M14 10 V16.5" },
        "keyboard": { f: "M6 9 H8 V11 H6 Z M10 9 H12 V11 H10 Z M14 9 H16 V11 H14 Z M8 13 H16 V15 H8 Z", s: "M3 6.5 H21 V17.5 H3 Z" }
    })
    readonly property var glyph: glyphs[name] !== undefined ? glyphs[name] : glyphs["none"]

    layer.enabled: true
    layer.samples: 4
    layer.smooth: true

    Shape {
        width: 24
        height: 24
        transform: Scale { xScale: g.width / 24; yScale: g.height / 24 }

        ShapePath {
            strokeColor: "transparent"
            fillColor: g.color
            PathSvg { path: g.glyph.f }
        }
        ShapePath {
            strokeColor: g.color
            strokeWidth: g.strokeWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: g.glyph.s }
        }
    }
}
