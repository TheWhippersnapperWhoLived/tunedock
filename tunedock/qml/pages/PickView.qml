import QtQuick
import QtQuick.Controls.Basic as C
import Td 1.0
import "../components"

Pane {
    id: v
    signal requestPage(int index)
    readonly property var nav: Backend.nav
    readonly property var scan: Backend.scan
    readonly property bool scanning: Backend.stage === "scanning"
    property bool stay: false
    property real countdown: 0
    property bool creating: false
    readonly property bool ffReady: Backend.status.ffmpegReady !== false
    readonly property bool canSave: nav.ok === true && !nav.loading && scan.tracks > 0 && ffReady
    readonly property bool autoOn: canSave && nav.decision.auto === true && Backend.cfg.auto_descend && !stay && !creating && on

    readonly property bool instant: Backend.cfg.auto_delay_ms === 0
    function fire() {
        if (!autoOn) return
        countdown = 0; stay = true
        Backend.chooseHere()
    }
    onAutoOnChanged: {
        countdown = 0
        if (autoOn && instant) Qt.callLater(fire)   // instant: save the moment we arrive
    }
    Connections { target: Backend; function onNavChanged() { v.stay = false; v.countdown = 0 } }
    Timer {
        interval: 30; repeat: true; running: v.autoOn && !v.instant
        onTriggered: {
            v.countdown += 30 / Backend.cfg.auto_delay_ms
            if (v.countdown >= 1) v.fire()
        }
    }

    // ---- collage: tiles sized by what is inside, only while it stays readable
    readonly property var entries: nav.ok === true && !nav.loading ? nav.entries : []
    property var rects: []
    readonly property bool collage: Backend.cfg.view_mode !== "list" && rects.length >= 3 && rects.length === entries.length
    readonly property var pal: [
        [Theme.primaryContainer, Theme.fgPrimaryContainer], [Theme.tertiaryContainer, Theme.fgTertiaryContainer],
        [Theme.secondaryContainer, Theme.fgSecondaryContainer], [Theme.primary, Theme.fgPrimary],
        [Theme.tertiary, Theme.fgTertiary], [Theme.secondary, Theme.fgSecondary]]
    function hash(str) { var h = 7; for (var i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0; return h }
    function weight(e) { var n = Math.max(0, e.subs) * 2 + Math.max(0, e.audio); return 1 + Math.min(10, Math.sqrt(n) * 1.4) }
    // squarified treemap: rectangles with areas proportional to the weights, kept as square as possible
    function squarify(ws, W, H) {
        var idx = ws.map(function (_, i) { return i }).sort(function (a, b) { return ws[b] - ws[a] })
        var total = ws.reduce(function (a, b) { return a + b }, 0), k = W * H / total
        var out = new Array(ws.length), x = 0, y = 0, w = W, h = H, row = []
        function worst(r, side) {
            var s = 0, mx = 0, mn = 1e18
            for (var i = 0; i < r.length; i++) { s += r[i].a; mx = Math.max(mx, r[i].a); mn = Math.min(mn, r[i].a) }
            return Math.max(side * side * mx / (s * s), s * s / (side * side * mn))
        }
        function place(r) {
            var s = 0, i
            for (i = 0; i < r.length; i++) s += r[i].a
            if (w >= h) { var cw = s / h, cy = y
                for (i = 0; i < r.length; i++) { out[r[i].i] = { x: x, y: cy, w: cw, h: r[i].a / cw }; cy += r[i].a / cw }
                x += cw; w -= cw
            } else { var rh = s / w, cx = x
                for (i = 0; i < r.length; i++) { out[r[i].i] = { x: cx, y: y, w: r[i].a / rh, h: rh }; cx += r[i].a / rh }
                y += rh; h -= rh }
        }
        var i = 0
        while (i < idx.length) {
            var side = Math.min(w, h), item = { i: idx[i], a: ws[idx[i]] * k }
            if (row.length === 0 || worst(row.concat([item]), side) <= worst(row, side)) { row.push(item); i++ }
            else { place(row); row = [] }
        }
        if (row.length) place(row)
        return out
    }
    function relayout() {
        var n = entries.length
        if (n < 3 || n > 40 || list.width < 200 || list.height < 160) { rects = []; return }
        var r = squarify(entries.map(weight), list.width, list.height), minSide = 1e9
        for (var i = 0; i < r.length; i++) minSide = Math.min(minSide, r[i].w, r[i].h)
        rects = minSide >= 88 ? r : []      // too cramped to read: fall back to the list
    }
    onEntriesChanged: Qt.callLater(relayout)
    Connections { target: list; function onWidthChanged() { Qt.callLater(v.relayout) } function onHeightChanged() { Qt.callLater(v.relayout) } }

    // ---- what is being added
    Rectangle {
        id: summary
        x: 28; y: 24; width: parent.width - 56; height: 92
        radius: Theme.rXL; color: Theme.secondaryContainer
        Blob { id: sb; x: 18; anchors.verticalCenter: parent.verticalCenter; size: 56; lobes: v.scanning ? 6 : 9; amp: 0.1; color: Theme.primary
            Text { anchors.centerIn: parent; text: v.scanning ? "" : scan.tracks; font: Theme.titleS; color: Theme.fgPrimary } }
        Column {
            x: 92; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 92 - 130; spacing: 3
            Txt { width: parent.width; font: Theme.title; color: Theme.fgSecondaryContainer; elide: Text.ElideRight; maximumLineCount: 1
                text: v.scanning ? "Reading your files\u2026" : (scan.tracks === 0 ? "No music found" :
                      scan.tracks + (scan.tracks === 1 ? " track" : " tracks") + (scan.albums > 0 ? " \u00b7 " + scan.albums + (scan.albums === 1 ? " album" : " albums") : "")) }
            Txt { width: parent.width; font: Theme.bodyS; color: Theme.fgSecondaryContainer; opacity: 0.8; elide: Text.ElideRight; maximumLineCount: 1
                text: scan.errors && scan.errors.length ? scan.errors[0] : (scan.labels ? scan.labels.join(", ") : "") }
        }
        XButton { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
            text: "Clear"; size: 1; variant: "text"; onClicked: Backend.clearQueue() }
    }

    // ---- breadcrumbs
    Flickable {
        id: crumbs
        x: 28; y: summary.y + summary.height + 14; width: parent.width - 56; height: 40
        contentWidth: crow.width; contentHeight: height; clip: true; interactive: contentWidth > width
        boundsBehavior: Flickable.StopAtBounds
        visible: nav.ok === true
        onContentWidthChanged: contentX = Math.max(0, contentWidth - width)
        Row { id: crow; spacing: 4; height: parent.height
            Repeater { model: nav.parts
                delegate: Row { spacing: 4; anchors.verticalCenter: parent.verticalCenter
                    Icon { visible: index > 0; path: Icons.chevron; size: 18; color: Theme.outline; anchors.verticalCenter: parent.verticalCenter }
                    Chip { text: modelData.name; icon: index === 0 ? Icons.home : ""; filter: false
                        selected: index === nav.parts.length - 1; onClicked: Backend.navTo(modelData.path) } } } }
    }

    // ---- folder list
    ListView {
        id: list
        x: 28; y: crumbs.y + crumbs.height + 8; width: parent.width - 56
        height: parent.height - y - 120
        clip: true; spacing: 3
        model: v.collage ? [] : v.entries
        boundsBehavior: Flickable.StopAtBounds
        C.ScrollBar.vertical: C.ScrollBar {}
        populate: Transition { SequentialAnimation {
            PropertyAction { property: "opacity"; value: 0 }
            PauseAnimation { duration: Theme.dur(Math.max(0, Math.min(ViewTransition.index, 12)) * 22) }
            ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 1; duration: Theme.dur(220) }
                NumberAnimation { property: "y"; from: ViewTransition.destination.y + 18; duration: Theme.dur(300); easing.type: Easing.OutBack; easing.overshoot: 1.4 } } } }
        delegate: Rectangle {
            id: row
            width: ListView.view.width; height: 68
            color: Theme.surfaceContainer
            readonly property int rr: Theme.rXL
            topLeftRadius: index === 0 ? rr : Theme.rS; topRightRadius: index === 0 ? rr : Theme.rS
            bottomLeftRadius: index === list.count - 1 ? rr : Theme.rS; bottomRightRadius: index === list.count - 1 ? rr : Theme.rS
            Rectangle { anchors.fill: parent; color: Theme.fgSurface; opacity: rma.pressed ? 0.1 : (rma.containsMouse ? 0.06 : 0)
                topLeftRadius: parent.topLeftRadius; topRightRadius: parent.topRightRadius; bottomLeftRadius: parent.bottomLeftRadius; bottomRightRadius: parent.bottomRightRadius }
            Rectangle { x: 14; anchors.verticalCenter: parent.verticalCenter; width: 44; height: 44; radius: Theme.rL; color: Theme.secondaryContainer
                Icon { anchors.centerIn: parent; path: Icons.folder; color: Theme.fgSecondaryContainer } }
            Column { x: 72; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 72 - 56; spacing: 2
                Txt { width: parent.width; text: modelData.name; font: Theme.titleS; elide: Text.ElideRight; maximumLineCount: 1 }
                Txt { width: parent.width; font: Theme.bodyS; color: Theme.fgSurfaceVariant
                    text: modelData.subs > 0 ? modelData.subs + (modelData.subs === 1 ? " folder" : " folders") : (modelData.audio > 0 ? modelData.audio + " tracks" : "Empty") } }
            Icon { anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; path: Icons.chevron; color: Theme.outline }
            MouseArea { id: rma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Backend.navTo(modelData.path) }
        }
        Column { anchors.centerIn: parent; spacing: 10; visible: v.entries.length === 0 && nav.ok === true && !nav.loading
            Blob { size: 72; lobes: 7; amp: 0.08; color: Theme.surfaceContainerHigh; anchors.horizontalCenter: parent.horizontalCenter; spin: false
                Icon { anchors.centerIn: parent; path: Icons.folder; color: Theme.outline; size: 30 } }
            Txt { text: "No folders in here"; color: Theme.fgSurfaceVariant; anchors.horizontalCenter: parent.horizontalCenter } }
    }
    // ---- the collage itself
    Item {
        id: collageArea
        x: list.x; y: list.y; width: list.width; height: list.height
        visible: v.collage
        Repeater {
            model: v.collage ? v.entries : []
            delegate: Item {
                id: tile
                readonly property var r: v.rects[index] ? v.rects[index] : { x: 0, y: 0, w: 0, h: 0 }
                readonly property var c: v.pal[v.hash(modelData.name) % v.pal.length]
                readonly property real minSide: Math.min(width, height)
                readonly property int longest: Math.max.apply(null, modelData.name.split(/[\s_-]+/).map(function (w) { return w.length }))
                // big enough to feel like a tile, small enough that the longest word never breaks mid-word
                readonly property real labelPx: Math.max(12, Math.min(Math.sqrt(width * height) / 7.5, 30,
                                                          (width - 2 * Math.min(22, minSide / 6)) / (Math.max(4, longest) * 0.74)))
                x: r.x + 4; y: r.y + 4; width: Math.max(0, r.w - 8); height: Math.max(0, r.h - 8)
                property bool appeared: false
                property real sc: ma2.pressed ? 0.97 : (ma2.containsMouse ? 1.025 : 1)
                Spring on sc { eps: 0.001 }
                opacity: appeared ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.dur(240) } }
                Timer { interval: Theme.reduce ? 0 : Math.min(index, 14) * 32; running: true; onTriggered: tile.appeared = true }
                activeFocusOnTab: true
                Keys.onReturnPressed: Backend.navTo(modelData.path)
                Keys.onSpacePressed: Backend.navTo(modelData.path)
                Rectangle {
                    anchors.fill: parent
                    scale: tile.appeared ? tile.sc : 0.82
                    Behavior on scale { enabled: !tile.appeared || Theme.reduce; NumberAnimation { duration: Theme.dur(420); easing.type: Easing.OutBack; easing.overshoot: 1.6 } }
                    radius: Math.min(36, tile.minSide / 4)
                    color: tile.c[0]
                    Rectangle { anchors.fill: parent; radius: parent.radius; color: tile.c[1]; opacity: ma2.pressed ? 0.14 : (ma2.containsMouse ? 0.08 : 0) }
                    Rectangle { anchors.fill: parent; anchors.margins: -3; radius: parent.radius + 3; color: "transparent"; border.width: 2; border.color: Theme.primary; visible: tile.activeFocus }
                    Icon { x: Math.min(22, tile.minSide / 6); y: x; path: Icons.folder; color: tile.c[1]; opacity: 0.85
                        size: Math.max(22, Math.min(44, tile.minSide / 4)) }
                    Column {
                        x: Math.min(22, tile.minSide / 6); width: parent.width - 2 * x
                        anchors.bottom: parent.bottom; anchors.bottomMargin: Math.min(20, tile.minSide / 7); spacing: 2
                        Text { width: parent.width; text: modelData.name; color: tile.c[1]; wrapMode: Text.Wrap; maximumLineCount: tile.height > 190 ? 3 : 2
                            elide: Text.ElideRight; font.pixelSize: tile.labelPx; font.weight: Font.DemiBold
                            renderType: Text.NativeRendering }
                        Text { visible: tile.minSide >= 110; width: parent.width; color: tile.c[1]; opacity: 0.8; font: Theme.bodyS; elide: Text.ElideRight; renderType: Text.NativeRendering
                            text: modelData.subs > 0 ? modelData.subs + (modelData.subs === 1 ? " folder" : " folders") : (modelData.audio > 0 ? modelData.audio + " tracks" : "Empty") }
                    }
                }
                MouseArea { id: ma2; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Backend.navTo(modelData.path) }
            }
        }
    }
    // loading wave
    WavyProgress { x: 28; y: list.y + 6; width: parent.width - 56; visible: nav.loading === true; value: -1 }

    // ---- no library yet
    Rectangle {
        visible: nav.ok !== true && !v.scanning
        anchors.centerIn: list; width: Math.min(460, parent.width - 80); height: 190; radius: Theme.rXL; color: Theme.tertiaryContainer
        Column { anchors.centerIn: parent; spacing: 14; width: parent.width - 48
            Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: "Where does your music live?"; font: Theme.title; color: Theme.fgTertiaryContainer }
            Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: "Pick your main music folder once. You'll navigate from there each time."; color: Theme.fgTertiaryContainer }
            XButton { anchors.horizontalCenter: parent.horizontalCenter; text: "Open Library settings"; onClicked: v.requestPage(1) } }
    }

    // ---- auto-save banner
    Rectangle {
        id: banner
        property real slide: v.autoOn && !v.instant ? 0 : 90
        Spring on slide { eps: 0.3 }
        visible: slide < 89
        x: 28; width: parent.width - 56; height: 74; y: parent.height - 108 - height + 8 + slide
        radius: Theme.rXL; color: Theme.inverseSurface
        Column { x: 22; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 44 - 120; spacing: 6
            Txt { width: parent.width; color: Theme.inverseOnSurface; font: Theme.titleS; elide: Text.ElideMiddle; maximumLineCount: 1
                text: (nav.allInplace ? "Reprocessing in " : "Adding to ") + (nav.name ? nav.name : "") }
            WavyProgress { width: parent.width; value: v.countdown; color: Theme.inversePrimary; trackColor: Qt.rgba(1, 1, 1, 0.18); height: 14; thickness: 4; amp: 2.5 } }
        XButton { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
            text: "Stay"; size: 1; variant: "text"; customFg: Theme.inversePrimary; onClicked: v.stay = true }
    }

    // ---- bottom bar
    Item {
        id: bar
        x: 28; width: parent.width - 56; height: 72; y: parent.height - height - 22
        XButton { id: upBtn; anchors.verticalCenter: parent.verticalCenter; size: 2; variant: "tonal"; icon: Icons.up
            visible: nav.ok === true && nav.atRoot === false; onClicked: Backend.navUp() }
        XButton { id: newBtn; anchors.verticalCenter: parent.verticalCenter; x: upBtn.visible ? upBtn.width + 12 : 0
            size: 2; variant: "tonal"; icon: Icons.folderPlus; text: "New folder"; visible: nav.ok === true
            onClicked: { v.creating = !v.creating; if (v.creating) nameField.input.forceActiveFocus() } }
        Txt { visible: !v.ffReady && nav.ok === true; anchors.verticalCenter: parent.verticalCenter
            x: (newBtn.visible ? newBtn.x + newBtn.width : 0) + 18; width: parent.width - x - 260; color: Theme.error; font: Theme.bodyS; wrapMode: Text.Wrap
            text: Backend.ffmpegDl.state === "downloading" ? "Getting ffmpeg ready\u2026 " + (Backend.ffmpegDl.pct >= 0 ? Math.round(Backend.ffmpegDl.pct * 100) + "%" : "") : "ffmpeg is needed to convert. See the Convert page." }
        Txt { visible: v.ffReady && nav.ok === true && nav.inplace > 0 && !nav.allInplace; anchors.verticalCenter: parent.verticalCenter
            x: (newBtn.visible ? newBtn.x + newBtn.width : 0) + 18; width: parent.width - x - 260; color: Theme.fgSurfaceVariant; font: Theme.bodyS; wrapMode: Text.Wrap
            text: nav.inplace + " already here: those get reprocessed and replaced" }
        XButton { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            size: 2; icon: nav.allInplace ? Icons.sync : Icons.check; enabled: v.canSave
            text: (nav.allInplace ? "Reprocess in " : "Add to ") + (nav.name ? (nav.name.length > 20 ? nav.name.substring(0, 19) + "\u2026" : nav.name) : "here")
            onClicked: Backend.chooseHere() }
    }

    // ---- new folder card
    Rectangle {
        id: nf
        property real slide: v.creating ? 0 : 140
        Spring on slide { eps: 0.3 }
        visible: slide < 139
        width: Math.min(420, parent.width - 56); height: 92
        x: 28; y: parent.height - 22 - 72 - height - 12 + slide
        radius: Theme.rXL; color: Theme.surfaceContainerHigh
        property string err: ""
        XField { id: nameField; x: 12; y: 15; width: parent.width - 24 - 120; label: "Folder name"; onAccepted: nf.create()
            error: ""; }
        XButton { anchors.right: parent.right; anchors.rightMargin: 12; y: 26; text: "Create"; size: 1; onClicked: nf.create() }
        function create() {
            var e = Backend.newFolder(nameField.input.text)
            if (e === "") { v.creating = false; nameField.input.text = "" }
        }
    }
}
