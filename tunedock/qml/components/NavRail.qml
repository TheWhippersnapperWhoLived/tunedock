import QtQuick

Rectangle {
    id: rail
    property int current: 0
    property var items: []
    signal picked(int index)
    width: 96
    color: Theme.surface
    Behavior on color { ColorAnimation { duration: Theme.dur(380) } }
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 24
        spacing: 6
        Blob { size: 52; lobes: 9; amp: 0.09; color: Theme.tertiaryContainer; anchors.horizontalCenter: parent.horizontalCenter
            Icon { anchors.centerIn: parent; path: Icons.music; size: 22; color: Theme.fgTertiaryContainer } }
        Item { width: 1; height: 10 }
        Repeater {
            model: rail.items
            delegate: Item {
                id: it
                width: 88; height: 70
                readonly property bool sel: index === rail.current
                activeFocusOnTab: true
                Keys.onReturnPressed: rail.picked(index)
                Keys.onSpacePressed: rail.picked(index)
                Rectangle { id: pill
                    anchors.horizontalCenter: parent.horizontalCenter; y: 4
                    height: 34; radius: 17
                    property real w: it.sel ? 60 : 36
                    Spring on w { eps: 0.3 }
                    width: Math.max(0, w)
                    color: it.sel ? Theme.secondaryContainer : (ma.containsMouse ? Theme.surfaceContainerHigh : "transparent")
                    Behavior on color { ColorAnimation { duration: Theme.dur(160) } }
                    Icon { anchors.centerIn: parent; path: modelData.icon; size: 22; color: it.sel ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant }
                    Rectangle { anchors.fill: parent; anchors.margins: -2; radius: height / 2; color: "transparent"; border.width: 2; border.color: Theme.primary; visible: it.activeFocus }
                }
                Text { anchors.horizontalCenter: parent.horizontalCenter; y: 44; text: modelData.label
                    font: Theme.labelS; color: it.sel ? Theme.fgSurface : Theme.fgSurfaceVariant; renderType: Text.NativeRendering }
                MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: rail.picked(index) }
            }
        }
    }
}
