import QtQuick

// A view inside a page that eases in/out when `on` flips.
Item {
    id: pane
    property bool on: false
    anchors.fill: parent
    opacity: on ? 1 : 0
    visible: opacity > 0.01
    enabled: on
    Behavior on opacity { NumberAnimation { duration: Theme.dur(220); easing.type: Easing.OutCubic } }
    property real sc: on ? 1 : 0.97
    Spring on sc { eps: 0.0005 }
    transform: Scale { origin.x: pane.width / 2; origin.y: pane.height / 2; xScale: pane.sc; yScale: pane.sc }
}
