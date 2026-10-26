import QtQuick
import QtQuick.Dialogs
import Td 1.0
import "../components"

PageBase {
    id: page
    title: "System"
    subtitle: "The right-click menu, notifications and running in the background."
    property string menuMsg: ""
    readonly property bool win: Backend.status.windows === true

    Section { title: "Right-click menu"
        ListGroup {
            SettingRow { title: "Explorer menu"
                desc: win ? "Adds \u201cAdd to music library\u201d for audio files, folders and archives. On Windows 11 it sits under Show more options."
                          : "Explorer integration is only available on Windows."
                trailing: Row { spacing: 8
                    XButton { text: Backend.status.menuInstalled ? "Update" : "Install"; size: 1; enabled: page.win
                        onClicked: page.menuMsg = Backend.installMenu() }
                    XButton { text: "Remove"; size: 1; variant: "tonal"; visible: Backend.status.menuInstalled === true
                        onClicked: page.menuMsg = Backend.removeMenu() } }
                Txt { visible: page.menuMsg.length > 0; width: parent.width; text: page.menuMsg; color: Theme.error; font: Theme.bodyS } }
            SettingRow { title: "Menu style"; desc: "One entry opens the folder picker. Branching adds one entry per top-level folder that saves instantly with no window, just a small card in the corner."
                SegGroup { model: ["One entry", "Branching"]; currentIndex: Backend.cfg.menu_mode === "submenu" ? 1 : 0
                    onPicked: (i) => Backend.setCfg("menu_mode", i === 1 ? "submenu" : "single") } }
            SettingRow { title: "Quick-add folders"; visible: Backend.cfg.menu_mode === "submenu"
                desc: Backend.status.libraryFolders.length === 0 ? "Set your music folder (Library page) to see its folders here"
                      : (Backend.cfg.menu_folders.length === 0 ? "All top-level folders appear. Tap to choose just some." : "Only the highlighted folders appear")
                Flow { width: parent.width; spacing: 8
                    Repeater { model: Backend.status.libraryFolders
                        delegate: Chip { text: modelData
                            selected: Backend.cfg.menu_folders.length === 0 || Backend.cfg.menu_folders.indexOf(modelData) >= 0
                            onClicked: {
                                var cur = Backend.cfg.menu_folders.length === 0 ? Backend.status.libraryFolders.slice() : Backend.cfg.menu_folders.slice()
                                var i = cur.indexOf(modelData)
                                if (i >= 0) cur.splice(i, 1); else cur.push(modelData)
                                if (cur.length === Backend.status.libraryFolders.length) cur = []
                                Backend.setCfg("menu_folders", cur)
                            } } } } }
            SettingRow { title: "Registry file"; visible: page.win; desc: "Save the menu as .reg files to review or apply by hand. A matching remove file is included."
                trailing: XButton { text: "Export"; size: 1; variant: "tonal"; onClicked: regDlg.open() } }
        }
    }

    Section { title: "Notifications"
        ListGroup {
            SettingRow { title: "Progress card"; desc: "Show the small card at the corner of the screen (and a Windows notification) while a right-click add runs and when it's done. Problems always show."
                trailing: XSwitch { checked: Backend.cfg.notify; onToggled: (v) => Backend.setCfg("notify", v) } }
        }
    }

    Section { title: "Background & startup (optional)"
        ListGroup {
            SettingRow { title: "Stay ready in the background"
                desc: "Off by default. Keeps Tunedock quietly running with an icon in the notification area, so the right-click menu opens it instantly instead of after a few seconds."
                trailing: XSwitch { checked: Backend.cfg.keep_running; onToggled: (v) => Backend.setCfg("keep_running", v) } }
            SettingRow { title: "Start with Windows"; visible: page.win
                desc: Backend.cfg.keep_running ? "So it's already waiting after you sign in." : "Turn on \u201cStay ready in the background\u201d first."
                trailing: XSwitch { enabled: Backend.cfg.keep_running; checked: Backend.cfg.autostart && Backend.cfg.keep_running; onToggled: (v) => Backend.setCfg("autostart", v) } }
            SettingRow { title: "Quit the background copy"; visible: Backend.cfg.keep_running; desc: "Stops it for now. It starts again the next time you use Tunedock."
                trailing: XButton { text: "Quit"; size: 1; variant: "tonal"; onClicked: Backend.quitApp() } }
        }
    }

    Section { title: "Shortcuts & setup"
        ListGroup {
            SettingRow { title: "Start menu shortcut"; visible: page.win; desc: "Adds Tunedock to the Start menu so you can open or pin it without any console window."
                trailing: XButton { text: "Create"; size: 1; variant: "tonal"; onClicked: page.menuMsg = Backend.createShortcut() === "" ? "Shortcut added to the Start menu." : "Couldn't create the shortcut." } }
            SettingRow { title: "Setup guide"; desc: "Go through the first-run steps again."
                trailing: XButton { text: "Run again"; size: 1; variant: "tonal"; onClicked: Backend.setCfg("onboarded", false) } }
        }
    }

    FolderDialog { id: regDlg; title: "Save .reg files to"; onAccepted: page.menuMsg = Backend.exportReg(String(selectedFolder)) ? "Saved." : "Couldn't save the files." }
}
