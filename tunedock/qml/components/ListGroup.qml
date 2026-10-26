import QtQuick

// A stack of rows with big outer corners and tight inner ones (M3 Expressive segmented list).
Column {
    id: g
    spacing: 3
    width: parent ? parent.width : 400
    function relayout() {
        var vis = []
        for (var i = 0; i < children.length; i++)
            if (children[i].visible && children[i].rTop !== undefined) vis.push(children[i])
        for (var j = 0; j < vis.length; j++) {
            vis[j].rTop = j === 0 ? Theme.rXL : Theme.rS
            vis[j].rBottom = j === vis.length - 1 ? Theme.rXL : Theme.rS
        }
    }
    onChildrenChanged: relayout()
    Component.onCompleted: relayout()
}
