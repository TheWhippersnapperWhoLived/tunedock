import QtQuick

Rectangle {
    id: r
    property string title
    property string desc
    property int rTop: Theme.rS
    property int rBottom: Theme.rS
    property alias trailing: rightSlot.data
    default property alias below: belowCol.data
    property bool stacked: false     // put the control under the text instead of beside it
    width: parent ? parent.width : 400
    color: Theme.surfaceContainer
    topLeftRadius: rTop; topRightRadius: rTop; bottomLeftRadius: rBottom; bottomRightRadius: rBottom
    onVisibleChanged: if (parent && parent.relayout) parent.relayout()
    readonly property bool hasBelow: belowCol.children.length > 0
    height: (hasBelow ? belowCol.y + belowCol.height : head.y + head.height) + 18

    Item {
        id: head
        x: 22; y: 18; width: r.width - 44
        height: Math.max(textCol.height, rightSlot.height)
        Column {
            id: textCol
            width: parent.width - rightSlot.width - (rightSlot.width > 0 ? 20 : 0)
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            Txt { width: parent.width; text: r.title; font: Theme.titleS }
            Txt { width: parent.width; visible: r.desc.length > 0; text: r.desc; font: Theme.bodyS; color: Theme.fgSurfaceVariant }
        }
        Row { id: rightSlot; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8 }
    }
    Column { id: belowCol; x: 22; y: head.y + head.height + 14; width: r.width - 44; spacing: 12 }
}
