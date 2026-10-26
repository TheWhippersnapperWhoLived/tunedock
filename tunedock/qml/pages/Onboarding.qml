import QtQuick
import QtQuick.Dialogs
import Td 1.0
import "../components"

// First-run setup: pick the music folder, then offer the right-click menu. Shown until finished or skipped.
Rectangle {
    id: ob
    property int step: 0
    property string msg: ""
    property bool instant: false
    readonly property bool open: Backend.cfg.onboarded !== true
    readonly property bool win: Backend.status.windows === true
    color: Theme.surface
    opacity: open ? 1 : 0
    visible: opacity > 0.01
    enabled: open
    Behavior on opacity { NumberAnimation { duration: Theme.dur(300); easing.type: Easing.OutCubic } }
    MouseArea { anchors.fill: parent; hoverEnabled: true }   // swallow clicks behind the overlay

    function finish() { Backend.setCfg("onboarded", true); step = 0; msg = "" }

    // step dots
    Row { anchors.horizontalCenter: parent.horizontalCenter; y: 36; spacing: 8
        Repeater { model: 2
            delegate: Rectangle { height: 8; radius: 4; color: index === ob.step ? Theme.primary : Theme.outlineVariant
                property real w: index === ob.step ? 28 : 8
                Spring on w { eps: 0.3 }
                width: Math.max(8, w) } } }

    // ---- step 1: music folder
    Pane {
        on: ob.open && ob.step === 0
        Column {
            anchors.centerIn: parent; width: Math.min(parent.width - 80, 560); spacing: 20
            Item { width: parent.width; height: 190
                Blob { anchors.centerIn: parent; size: 170; lobes: 9; amp: 0.09; color: Theme.primaryContainer
                    Icon { anchors.centerIn: parent; path: Icons.folder; size: 70; color: Theme.fgPrimaryContainer } } }
            Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; font: Theme.headline; text: "Welcome to Tunedock" }
            Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; color: Theme.fgSurfaceVariant
                text: Backend.status.libraryOk ? "Your music folder is set. Check it's the right one, then carry on."
                                               : "Start by choosing the folder where your music lives. New music will be filed inside it." }
            XField { width: parent.width; label: "Music folder"; mono: true; text: Backend.cfg.library_root; trailingIcon: Icons.folder
                placeholder: "D:\\Music"
                error: Backend.cfg.library_root.length > 0 && !Backend.status.libraryOk ? "That folder doesn't exist" : ""
                onEdited: (t) => Backend.setCfg("library_root", t); onTrailingClicked: dlg.open() }
            Row { anchors.horizontalCenter: parent.horizontalCenter; spacing: 12
                XButton { text: "Choose folder"; variant: "tonal"; size: 2; icon: Icons.folder; onClicked: dlg.open() }
                XButton { text: "Continue"; size: 2; icon: Icons.chevron; enabled: Backend.status.libraryOk === true; onClicked: ob.step = 1 } }
        }
    }

    // ---- step 2: right-click menu
    Pane {
        on: ob.open && ob.step === 1
        Column {
            anchors.centerIn: parent; width: Math.min(parent.width - 80, 560); spacing: 20
            Item { width: parent.width; height: 190
                Blob { anchors.centerIn: parent; size: 170; lobes: 12; amp: 0.07; color: Theme.tertiaryContainer
                    Icon { anchors.centerIn: parent; path: Icons.add; size: 70; color: Theme.fgTertiaryContainer } } }
            Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; font: Theme.headline; text: ob.win ? "Add it to your right-click menu" : "Almost there" }
            Txt { width: parent.width; horizontalAlignment: Text.AlignHCenter; color: Theme.fgSurfaceVariant
                text: ob.win ? "Right-click any song, album folder or zip in Explorer and choose \u201cAdd to music library\u201d. On Windows 11 it's under Show more options."
                             : "The right-click menu is a Windows feature. You can still drag music onto Tunedock." }
            Rectangle { visible: ob.win; width: parent.width; height: 76; radius: Theme.rXL; color: Theme.surfaceContainer
                Column { x: 22; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 44 - 70; spacing: 2
                    Txt { width: parent.width; text: "Open instantly (optional)"; font: Theme.titleS }
                    Txt { width: parent.width; text: "Keeps Tunedock running quietly in the notification area and starts it with Windows. Off unless you turn it on."; font: Theme.bodyS; color: Theme.fgSurfaceVariant } }
                XSwitch { anchors.right: parent.right; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter
                    checked: ob.instant; onToggled: (v) => ob.instant = v } }
            Txt { visible: ob.msg.length > 0; width: parent.width; horizontalAlignment: Text.AlignHCenter; text: ob.msg; color: Theme.error; font: Theme.bodyS }
            Row { anchors.horizontalCenter: parent.horizontalCenter; spacing: 12
                XButton { visible: ob.win; text: "Add to right-click menu"; size: 2; icon: Icons.check
                    onClicked: {
                        ob.msg = Backend.installMenu()
                        if (ob.msg === "") {
                            Backend.setCfg("keep_running", ob.instant)
                            Backend.setCfg("autostart", ob.instant)
                            ob.finish()
                        }
                    } }
                XButton { text: ob.win ? "Not now" : "Finish"; size: 2; variant: ob.win ? "text" : "filled"; onClicked: ob.finish() } }
            XButton { anchors.horizontalCenter: parent.horizontalCenter; text: "Back"; size: 1; variant: "text"; onClicked: ob.step = 0 }
        }
    }

    FolderDialog { id: dlg; title: "Choose your music folder"; onAccepted: Backend.setCfg("library_root", String(selectedFolder)) }
}
