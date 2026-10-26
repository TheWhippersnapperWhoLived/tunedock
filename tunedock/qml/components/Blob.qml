import QtQuick

// The signature shape: a soft, lobed "cookie" that morphs between shapes with a springy overshoot.
Item {
    id: root
    property real size: 120
    property int lobes: 9
    property real amp: 0.08
    property color color: Theme.primaryContainer
    property bool spin: true
    property real rot: 0
    property real n0: lobes
    property real a0: amp
    property real n1: lobes
    property real a1: amp
    property real t: 1
    width: size; height: size

    onLobesChanged: retarget()
    onAmpChanged: retarget()
    function retarget() {
        n0 = n1; a0 = a1 * t + a0 * (1 - t)
        n1 = lobes; a1 = amp; t = 0
        morph.restart()
    }
    NumberAnimation { id: morph; target: root; property: "t"; from: 0; to: 1
        duration: Theme.dur(650); easing.type: Easing.OutBack; easing.overshoot: 2.2 }
    NumberAnimation on rot { from: 0; to: Math.PI * 2; duration: 24000; loops: Animation.Infinite
        running: root.spin && !Theme.reduce && root.visible }

    onTChanged: cv.requestPaint()
    onRotChanged: cv.requestPaint()
    onColorChanged: cv.requestPaint()
    onSizeChanged: cv.requestPaint()

    Canvas {
        id: cv
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var R = width / 2 / 1.22, cx = width / 2, cy = height / 2
            ctx.beginPath()
            var N = 160
            for (var i = 0; i <= N; i++) {
                var th = i / N * Math.PI * 2
                var r = R * (1 + (1 - root.t) * root.a0 * Math.cos(root.n0 * th + root.rot * root.n0 / Math.max(1, root.n0))
                               + root.t * root.a1 * Math.cos(root.n1 * th + root.rot))
                var x = cx + r * Math.cos(th), y = cy + r * Math.sin(th)
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
            }
            ctx.closePath()
            ctx.fillStyle = root.color
            ctx.fill()
        }
    }
}
