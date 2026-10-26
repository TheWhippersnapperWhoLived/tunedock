import QtQuick
import QtQuick.Controls.Basic as C

Item {
    id: page
    property string title
    property string subtitle
    property bool active: false
    default property alias content: col.data
    opacity: active ? 1 : 0
    visible: opacity > 0.01
    Behavior on opacity { NumberAnimation { duration: Theme.dur(240); easing.type: Easing.OutCubic } }
    property real shift: active ? 0 : 28
    Spring on shift { eps: 0.3 }
    transform: Translate { y: page.shift }

    Flickable {
        id: fl
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.height + 120
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        C.ScrollBar.vertical: C.ScrollBar { policy: C.ScrollBar.AsNeeded }
        Column {
            id: col
            width: Math.min(fl.width - 64, 780)
            x: Math.max(32, (fl.width - width) / 2)
            y: 30
            spacing: 18
            Column {
                width: parent.width; spacing: 6
                Text { text: page.title; font: Theme.headline; color: Theme.fgSurface; renderType: Text.NativeRendering }
                Txt { width: parent.width; visible: page.subtitle.length > 0; text: page.subtitle; color: Theme.fgSurfaceVariant }
            }
        }
    }
}
