import QtQuick
import Td 1.0
import "../components"

PageBase {
    id: page
    title: "Names"
    subtitle: "Decide how files and album folders are named. Changes show instantly."
    readonly property var pv: Backend.preview(Backend.cfg.file_template)
    readonly property var fv: Backend.preview(Backend.cfg.folder_template)

    Rectangle {
        width: parent.width; height: pcol.implicitHeight + 36; radius: Theme.rXL; color: Theme.primaryContainer
        Column { id: pcol; x: 22; y: 18; width: parent.width - 44; spacing: 6
            Text { text: "Tagged track"; font: Theme.labelS; color: Theme.fgPrimaryContainer; opacity: 0.75 }
            Text { width: parent.width; text: Backend.cfg.file_template.trim().length === 0 ? "(original name kept)" : (page.pv.ok ? page.pv.text + ".opus" : "Fix the pattern below")
                font: Theme.title; color: Theme.fgPrimaryContainer; elide: Text.ElideRight; maximumLineCount: 1 }
            Text { text: "Untagged file (named from its file name)"; font: Theme.labelS; color: Theme.fgPrimaryContainer; opacity: 0.75; topPadding: 6 }
            Text { width: parent.width; text: Backend.cfg.file_template.trim().length === 0 ? "(original name kept)" : (page.pv.ok ? page.pv.untagged + ".opus" : "")
                font: Theme.titleS; color: Theme.fgPrimaryContainer; elide: Text.ElideRight; maximumLineCount: 1; opacity: 0.9 } }
    }

    ListGroup {
        SettingRow { title: "File names"; desc: "Leave empty to keep each file's own name."
            XField { id: ft; width: parent.width; label: "Pattern"; mono: true; text: Backend.cfg.file_template; error: page.pv.ok ? "" : page.pv.error
                onEdited: (t) => Backend.setCfg("file_template", t) }
            Flickable { width: parent.width; height: 36; contentWidth: prow.width; contentHeight: height; clip: true
                interactive: contentWidth > width; boundsBehavior: Flickable.StopAtBounds
                Row { id: prow; spacing: 8
                    Repeater { model: Backend.namePresets
                        delegate: Chip { text: modelData.label; filter: false; selected: Backend.cfg.file_template === modelData.tpl
                            onClicked: Backend.setCfg("file_template", modelData.tpl) } } } }
            Txt { text: "Tap to add a field"; font: Theme.labelS; color: Theme.fgSurfaceVariant }
            Flow { width: parent.width; spacing: 8
                Repeater { model: Backend.fields
                    delegate: Chip { text: modelData.label; icon: Icons.add; filter: false
                        onClicked: { ft.input.insert(ft.input.cursorPosition, "{" + modelData.key + "}"); Backend.setCfg("file_template", ft.input.text) } } } } }
    }

    ListGroup {
        SettingRow { title: "Rename album folders"; desc: "Only for albums you add as a folder. Other folders keep their names."
            trailing: XSwitch { checked: Backend.cfg.folder_rename; onToggled: (v) => Backend.setCfg("folder_rename", v) } }
        SettingRow { title: "Folder pattern"; visible: Backend.cfg.folder_rename
            desc: page.fv.ok ? "Looks like: " + page.fv.text : ""
            XField { width: parent.width; label: "Pattern"; mono: true; text: Backend.cfg.folder_template; error: page.fv.ok ? "" : page.fv.error
                onEdited: (t) => Backend.setCfg("folder_template", t) }
            Flickable { width: parent.width; height: 36; contentWidth: frow.width; contentHeight: height; clip: true
                interactive: contentWidth > width; boundsBehavior: Flickable.StopAtBounds
                Row { id: frow; spacing: 8
                    Repeater { model: Backend.folderPresets
                        delegate: Chip { text: modelData.label; filter: false; selected: Backend.cfg.folder_template === modelData.tpl
                            onClicked: Backend.setCfg("folder_template", modelData.tpl) } } } } }
    }

    Rectangle {
        width: parent.width; height: help.implicitHeight + 36; radius: Theme.rXL; color: Theme.surfaceContainer
        Column { id: help; x: 22; y: 18; width: parent.width - 44; spacing: 8
            Text { text: "Pattern cheat sheet"; font: Theme.titleS; color: Theme.fgSurface }
            Txt { width: parent.width; font: Theme.mono; color: Theme.fgSurfaceVariant; text: "{artist} - {title}      a field" }
            Txt { width: parent.width; font: Theme.mono; color: Theme.fgSurfaceVariant; text: "{track:02}               number with leading zero" }
            Txt { width: parent.width; font: Theme.mono; color: Theme.fgSurfaceVariant; text: "{albumartist|artist}    first one that isn't empty" }
            Txt { width: parent.width; font: Theme.mono; color: Theme.fgSurfaceVariant; text: "[ ({year})]              only shown when the year exists" }
            Txt { width: parent.width; font: Theme.mono; color: Theme.fgSurfaceVariant; text: "{title:upper}  :lower  :title   change case" } }
    }
}
