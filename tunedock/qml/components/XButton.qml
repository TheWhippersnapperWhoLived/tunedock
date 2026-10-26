import QtQuick

// Expressive button: pill by default, morphs to a rounded square when pressed (and when a toggle is on).
Item {
    id: b
    property string text: ""
    property string icon: ""
    property string variant: "filled"     // filled | tonal | outlined | text | error
    property int size: 1                  // 0 xs, 1 small, 2 medium, 3 large
    property bool toggle: false
    property bool checked: false
    property color customFg: "transparent"   // override the text/icon colour (used on dark banners)
    property bool square: false           // start as a rounded square
    property bool connectedLeft: false
    property bool connectedRight: false
    signal clicked()
    readonly property bool pressed: ma.pressed
    readonly property real h: [32, 40, 56, 96][size]
    readonly property real pad: [14, 20, 28, 48][size]
    readonly property real iconSize: [18, 20, 24, 36][size]
    implicitHeight: h
    implicitWidth: row.implicitWidth + pad * 2
    opacity: enabled ? 1 : 0.38
    activeFocusOnTab: true
    Keys.onReturnPressed: b.clicked()
    Keys.onSpacePressed: b.clicked()

    readonly property bool on: toggle && checked
    readonly property color bgc: {
        if (toggle) return checked ? Theme.primary : Theme.surfaceContainerHighest
        switch (variant) {
        case "filled": return Theme.primary
        case "tonal": return Theme.secondaryContainer
        case "error": return Theme.errorContainer
        default: return "transparent"
        }
    }
    readonly property color fgc: {
        if (customFg.a > 0) return customFg
        if (toggle) return checked ? Theme.fgPrimary : Theme.fgSurfaceVariant
        switch (variant) {
        case "filled": return Theme.fgPrimary
        case "tonal": return Theme.fgSecondaryContainer
        case "error": return Theme.fgErrorContainer
        default: return Theme.primary
        }
    }
    readonly property real fullR: h / 2
    readonly property real smallR: size >= 2 ? Theme.rL : Theme.rM
    property real targetR: {
        if (pressed) return smallR
        if (toggle) return (checked !== square) ? smallR : fullR   // checked flips the shape
        return square ? smallR : fullR
    }
    property real animR: targetR
    Spring on animR { eps: 0.4 }
    property real sc: pressed ? 0.965 : 1
    Spring on sc { eps: 0.001 }

    Rectangle {
        id: bg
        anchors.fill: parent
        scale: b.sc
        radius: Math.max(0, b.animR)
        color: b.bgc
        Behavior on color { ColorAnimation { duration: Theme.dur(200) } }
        border.width: b.variant === "outlined" && !b.toggle ? 1 : 0
        border.color: Theme.outline
        Rectangle { anchors.fill: parent; radius: parent.radius; color: b.fgc
            opacity: ma.pressed ? 0.12 : (ma.containsMouse ? 0.08 : (b.activeFocus ? 0.1 : 0))
            Behavior on opacity { NumberAnimation { duration: Theme.dur(120) } } }
        Row {
            id: row
            anchors.centerIn: parent
            spacing: b.text.length && b.icon.length ? (b.size >= 2 ? 10 : 8) : 0
            Icon { visible: b.icon.length > 0; path: b.icon; size: b.iconSize; color: b.fgc; anchors.verticalCenter: parent.verticalCenter }
            Text { visible: b.text.length > 0; text: b.text; color: b.fgc; anchors.verticalCenter: parent.verticalCenter
                font: b.size >= 2 ? Theme.title : Theme.label; renderType: Text.NativeRendering }
        }
        Rectangle { anchors.fill: parent; anchors.margins: -3; radius: parent.radius + 3; color: "transparent"
            border.width: b.activeFocus ? 2 : 0; border.color: Theme.primary; visible: b.activeFocus }
    }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        onClicked: { b.forceActiveFocus(Qt.MouseFocusReason); b.clicked() } }
}
