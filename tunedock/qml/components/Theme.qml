pragma Singleton
import QtQuick
import Td 1.0

QtObject {
    id: t
    readonly property bool reduce: Backend.cfg.reduce_motion === true
    readonly property bool dark: Backend.dark
    function dur(ms) { return reduce ? 0 : ms }
    // spatial spring (fast, a little bounce) - the Expressive feel
    readonly property real spring: 3.6
    readonly property real damping: 0.32

    // shape scale
    readonly property int rXS: 4
    readonly property int rS: 8
    readonly property int rM: 12
    readonly property int rL: 16
    readonly property int rXL: 28
    readonly property int rXXL: 40

    // type scale
    readonly property font display: Qt.font({pixelSize: 44, weight: Font.Bold})
    readonly property font headline: Qt.font({pixelSize: 30, weight: Font.DemiBold})
    readonly property font title: Qt.font({pixelSize: 20, weight: Font.DemiBold})
    readonly property font titleS: Qt.font({pixelSize: 16, weight: Font.DemiBold})
    readonly property font body: Qt.font({pixelSize: 15, weight: Font.Normal})
    readonly property font bodyS: Qt.font({pixelSize: 13, weight: Font.Normal})
    readonly property font label: Qt.font({pixelSize: 14, weight: Font.DemiBold})
    readonly property font labelS: Qt.font({pixelSize: 12, weight: Font.DemiBold})
    readonly property font mono: Qt.font({pixelSize: 14, family: "Cascadia Mono, Consolas, monospace"})

    // colour roles (components animate their own colour changes; Behaviors inside a singleton crash Qt)
    property color primary: Backend.scheme.primary
    property color fgPrimary: Backend.scheme.onPrimary
    property color primaryContainer: Backend.scheme.primaryContainer
    property color fgPrimaryContainer: Backend.scheme.onPrimaryContainer
    property color secondary: Backend.scheme.secondary
    property color fgSecondary: Backend.scheme.onSecondary
    property color secondaryContainer: Backend.scheme.secondaryContainer
    property color fgSecondaryContainer: Backend.scheme.onSecondaryContainer
    property color tertiary: Backend.scheme.tertiary
    property color fgTertiary: Backend.scheme.onTertiary
    property color tertiaryContainer: Backend.scheme.tertiaryContainer
    property color fgTertiaryContainer: Backend.scheme.onTertiaryContainer
    property color error: Backend.scheme.error
    property color fgError: Backend.scheme.onError
    property color errorContainer: Backend.scheme.errorContainer
    property color fgErrorContainer: Backend.scheme.onErrorContainer
    property color background: Backend.scheme.background
    property color fgBackground: Backend.scheme.onBackground
    property color surface: Backend.scheme.surface
    property color fgSurface: Backend.scheme.onSurface
    property color surfaceVariant: Backend.scheme.surfaceVariant
    property color fgSurfaceVariant: Backend.scheme.onSurfaceVariant
    property color outline: Backend.scheme.outline
    property color outlineVariant: Backend.scheme.outlineVariant
    property color surfaceDim: Backend.scheme.surfaceDim
    property color surfaceBright: Backend.scheme.surfaceBright
    property color surfaceContainerLowest: Backend.scheme.surfaceContainerLowest
    property color surfaceContainerLow: Backend.scheme.surfaceContainerLow
    property color surfaceContainer: Backend.scheme.surfaceContainer
    property color surfaceContainerHigh: Backend.scheme.surfaceContainerHigh
    property color surfaceContainerHighest: Backend.scheme.surfaceContainerHighest
    property color inverseSurface: Backend.scheme.inverseSurface
    property color inverseOnSurface: Backend.scheme.inverseOnSurface
    property color inversePrimary: Backend.scheme.inversePrimary
    property color scrim: Backend.scheme.scrim
    property color shadow: Backend.scheme.shadow
}
