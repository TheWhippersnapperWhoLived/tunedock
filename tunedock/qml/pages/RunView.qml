import QtQuick
import Td 1.0
import "../components"

Pane {
    id: v
    readonly property var p: Backend.progress
    readonly property var stateIcon: ({ converted: Icons.sync, copied: Icons.copy, skipped: Icons.chevron, failed: Icons.warning })
    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 520)
        spacing: 22
        Item { width: parent.width; height: 170
            Blob { id: lb; anchors.centerIn: parent; size: 150; color: Theme.primaryContainer; amp: 0.12; lobes: 9
                property int step: 0
                Timer { interval: 1300; repeat: true; running: v.on; onTriggered: { lb.step = (lb.step + 1) % 4; lb.lobes = [9, 6, 8, 5][lb.step]; lb.amp = [0.1, 0.16, 0.12, 0.18][lb.step] } }
                Icon { anchors.centerIn: parent; path: Icons.music; size: 52; color: Theme.fgPrimaryContainer } }
        }
        Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; font: Theme.headline
            text: "Adding " + (p.done || 0) + " of " + (p.total || 0) }
        WavyProgress { width: parent.width; value: p.total > 0 ? p.done / p.total : -1; height: 22; thickness: 6; amp: 4 }
        Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; color: Theme.fgSurfaceVariant; elide: Text.ElideMiddle; maximumLineCount: 1
            text: p.name ? p.name : "Getting started\u2026" }
        Column { width: parent.width; spacing: 4
            Repeater { model: p.recent ? p.recent.slice(0, 4) : []
                delegate: Item { width: parent.width; height: 28; opacity: 1 - index * 0.22
                    Icon { x: parent.width / 2 - 150; anchors.verticalCenter: parent.verticalCenter; size: 18
                        path: v.stateIcon[modelData.state] || Icons.check
                        color: modelData.state === "failed" ? Theme.error : Theme.fgSurfaceVariant }
                    Txt { x: parent.width / 2 - 124; width: 300; anchors.verticalCenter: parent.verticalCenter; text: modelData.name
                        elide: Text.ElideMiddle; maximumLineCount: 1; font: Theme.bodyS; color: Theme.fgSurfaceVariant } } } }
        XButton { anchors.horizontalCenter: parent.horizontalCenter; text: "Cancel"; variant: "outlined"; onClicked: Backend.cancel() }
    }
}
