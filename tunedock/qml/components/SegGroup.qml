import QtQuick

// Connected button group. model: ["Opus", ...] or [{label, enabled}]. The selected segment becomes a full pill.
Item {
    id: g
    property var model: []
    property int currentIndex: 0
    property int size: 1
    signal picked(int index)
    readonly property real h: [32, 40, 56][size]
    implicitHeight: h
    implicitWidth: row.implicitWidth
    Row {
        id: row
        spacing: 2
        Repeater {
            model: g.model
            delegate: Item {
                id: seg
                readonly property string label: typeof modelData === "string" ? modelData : modelData.label
                readonly property bool avail: typeof modelData === "string" ? true : modelData.enabled !== false
                readonly property bool sel: index === g.currentIndex
                readonly property bool first: index === 0
                readonly property bool last: index === g.model.length - 1
                width: lbl.implicitWidth + (g.size >= 1 ? 40 : 28)
                height: g.h
                opacity: avail ? 1 : 0.38
                activeFocusOnTab: true
                Keys.onReturnPressed: if (avail) g.picked(index)
                Keys.onSpacePressed: if (avail) g.picked(index)
                readonly property real full: height / 2
                readonly property real inner: Theme.rS
                property real tl: sel || first ? full : inner
                property real tr: sel || last ? full : inner
                property real sc: ma.pressed ? 0.96 : 1
                Spring on tl { eps: 0.3 }
                Spring on tr { eps: 0.3 }
                Spring on sc { eps: 0.001 }
                Rectangle {
                    anchors.fill: parent; scale: seg.sc
                    topLeftRadius: Math.max(0, seg.tl); bottomLeftRadius: Math.max(0, seg.tl)
                    topRightRadius: Math.max(0, seg.tr); bottomRightRadius: Math.max(0, seg.tr)
                    color: seg.sel ? Theme.primary : Theme.surfaceContainerHighest
                    Behavior on color { ColorAnimation { duration: Theme.dur(180) } }
                    Rectangle { anchors.fill: parent; radius: Theme.rS; color: seg.sel ? Theme.fgPrimary : Theme.fgSurface
                        topLeftRadius: parent.topLeftRadius; bottomLeftRadius: parent.bottomLeftRadius
                        topRightRadius: parent.topRightRadius; bottomRightRadius: parent.bottomRightRadius
                        opacity: ma.pressed ? 0.12 : (ma.containsMouse && seg.avail ? 0.08 : 0) }
                    Text { id: lbl; anchors.centerIn: parent; text: seg.label; font: Theme.label; renderType: Text.NativeRendering
                        color: seg.sel ? Theme.fgPrimary : Theme.fgSurfaceVariant }
                    Rectangle { anchors.fill: parent; anchors.margins: -2; color: "transparent"; border.width: 2; border.color: Theme.primary
                        radius: height / 2; visible: seg.activeFocus }
                }
                MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; enabled: seg.avail
                    cursorShape: Qt.PointingHandCursor; onClicked: g.picked(index) }
            }
        }
    }
}
