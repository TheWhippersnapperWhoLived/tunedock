import QtQuick
import Td 1.0
import "../components"

Pane {
    id: v
    readonly property var r: Backend.report
    readonly property bool good: r.kind === "ok"
    readonly property bool bad: r.kind === "error"
    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 600)
        spacing: 18
        Item { width: parent.width; height: 190
            Blob { anchors.centerIn: parent; size: 170; lobes: v.bad ? 5 : 12; amp: v.bad ? 0.1 : 0.07
                color: v.bad ? Theme.errorContainer : (v.good ? Theme.tertiaryContainer : Theme.secondaryContainer)
                Icon { anchors.centerIn: parent; size: 76; path: v.bad ? Icons.warning : (v.good ? Icons.check : Icons.info)
                    color: v.bad ? Theme.fgErrorContainer : (v.good ? Theme.fgTertiaryContainer : Theme.fgSecondaryContainer) } }
        }
        Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; font: Theme.headline; text: r.title ? r.title : "" }
        Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; color: Theme.fgSurfaceVariant; visible: text.length > 0; text: r.sub ? r.sub : "" }

        Row { anchors.horizontalCenter: parent.horizontalCenter; spacing: 6; visible: !r.fatal
            Repeater {
                model: [ { k: "converted", l: "Converted" }, { k: "copied", l: "Copied" }, { k: "skipped", l: "Skipped" }, { k: "failed", l: "Failed" } ]
                delegate: Rectangle { width: 112; height: 78; color: Theme.surfaceContainer
                    topLeftRadius: index === 0 ? Theme.rXL : Theme.rS; bottomLeftRadius: index === 0 ? Theme.rXL : Theme.rS
                    topRightRadius: index === 3 ? Theme.rXL : Theme.rS; bottomRightRadius: index === 3 ? Theme.rXL : Theme.rS
                    Column { anchors.centerIn: parent; spacing: 2
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: r[modelData.k] !== undefined ? r[modelData.k] : 0; font: Theme.title
                            color: modelData.k === "failed" && r.failed > 0 ? Theme.error : Theme.fgSurface }
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.l; font: Theme.labelS; color: Theme.fgSurfaceVariant } } } } }
        Txt { visible: r.bytes_in > 0 && !r.fatal; width: parent.width; horizontalAlignment: Text.AlignHCenter; color: Theme.fgSurfaceVariant; font: Theme.bodyS
            text: r.inMB + " MB in \u2192 " + r.outMB + " MB out \u00b7 " + r.seconds + " s" + (r.replaced > 0 ? " \u00b7 " + r.replaced + " replaced in place" : "") }
        Rectangle { visible: !!(r.errors && r.errors.length > 0); width: parent.width; height: Math.min(110, errs.implicitHeight + 24); radius: Theme.rL; color: Theme.errorContainer; clip: true
            Txt { id: errs; x: 14; y: 12; width: parent.width - 28; font: Theme.bodyS; color: Theme.fgErrorContainer
                text: r.errors ? r.errors.slice(0, 6).join("\n") + (r.errors.length > 6 ? "\n\u2026and " + (r.errors.length - 6) + " more" : "") : "" } }
        Row { anchors.horizontalCenter: parent.horizontalCenter; spacing: 12
            XButton { text: "Open folder"; size: 2; icon: Icons.open; visible: !r.fatal; onClicked: Backend.openPath(r.dest) }
            XButton { text: "Add more"; size: 2; variant: "tonal"; icon: Icons.add; onClicked: Backend.finish() } }
    }
}
