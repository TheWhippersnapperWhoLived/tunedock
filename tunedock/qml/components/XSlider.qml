import QtQuick
import QtQuick.Controls.Basic as C

// Expressive slider: thick split track and a tall bar handle with a value bubble.
C.Slider {
    id: s
    property string unit: ""
    property var fmt: function (v) { return Math.round(v) + s.unit }
    implicitHeight: 52
    implicitWidth: 300
    snapMode: C.Slider.SnapAlways
    opacity: enabled ? 1 : 0.38
    background: Item {
        x: s.leftPadding; y: s.topPadding; width: s.availableWidth; height: s.availableHeight
        Rectangle { // active part
            y: (parent.height - 16) / 2; height: 16
            width: Math.max(0, s.visualPosition * parent.width - 8)
            topLeftRadius: 8; bottomLeftRadius: 8; topRightRadius: 3; bottomRightRadius: 3
            color: Theme.primary
        }
        Rectangle { // inactive part
            x: s.visualPosition * parent.width + 8; y: (parent.height - 16) / 2; height: 16
            width: Math.max(0, parent.width - x)
            topRightRadius: 8; bottomRightRadius: 8; topLeftRadius: 3; bottomLeftRadius: 3
            color: Theme.secondaryContainer
        }
    }
    handle: Item {
        x: s.leftPadding + s.visualPosition * s.availableWidth - width / 2
        y: s.topPadding + (s.availableHeight - height) / 2
        width: 12; height: 44
        Rectangle {
            anchors.centerIn: parent
            width: s.pressed ? 2 : 4; height: parent.height; radius: 2; color: Theme.primary
            Spring on width { eps: 0.1 }
        }
        Rectangle { // value bubble
            visible: opacity > 0.01
            opacity: s.pressed || s.hovered || s.activeFocus ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.dur(120) } }
            anchors.horizontalCenter: parent.horizontalCenter; y: -height - 6
            width: vt.implicitWidth + 24; height: 36; radius: 18; color: Theme.inverseSurface
            Text { id: vt; anchors.centerIn: parent; text: s.fmt(s.value); color: Theme.inverseOnSurface; font: Theme.label }
        }
    }
}
