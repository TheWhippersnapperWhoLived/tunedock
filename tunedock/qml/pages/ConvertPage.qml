import QtQuick
import QtQuick.Dialogs
import Td 1.0
import "../components"

PageBase {
    id: page
    title: "Convert"
    subtitle: "What your music becomes on its way in."
    readonly property string fk: Backend.cfg.format
    readonly property var dl: Backend.ffmpegDl
    readonly property var fi: Backend.formats.find(f => f.key === fk)
    readonly property var order: Backend.formats.map(function (f) { return f.key })   // best first, defined once in the engine
    readonly property var hint: ({
        opus: "Best quality for the size. Plays on Android, VLC, foobar2000 and most modern players.",
        mp3: "Plays absolutely everywhere. Needs a higher bitrate than Opus for the same quality.",
        aac: "Great on Apple devices and most phones. Saved as .m4a.",
        vorbis: "Open and efficient, a little older than Opus. Saved as .ogg.",
        flac: "Lossless. Large files, perfect copies.",
        keep: "No conversion. Files are only renamed, tagged with cover art and filed."
    })

    Section { title: "Format & quality"
    ListGroup {
        SettingRow { title: "Format"; desc: page.hint[page.fk]
            SegGroup { model: Backend.formats.map(f => ({ label: f.label, enabled: Backend.status.fmtOk[f.key] !== false || !Backend.status.ffmpegOk }))
                currentIndex: page.order.indexOf(page.fk); onPicked: (i) => Backend.setCfg("format", page.order[i]) } }

        SettingRow { title: page.fk === "mp3" && Backend.cfg.mp3_vbr ? "Quality" : "Bitrate"; visible: page.fi.lossy
            desc: page.fk === "opus" ? "128 kbps is transparent for most people. 96 is great for a phone." : (page.fk === "mp3" ? "192 kbps is a good middle. 320 is the maximum." : "")
            trailing: Text { text: page.fk === "mp3" && Backend.cfg.mp3_vbr ? "V" + Backend.cfg.mp3_vq : Backend.cfg["br_" + page.fk] + " kbps"; font: Theme.title; color: Theme.primary }
            XSlider { id: brs; width: parent.width; visible: !(page.fk === "mp3" && Backend.cfg.mp3_vbr)
                from: page.fi.lo; to: page.fi.hi; stepSize: 1; value: Backend.cfg["br_" + page.fk] || 0; unit: " kbps"
                onMoved: Backend.setCfg("br_" + page.fk, value) }
            XSlider { width: parent.width; visible: page.fk === "mp3" && Backend.cfg.mp3_vbr; from: 0; to: 9; stepSize: 1; value: 9 - Backend.cfg.mp3_vq
                fmt: function (v) { return "V" + (9 - Math.round(v)) }; onMoved: Backend.setCfg("mp3_vq", 9 - Math.round(value)) }
            Flow { width: parent.width; spacing: 8; visible: !(page.fk === "mp3" && Backend.cfg.mp3_vbr)
                Repeater { model: page.fi.presets
                    delegate: Chip { text: modelData; filter: false; selected: Backend.cfg["br_" + page.fk] === modelData
                        onClicked: Backend.setCfg("br_" + page.fk, modelData) } } } }
        SettingRow { title: "Variable bitrate"; visible: page.fk === "opus" || page.fk === "mp3"
            desc: page.fk === "opus" ? "Recommended. Spends bits where the music needs them." : "Pick a quality level (V0 best) instead of a fixed bitrate."
            trailing: XSwitch { checked: page.fk === "opus" ? Backend.cfg.opus_vbr : Backend.cfg.mp3_vbr
                onToggled: (v) => Backend.setCfg(page.fk === "opus" ? "opus_vbr" : "mp3_vbr", v) } }
    } }

    Section { title: "Smart handling"
    ListGroup {
        SettingRow { title: "Don't convert what already fits"; visible: page.fk !== "keep"
            desc: "A file already in the target format at or below the bitrate is copied untouched, not re-encoded."
            trailing: XSwitch { checked: Backend.cfg.copy_if_fit; onToggled: (v) => Backend.setCfg("copy_if_fit", v) } }
        SettingRow { title: "Other lossy formats"; visible: page.fk !== "keep" && page.fk !== "flac"
            desc: "Converting MP3 to Opus loses a little more quality each time. You can leave those files as they are."
            SegGroup { model: ["Convert them", "Leave as they are"]; currentIndex: Backend.cfg.lossy_policy === "keep" ? 1 : 0
                onPicked: (i) => Backend.setCfg("lossy_policy", i === 1 ? "keep" : "convert") } }
    } }

    Section { title: "Audio"
    ListGroup {
        SettingRow { title: "Channels"; visible: page.fk !== "keep"
            SegGroup { model: ["Keep", "Mono", "Stereo"]; currentIndex: Backend.cfg.channels
                onPicked: (i) => Backend.setCfg("channels", i) } }
        SettingRow { title: "Sample rate"; visible: page.fk !== "keep" && page.fk !== "opus"; desc: "Opus always works at 48 kHz internally"
            SegGroup { model: ["Keep", "44.1 kHz", "48 kHz"]; currentIndex: [0, 44100, 48000].indexOf(Backend.cfg.sample_rate)
                onPicked: (i) => Backend.setCfg("sample_rate", [0, 44100, 48000][i]) } }
    } }

    Section { title: "Loudness"
    ListGroup {
        SettingRow { title: "ReplayGain"; visible: page.fk !== "keep"
            desc: page.fk === "opus" ? "Opus players read R128 gain tags, so those are written (EBU R128, -23 LUFS reference)." : "Writes REPLAYGAIN_* tags at the ReplayGain 2 reference of -18 LUFS. Measured on the final audio."
            SegGroup { model: ["Off", "Track", "Track + album"]; currentIndex: ["off", "track", "album"].indexOf(Backend.cfg.replaygain)
                onPicked: (i) => Backend.setCfg("replaygain", ["off", "track", "album"][i]) } }
    } }

    Section { title: "Artwork"
    ListGroup {
        SettingRow { title: "Keep cover art"; visible: page.fk !== "keep"
            desc: "Embedded art is carried across to every format."
            trailing: XSwitch { checked: Backend.cfg.embed_art; onToggled: (v) => Backend.setCfg("embed_art", v) } }
        SettingRow { title: "Use cover.jpg when a track has none"; visible: page.fk !== "keep" && Backend.cfg.embed_art
            desc: "Looks for cover, folder, front or album images in the same folder."
            trailing: XSwitch { checked: Backend.cfg.folder_art; onToggled: (v) => Backend.setCfg("folder_art", v) } }
        SettingRow { title: "Shrink large artwork"; visible: page.fk !== "keep" && Backend.cfg.embed_art
            desc: "Big covers are copied into every track, so 800 px is a good limit for phones."
            SegGroup { model: ["Original", "1200 px", "800 px", "500 px"]; currentIndex: [0, 1200, 800, 500].indexOf(Backend.cfg.art_max_px)
                onPicked: (i) => Backend.setCfg("art_max_px", [0, 1200, 800, 500][i]) } }
    } }

    Section { title: "Tools"
    ListGroup {
        SettingRow { title: "ffmpeg"
            desc: dl.state === "downloading" ? "Downloading ffmpeg, one time only\u2026 " + dl.msg
                  : (dl.state === "error" ? dl.msg
                  : (Backend.status.ffmpegReady ? (Backend.status.ffmpegNeeded ? Backend.status.ffmpeg : "Not needed while Format is set to Keep")
                  : Backend.status.ffmpegNote + ". " + (Backend.status.canDownload ? "Tunedock can download it for you." : "Install it (winget install Gyan.FFmpeg) or point to ffmpeg.exe below.")))
            trailing: Rectangle { width: 36; height: 36; radius: 18; color: Backend.status.ffmpegReady ? Theme.primaryContainer : Theme.errorContainer
                Icon { anchors.centerIn: parent; size: 22; path: Backend.status.ffmpegReady ? Icons.check : Icons.close
                    color: Backend.status.ffmpegReady ? Theme.fgPrimaryContainer : Theme.fgErrorContainer } }
            WavyProgress { width: parent.width; visible: dl.state === "downloading"; value: dl.pct }
            Row { spacing: 8; visible: !Backend.status.ffmpegReady && Backend.status.canDownload === true
                XButton { visible: dl.state !== "downloading"; text: dl.state === "error" ? "Try again" : "Download ffmpeg"; size: 1; icon: Icons.open; onClicked: Backend.downloadFfmpeg() }
                XButton { visible: dl.state === "downloading"; text: "Cancel"; size: 1; variant: "tonal"; onClicked: Backend.cancelDownload() } }
            XField { width: parent.width; label: "Path to ffmpeg (optional)"; text: Backend.cfg.ffmpeg_path; mono: true; trailingIcon: Icons.folder
                onEdited: (t) => Backend.setCfg("ffmpeg_path", t); onTrailingClicked: ffDlg.open() } }
        SettingRow { title: "Download ffmpeg automatically"; visible: Backend.status.canDownload === true
            desc: "Only when converting needs it and it can't be found. Never for Keep."
            trailing: XSwitch { checked: Backend.cfg.ffmpeg_auto; onToggled: (v) => Backend.setCfg("ffmpeg_auto", v) } }
        SettingRow { title: "Files at once"; desc: "Auto uses your CPU cores. Lower it on a slow disk or network drive."
            SegGroup { model: ["Auto", "1", "2", "4", "8"]; currentIndex: [0, 1, 2, 4, 8].indexOf(Backend.cfg.threads) < 0 ? 0 : [0, 1, 2, 4, 8].indexOf(Backend.cfg.threads)
                onPicked: (i) => Backend.setCfg("threads", [0, 1, 2, 4, 8][i]) } }
    } }
    FileDialog { id: ffDlg; title: "Find ffmpeg"; nameFilters: ["ffmpeg (ffmpeg*)", "All files (*)"]
        onAccepted: Backend.setCfg("ffmpeg_path", String(selectedFile)) }
}
