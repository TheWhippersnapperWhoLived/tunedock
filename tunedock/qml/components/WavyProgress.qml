import QtQuick

// M3 Expressive wavy linear progress. value 0..1, or -1 for indeterminate.
Item {
    id: root
    property real value: -1
    property color color: Theme.primary
    property color trackColor: Theme.secondaryContainer
    property real amp: 3.5
    property real wavelength: 30
    property real thickness: 5
    property real phase: 0
    property real shown: value
    implicitHeight: 20; implicitWidth: 240
    Behavior on shown { NumberAnimation { duration: Theme.dur(300); easing.type: Easing.OutCubic } }
    NumberAnimation on phase { from: 0; to: Math.PI * 2; duration: 1100; loops: Animation.Infinite; running: root.visible && !Theme.reduce }
    onPhaseChanged: cv.requestPaint()
    onShownChanged: cv.requestPaint()
    onWidthChanged: cv.requestPaint()
    onColorChanged: cv.requestPaint()
    onTrackColorChanged: cv.requestPaint()

    Canvas {
        id: cv
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            var w = width, h = height, th = root.thickness, mid = h / 2
            ctx.lineCap = "round"; ctx.lineWidth = th
            var a = 0, b = 0
            if (root.shown < 0) {
                var p = (root.phase / (Math.PI * 2))
                b = p * (w * 1.4); a = b - w * 0.35
                a = Math.max(0, a); b = Math.min(w, b)
            } else { a = 0; b = Math.max(0, Math.min(1, root.shown)) * w }
            var pad = th / 2
            // track (straight) after the active part
            ctx.strokeStyle = root.trackColor
            ctx.beginPath()
            if (root.shown < 0) {
                if (a > pad + 2) { ctx.moveTo(pad, mid); ctx.lineTo(a - 8, mid) }
                if (b < w - pad - 2) { ctx.moveTo(b + 8, mid); ctx.lineTo(w - pad, mid) }
            } else if (b + 8 < w - pad) { ctx.moveTo(b + 8, mid); ctx.lineTo(w - pad, mid) }
            ctx.stroke()
            // active (wavy)
            if (b - a > 1) {
                ctx.strokeStyle = root.color
                ctx.beginPath()
                var k = Math.PI * 2 / root.wavelength
                for (var x = a + pad; x <= b - pad + 0.5; x += 1.5) {
                    var edge = Math.min(1, Math.min(x - a, b - x) / 14)   // calm the wave at the ends
                    var y = mid + Math.sin(x * k - root.phase) * root.amp * edge
                    if (x === a + pad) ctx.moveTo(x, y); else ctx.lineTo(x, y)
                }
                ctx.stroke()
            }
        }
    }
}
