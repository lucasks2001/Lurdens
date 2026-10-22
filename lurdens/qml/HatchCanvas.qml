import QtQuick 2.15

// Preenchimentos à mão das referências: hachura, hachura cruzada,
// pontilhado, trama e traço interrompido. Redesenha só quando o tamanho,
// a cor ou o padrão mudam — nunca a cada quadro.
Canvas {
    id: c
    property string pattern: "diagonal"   // diagonal | cross | triple | stipple | weave | dash
    property color color: Theme.ink
    property real spacing: 6
    property real lineWidth: 1.3
    property real jitter: 0.7
    property real density: 0.35           // pontilhado
    property bool edgeWeighted: true      // pontilhado mais denso nas bordas
    property int seed: 7

    renderStrategy: Canvas.Cooperative
    antialiasing: true

    onPatternChanged: requestPaint()
    onColorChanged: requestPaint()
    onSpacingChanged: requestPaint()
    onDensityChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        ctx.clearRect(0, 0, width, height)
        if (width <= 0 || height <= 0)
            return
        var state = c.seed * 7919 + 13
        function rnd() {
            state = (state * 16807) % 2147483647
            return (state - 1) / 2147483646
        }
        function j() { return (rnd() - 0.5) * 2 * c.jitter }
        var col = Theme.rgba(c.color)
        ctx.strokeStyle = col
        ctx.fillStyle = col
        ctx.lineWidth = c.lineWidth
        ctx.lineCap = "round"
        var w = width, h = height, s = Math.max(2, c.spacing), k

        function diag(dir) {
            ctx.beginPath()
            for (k = -h; k < w + h; k += s) {
                if (dir > 0) {
                    ctx.moveTo(k + j(), h + j())
                    ctx.lineTo(k + h + j(), j())
                } else {
                    ctx.moveTo(k + j(), j())
                    ctx.lineTo(k + h + j(), h + j())
                }
            }
            ctx.stroke()
        }

        if (pattern === "diagonal") {
            diag(1)
        } else if (pattern === "cross") {
            diag(1); diag(-1)
        } else if (pattern === "triple") {
            diag(1); diag(-1)
            ctx.beginPath()
            for (k = s / 2; k < h; k += s) { ctx.moveTo(j(), k + j()); ctx.lineTo(w + j(), k + j()) }
            ctx.stroke()
        } else if (pattern === "dash") {
            ctx.beginPath()
            for (k = s / 2; k < h; k += s) {
                var x = rnd() * 10
                while (x < w) {
                    var len = 6 + rnd() * 18
                    ctx.moveTo(x, k + j() * 0.4)
                    ctx.lineTo(Math.min(w, x + len), k + j() * 0.4)
                    x += len + 3 + rnd() * 9
                }
            }
            ctx.stroke()
        } else if (pattern === "weave") {
            var cell = s * 3
            ctx.beginPath()
            for (var gy = 0; gy < h + cell; gy += cell) {
                for (var gx = 0; gx < w + cell; gx += cell) {
                    var horiz = ((gx + gy) / cell) % 2 === 0
                    for (var t = 1; t < 3; t++) {
                        if (horiz) { ctx.moveTo(gx + 1, gy + t * s + j() * 0.3); ctx.lineTo(gx + cell - 1, gy + t * s + j() * 0.3) }
                        else { ctx.moveTo(gx + t * s + j() * 0.3, gy + 1); ctx.lineTo(gx + t * s + j() * 0.3, gy + cell - 1) }
                    }
                }
            }
            ctx.stroke()
        } else if (pattern === "stipple") {
            var n = Math.round(w * h * c.density / (s * s) * 4)
            ctx.beginPath()
            for (k = 0; k < n; k++) {
                var px = rnd() * w, py = rnd() * h
                if (c.edgeWeighted) {
                    var dx = Math.abs(px - w / 2) / (w / 2), dy = Math.abs(py - h / 2) / (h / 2)
                    var d = Math.max(dx, dy)
                    if (rnd() > Math.pow(d, 1.7) + 0.06)
                        continue
                }
                var r = 0.45 + rnd() * c.lineWidth * 0.6
                ctx.moveTo(px + r, py)
                ctx.arc(px, py, r, 0, Math.PI * 2)
            }
            ctx.fill()
        }
    }
}
