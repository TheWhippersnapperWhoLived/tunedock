import QtQuick
import Td 1.0
import "../components"

PageBase {
    id: page
    title: "Style"
    subtitle: "Colours follow one seed colour, the way Material You does."
    readonly property bool hexOk: /^#[0-9a-fA-F]{6}$/.test(hexField.input.text)

    ListGroup {
        SettingRow { title: "Theme"
            SegGroup { model: ["System", "Light", "Dark"]; currentIndex: ["system", "light", "dark"].indexOf(Backend.cfg.theme_mode)
                onPicked: (i) => Backend.setCfg("theme_mode", ["system", "light", "dark"][i]) } }
        SettingRow { title: "Seed colour"; desc: "The last swatch uses your Windows accent colour."
            Flow { width: parent.width; spacing: 12
                Repeater { model: Backend.swatches.concat(["system"])
                    delegate: Item { width: 52; height: 52
                        readonly property bool sel: Backend.cfg.seed.toLowerCase() === String(modelData).toLowerCase()
                        readonly property color sw: modelData === "system" ? Backend.systemAccent() : modelData
                        Rectangle { anchors.fill: parent; radius: sel ? 16 : 26; color: parent.sw
                            Spring on radius { eps: 0.3 }
                            Icon { anchors.centerIn: parent; path: modelData === "system" && !parent.parent.sel ? Icons.settings : Icons.check; size: 24; color: "white"
                                opacity: parent.parent.sel || modelData === "system" ? 1 : 0 } }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Backend.setCfg("seed", modelData) } } } }
            XField { id: hexField; width: 240; label: "Custom colour (hex)"; mono: true; text: Backend.cfg.seed === "system" ? Backend.systemAccent() : Backend.cfg.seed
                error: text.length > 0 && !page.hexOk ? "Use six digits, like #6750A4" : ""
                onEdited: (t) => { if (/^#[0-9a-fA-F]{6}$/.test(t)) Backend.setCfg("seed", t) } } }
        SettingRow { title: "Reduce motion"; desc: "Turns off springs, morphing and the wavy progress animation."
            trailing: XSwitch { checked: Backend.cfg.reduce_motion; onToggled: (v) => Backend.setCfg("reduce_motion", v) } }
    }

    Rectangle {
        width: parent.width; height: 210; radius: Theme.rXL; color: Theme.surfaceContainer
        Text { x: 22; y: 18; text: "Preview"; font: Theme.labelS; color: Theme.fgSurfaceVariant }
        Row { x: 22; y: 48; spacing: 12
            XButton { text: "Filled"; size: 2 }
            XButton { text: "Tonal"; size: 2; variant: "tonal" }
            XButton { text: "Outlined"; size: 2; variant: "outlined" }
            XSwitch { anchors.verticalCenter: parent.verticalCenter; checked: true } }
        Row { x: 22; y: 120; spacing: 20
            Blob { size: 64; color: Theme.primaryContainer; lobes: 9; amp: 0.09 }
            Blob { size: 64; color: Theme.secondaryContainer; lobes: 6; amp: 0.12 }
            Blob { size: 64; color: Theme.tertiaryContainer; lobes: 12; amp: 0.07 }
            WavyProgress { width: 220; anchors.verticalCenter: parent.verticalCenter; value: 0.62 } }
    }
}
