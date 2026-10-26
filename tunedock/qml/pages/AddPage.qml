import QtQuick
import Td 1.0
import "../components"

Item {
    id: page
    property bool active: false
    signal requestPage(int index)
    opacity: active ? 1 : 0
    visible: opacity > 0.01
    Behavior on opacity { NumberAnimation { duration: Theme.dur(240); easing.type: Easing.OutCubic } }
    property real shift: active ? 0 : 28
    Spring on shift { eps: 0.3 }
    transform: Translate { y: page.shift }

    // dropping more music works on every screen, not just the first one
    DropArea {
        anchors.fill: parent
        enabled: Backend.stage !== "idle"
        onDropped: (d) => { if (d.hasUrls) Backend.addPaths(d.urls.map(String)) }
    }

    IdleView { on: Backend.stage === "idle"; onRequestPage: (i) => page.requestPage(i) }
    PickView { on: Backend.stage === "pick" || Backend.stage === "scanning"; onRequestPage: (i) => page.requestPage(i) }
    RunView { on: Backend.stage === "running" }
    DoneView { on: Backend.stage === "done" }
}
