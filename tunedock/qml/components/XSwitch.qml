import QtQuick

Item {
    id: s
    property bool checked: false
    signal toggled(bool value)
    implicitWidth: 56; implicitHeight: 34
    opacity: enabled ? 1 : 0.38
    activeFocusOnTab: true
    Keys.onSpacePressed: s.toggled(!s.checked)
    Keys.onReturnPressed: s.toggled(!s.checked)
    property real hsz: ma.pressed ? 28 : (checked ? 24 : 16)
    Spring on hsz { eps: 0.2 }
    Rectangle {
        id: track
        anchors.fill: parent; radius: height / 2
        color: s.checked ? Theme.primary : Theme.surfaceContainerHighest
        border.width: s.checked ? 0 : 2; border.color: Theme.outline
        Behavior on color { ColorAnimation { duration: Theme.dur(180) } }
        Rectangle {
            id: handle
            width: s.hsz; height: s.hsz; radius: width / 2
            anchors.verticalCenter: parent.verticalCenter
            readonly property real m: (parent.height - width) / 2
            x: s.checked ? parent.width - width - m : m
            color: s.checked ? Theme.fgPrimary : Theme.outline
            Spring on x { eps: 0.25 }
            Behavior on color { ColorAnimation { duration: Theme.dur(180) } }
            Icon { anchors.centerIn: parent; path: Icons.check; size: 16; color: Theme.primary; opacity: s.checked ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.dur(150) } } }
        }
        Rectangle { anchors.fill: parent; anchors.margins: -3; radius: height / 2; color: "transparent"; border.width: 2; border.color: Theme.primary; visible: s.activeFocus }
    }
    MouseArea { id: ma; anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: s.toggled(!s.checked) }
}
