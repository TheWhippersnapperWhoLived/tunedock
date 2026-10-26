import QtQuick
import QtQuick.Window
import Td 1.0

// Small floating card shown for quick-add (right-click menu) jobs. Never takes focus.
Window {
    id: w
    readonly property var t: Backend.toast
    property bool shown: t.visible
    transientParent: null          // a standalone window: never owned by (and hidden with) the main window
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    width: 400; height: 124
    x: Screen.virtualX + Screen.desktopAvailableWidth - width - 8
    y: Screen.virtualY + Screen.desktopAvailableHeight - height - 8
    visible: false
    onShownChanged: {
        if (shown) { hideTimer.stop(); visible = true; card.slide = 0 }
        else { card.slide = 60; hideTimer.restart() }
    }
    Timer { id: hideTimer; interval: 420; onTriggered: if (!w.shown) w.visible = false }

    Rectangle {
        id: card
        property real slide: 60
        Spring on slide { eps: 0.3 }
        x: 8; y: 8 + slide; width: parent.width - 16; height: parent.height - 16
        opacity: 1 - Math.min(1, slide / 60)
        radius: Theme.rXL
        color: Theme.inverseSurface
        Row {
            x: 18; y: 16; spacing: 14
            Blob { size: 46; lobes: w.t.state === "done" ? 12 : (w.t.state === "error" ? 5 : 9)
                amp: w.t.state === "working" ? 0.12 : 0.07
                spin: w.t.state === "working"
                color: w.t.state === "error" ? Theme.errorContainer : (w.t.state === "warn" ? Theme.tertiaryContainer : Theme.primaryContainer)
                Icon { anchors.centerIn: parent; size: 22
                    path: w.t.state === "done" ? Icons.check : (w.t.state === "working" ? Icons.music : Icons.warning)
                    color: w.t.state === "error" ? Theme.fgErrorContainer : Theme.fgPrimaryContainer }
            }
            Column { width: card.width - 18 * 2 - 46 - 14; spacing: 3
                Text { width: parent.width; text: w.t.title; elide: Text.ElideRight; font: Theme.titleS; color: Theme.inverseOnSurface; renderType: Text.NativeRendering }
                Text { width: parent.width; text: w.t.sub; elide: Text.ElideMiddle; font: Theme.bodyS; color: Theme.inverseOnSurface; opacity: 0.8; renderType: Text.NativeRendering }
            }
        }
        WavyProgress { x: 18; y: parent.height - 34; width: parent.width - 36
            visible: w.t.state === "working"; value: w.t.value
            color: Theme.inversePrimary; trackColor: Qt.rgba(1, 1, 1, 0.15) }
        Row { x: 18; y: parent.height - 40; spacing: 8; visible: w.t.state !== "working"
            XButton { text: "Open folder"; size: 0; variant: "text"; customFg: Theme.inversePrimary; visible: w.t.dest.length > 0; onClicked: { Backend.openPath(w.t.dest); Backend.dismissToast() } }
            XButton { text: "Dismiss"; size: 0; variant: "text"; customFg: Theme.inversePrimary; onClicked: Backend.dismissToast() }
        }
        XButton { visible: w.t.state === "working"; text: "Cancel"; size: 0; variant: "text"; customFg: Theme.inversePrimary; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
            onClicked: Backend.cancel() }
    }
}
