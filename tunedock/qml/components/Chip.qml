import QtQuick

Item {
    id: c
    property string text
    property string icon
    property bool selected: false
    property bool filter: true      // filter chips show a check when selected
    signal clicked()
    implicitHeight: 34
    implicitWidth: r.implicitWidth + 24
    activeFocusOnTab: true
    Keys.onReturnPressed: c.clicked()
    Keys.onSpacePressed: c.clicked()
    readonly property color fg: selected ? Theme.fgSecondaryContainer : Theme.fgSurfaceVariant
    Rectangle {
        anchors.fill: parent; radius: Theme.rM
        color: c.selected ? Theme.secondaryContainer : "transparent"
        border.width: c.selected ? 0 : 1; border.color: Theme.outlineVariant
        Behavior on color { ColorAnimation { duration: Theme.dur(160) } }
        Rectangle { anchors.fill: parent; radius: parent.radius; color: c.fg
            opacity: ma.pressed ? 0.12 : (ma.containsMouse ? 0.08 : 0) }
        Row { id: r; anchors.centerIn: parent; spacing: 6
            Icon { path: c.selected && c.filter ? Icons.check : c.icon; visible: path.length > 0; size: 18; color: c.fg; anchors.verticalCenter: parent.verticalCenter }
            Text { text: c.text; color: c.fg; font: Theme.label; anchors.verticalCenter: parent.verticalCenter; renderType: Text.NativeRendering } }
        Rectangle { anchors.fill: parent; anchors.margins: -2; radius: parent.radius + 2; color: "transparent"; border.width: 2; border.color: Theme.primary; visible: c.activeFocus }
    }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: c.clicked() }
}
