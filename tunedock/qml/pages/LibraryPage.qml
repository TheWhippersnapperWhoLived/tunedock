import QtQuick
import QtQuick.Dialogs
import Td 1.0
import "../components"

PageBase {
    id: page
    title: "Library"
    subtitle: "Where your music lives, how you pick a folder, and what happens to the files you add."

    Section { title: "Your library"
        ListGroup {
            SettingRow { title: "Music folder"; desc: Backend.status.libraryOk ? Backend.status.libraryFolders.length + " folders at the top level" : "Not set yet. The folder picker starts here."
                XField { width: parent.width; label: "Library folder"; text: Backend.cfg.library_root; mono: true; trailingIcon: Icons.folder
                    onEdited: (t) => Backend.setCfg("library_root", t); onTrailingClicked: libDlg.open() } }
        }
    }

    Section { title: "Choosing a folder"
        ListGroup {
            SettingRow { title: "Skip ahead when it's obvious"; desc: "Files save as soon as you reach a folder with no sub-folders. Albums save once most sub-folders are albums. You can always press Stay."
                trailing: XSwitch { checked: Backend.cfg.auto_descend; onToggled: (v) => Backend.setCfg("auto_descend", v) } }
            SettingRow { title: "Wait before saving"; visible: Backend.cfg.auto_descend
                desc: Backend.cfg.auto_delay_ms === 0 ? "Instant: it saves the moment you reach the right folder, with no Stay button. Use New folder from the level above to make a place."
                                                       : "How long you get to press Stay before it saves"
                trailing: Text { text: Backend.cfg.auto_delay_ms === 0 ? "Instant" : (Backend.cfg.auto_delay_ms / 1000).toFixed(1) + " s"; font: Theme.title; color: Theme.primary }
                XSlider { width: parent.width; from: 0; to: 6000; stepSize: 100; value: Backend.cfg.auto_delay_ms
                    fmt: function (v) { return v === 0 ? "Instant" : (v / 1000).toFixed(1) + " s" }; onMoved: Backend.setCfg("auto_delay_ms", value) }
                Flow { width: parent.width; spacing: 8
                    Repeater { model: [ { l: "Instant", v: 0 }, { l: "0.5 s", v: 500 }, { l: "1.5 s", v: 1500 }, { l: "3 s", v: 3000 } ]
                        delegate: Chip { text: modelData.l; filter: false; selected: Backend.cfg.auto_delay_ms === modelData.v
                            onClicked: Backend.setCfg("auto_delay_ms", modelData.v) } } } }
            SettingRow { title: "Folder view"; desc: "Auto shows folders as a collage of tiles sized by what's inside, and switches to a plain list when there are too many to read comfortably."
                SegGroup { model: ["Auto", "Always a list"]; currentIndex: Backend.cfg.view_mode === "list" ? 1 : 0
                    onPicked: (i) => Backend.setCfg("view_mode", i === 1 ? "list" : "auto") } }
        }
    }

    Section { title: "Files you add"
        ListGroup {
            SettingRow { title: "If a file already exists"; desc: "Nothing new is ever overwritten. (Music that's already in the folder you add it to is reprocessed and replaced instead.)"
                SegGroup { model: ["Keep both", "Skip it"]; currentIndex: Backend.cfg.on_conflict === "skip" ? 1 : 0
                    onPicked: (i) => Backend.setCfg("on_conflict", i === 1 ? "skip" : "rename") } }
            SettingRow { title: "Bring along cover images and lyrics"; desc: "Copies cover.jpg, .lrc and similar files next to the music (lyrics follow renamed tracks)"
                trailing: XSwitch { checked: Backend.cfg.copy_others; onToggled: (v) => Backend.setCfg("copy_others", v) } }
            SettingRow { title: "Originals afterwards"
                desc: Backend.cfg.after === "delete" ? "Deleted for good once everything went in fine. For a folder that means the whole folder, including files that weren't copied."
                      : (Backend.cfg.after === "recycle" ? "Sent to the Recycle Bin once everything went in fine." : "Left where they are, like a copy.")
                SegGroup { model: [ "Keep them", { label: "Recycle Bin", enabled: Backend.status.recycle === true }, "Delete" ]
                    currentIndex: ["keep", "recycle", "delete"].indexOf(Backend.cfg.after)
                    onPicked: (i) => Backend.setCfg("after", ["keep", "recycle", "delete"][i]) } }
        }
    }

    FolderDialog { id: libDlg; title: "Choose your music folder"; onAccepted: Backend.setCfg("library_root", String(selectedFolder)) }
}
