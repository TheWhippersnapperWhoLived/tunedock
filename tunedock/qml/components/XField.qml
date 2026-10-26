import QtQuick
import QtQuick.Controls.Basic as C

Item {
    id: f
    property string label
    property string text
    property string error
    property string placeholder
    property bool mono: false
    property bool readOnly: false
    property alias input: tf
    property string trailingIcon
    signal edited(string text)
    signal accepted()
    signal trailingClicked()
    implicitHeight: 62 + (error.length ? 22 : 0)
    implicitWidth: 320
    Rectangle {
        id: box
        width: parent.width; height: 62; radius: Theme.rL
        color: Theme.surfaceContainerHighest
        border.width: f.error.length ? 2 : (tf.activeFocus ? 2 : 0)
        border.color: f.error.length ? Theme.error : Theme.primary
        Behavior on border.width { NumberAnimation { duration: Theme.dur(120) } }
        Text { x: 16; y: 8; text: f.label; font: Theme.labelS; color: f.error.length ? Theme.error : (tf.activeFocus ? Theme.primary : Theme.fgSurfaceVariant); renderType: Text.NativeRendering }
        C.TextField {
            id: tf
            x: 8; y: 24; width: parent.width - 16 - (f.trailingIcon.length ? 44 : 0); height: 34
            text: f.text
            readOnly: f.readOnly
            font: f.mono ? Theme.mono : Theme.body
            color: Theme.fgSurface
            selectionColor: Theme.primary; selectedTextColor: Theme.fgPrimary
            placeholderText: f.placeholder; placeholderTextColor: Theme.outline
            verticalAlignment: TextInput.AlignVCenter
            background: Item {}
            selectByMouse: true
            clip: true
            onTextEdited: f.edited(text)
            onAccepted: f.accepted()
        }
        Item { visible: f.trailingIcon.length > 0; width: 44; height: 44; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            Icon { anchors.centerIn: parent; path: f.trailingIcon; size: 22; color: Theme.fgSurfaceVariant }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: f.trailingClicked() } }
    }
    Text { visible: f.error.length > 0; x: 16; y: 66; width: parent.width - 32; text: f.error; color: Theme.error; font: Theme.bodyS; wrapMode: Text.Wrap; renderType: Text.NativeRendering }
}
