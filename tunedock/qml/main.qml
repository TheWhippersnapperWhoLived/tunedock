import QtQuick
import QtQuick.Controls.Basic as C
import QtQuick.Window
import Td 1.0
import "components"
import "pages"

C.ApplicationWindow {
    id: win
    width: 1100; height: 760
    minimumWidth: 820; minimumHeight: 620
    title: "Tunedock"
    color: Theme.surface
    Behavior on color { ColorAnimation { duration: Theme.dur(380) } }
    visible: Backend.windowVisible
    property int page: 0
    onClosing: Backend.windowClosed()

    Connections {
        target: Backend
        function onRaiseWindow() { win.show(); win.raise(); win.requestActivate() }
        function onGoto(i) { win.page = i }
    }

    NavRail {
        id: rail
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        current: win.page
        items: [
            { icon: Icons.add, label: "Add" },
            { icon: Icons.library, label: "Library" },
            { icon: Icons.tune, label: "Convert" },
            { icon: Icons.edit, label: "Names" },
            { icon: Icons.settings, label: "System" },
            { icon: Icons.palette, label: "Style" }
        ]
        onPicked: (i) => win.page = i
    }

    Rectangle {
        id: surface
        anchors { left: rail.right; right: parent.right; top: parent.top; bottom: parent.bottom; margins: 12; leftMargin: 0 }
        radius: Theme.rXL + 8
        color: Theme.surfaceContainerLow
        Behavior on color { ColorAnimation { duration: Theme.dur(380) } }
        clip: true
        AddPage { anchors.fill: parent; active: win.page === 0; onRequestPage: (i) => win.page = i }
        LibraryPage { anchors.fill: parent; active: win.page === 1 }
        ConvertPage { anchors.fill: parent; active: win.page === 2 }
        NamesPage { anchors.fill: parent; active: win.page === 3 }
        SystemPage { anchors.fill: parent; active: win.page === 4 }
        StylePage { anchors.fill: parent; active: win.page === 5 }
    }
    Onboarding { anchors.fill: parent }
}
