import QtQuick

// A titled block of settings: small coloured heading, then its rows.
Column {
    id: sec
    property string title
    default property alias content: holder.data
    width: parent ? parent.width : 400
    spacing: 10
    Text { text: sec.title; font: Theme.titleS; color: Theme.primary; leftPadding: 12; renderType: Text.NativeRendering }
    Column { id: holder; width: sec.width; spacing: 18 }
}
