import QtQuick
import QtQuick.Dialogs
import Td 1.0
import "../components"

Pane {
    id: v
    signal requestPage(int index)
    readonly property var fmtInfo: Backend.formats.find(f => f.key === Backend.cfg.format)
    function summary() {
        var c = Backend.cfg
        if (c.format === "keep") return "Keeping original formats"
        var f = fmtInfo
        var q = f.lossy ? (c.format === "mp3" && c.mp3_vbr ? "V" + c.mp3_vq : c["br_" + c.format] + " kbps") : "lossless"
        return "Converting to " + f.label + " \u00b7 " + q
    }

    DropArea {
        id: drop
        anchors.fill: parent
        onDropped: (d) => { if (d.hasUrls) Backend.addPaths(d.urls.map(String)) }
    }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 600)
        spacing: 20

        Item {
            width: parent.width; height: 270
            Blob {
                id: blob
                anchors.centerIn: parent
                size: drop.containsDrag ? 262 : 228
                Spring on size { eps: 0.3 }
                lobes: drop.containsDrag ? 6 : 9
                amp: drop.containsDrag ? 0.15 : 0.085
                color: drop.containsDrag ? Theme.tertiaryContainer : Theme.primaryContainer
                Behavior on color { ColorAnimation { duration: Theme.dur(250) } }
                Icon { anchors.centerIn: parent; path: drop.containsDrag ? Icons.add : Icons.music; size: 84
                    color: drop.containsDrag ? Theme.fgTertiaryContainer : Theme.fgPrimaryContainer }
            }
        }
        Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: drop.containsDrag ? "Let go to add" : "Drop music here"; font: Theme.headline }
        Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; color: Theme.fgSurfaceVariant
            text: "Files, folders, zip, 7z and rar all work. You can also right-click them in Explorer." }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 12
            XButton { text: "Add files"; icon: Icons.music; size: 2; onClicked: files.open() }
            XButton { text: "Add folder"; icon: Icons.folder; size: 2; variant: "tonal"; onClicked: folder.open() }
        }

        // gentle status line, or a call to action if setup is missing
        Item { width: parent.width; height: 56
            Rectangle { visible: !Backend.status.libraryOk; anchors.fill: parent; radius: Theme.rXL; color: Theme.tertiaryContainer
                Icon { x: 18; anchors.verticalCenter: parent.verticalCenter; path: Icons.info; color: Theme.fgTertiaryContainer }
                Txt { x: 54; width: parent.width - 54 - 150; anchors.verticalCenter: parent.verticalCenter; text: "Choose your music folder to start"; color: Theme.fgTertiaryContainer }
                XButton { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; text: "Choose"; size: 0; variant: "text"; onClicked: v.requestPage(1) } }
            Rectangle { id: ffcard; visible: Backend.status.libraryOk && Backend.status.ffmpegReady === false; anchors.fill: parent; radius: Theme.rXL; color: Theme.errorContainer
                readonly property var dl: Backend.ffmpegDl
                Rectangle { x: 14; anchors.verticalCenter: parent.verticalCenter; width: 30; height: 30; radius: 15; color: Theme.error
                    Icon { anchors.centerIn: parent; path: Icons.close; size: 18; color: Theme.fgError } }
                Txt { x: 58; width: parent.width - 58 - 150; anchors.verticalCenter: parent.verticalCenter; color: Theme.fgErrorContainer; elide: Text.ElideRight; maximumLineCount: 1
                    text: ffcard.dl.state === "downloading" ? "Downloading ffmpeg (needed to convert)\u2026 " + (ffcard.dl.pct >= 0 ? Math.round(ffcard.dl.pct * 100) + "%" : ffcard.dl.msg)
                          : (ffcard.dl.state === "error" ? "Couldn't download ffmpeg" : Backend.status.ffmpegNote + " (needed to convert)") }
                WavyProgress { visible: ffcard.dl.state === "downloading"; x: 58; y: parent.height - 14; width: parent.width - 58 - 150; height: 10; thickness: 3; amp: 2; value: ffcard.dl.pct
                    color: Theme.error; trackColor: Qt.rgba(1, 1, 1, 0.5) }
                XButton { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; size: 0; variant: "text"
                    visible: ffcard.dl.state !== "downloading"; text: Backend.status.canDownload ? (ffcard.dl.state === "error" ? "Retry" : "Download") : "Fix"
                    onClicked: Backend.status.canDownload ? Backend.downloadFfmpeg() : v.requestPage(2) } }
            Txt { visible: Backend.status.libraryOk && Backend.status.ffmpegReady !== false
                width: parent.width; horizontalAlignment: Text.AlignHCenter; anchors.verticalCenter: parent.verticalCenter
                color: Theme.fgSurfaceVariant; font: Theme.bodyS
                text: v.summary() + "  \u2192  " + Backend.cfg.library_root; elide: Text.ElideMiddle; maximumLineCount: 1 }
        }
    }

    FileDialog {
        id: files
        title: "Add music files"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Music and archives (*.mp3 *.flac *.m4a *.opus *.ogg *.wav *.aac *.wma *.ape *.wv *.aiff *.zip *.7z *.rar *.tar *.gz)", "All files (*)"]
        onAccepted: Backend.addPaths(selectedFiles.map(String))
    }
    FolderDialog {
        id: folder
        title: "Add a music folder"
        onAccepted: Backend.addPaths([String(selectedFolder)])
    }
}
