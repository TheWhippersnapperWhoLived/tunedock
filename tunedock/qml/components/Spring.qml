import QtQuick

// A spatial spring: use as `Spring on x {}`. Respects the reduce-motion setting.
Behavior {
    id: b
    property real eps: 0.25
    enabled: !Theme.reduce
    animation: SpringAnimation { spring: Theme.spring; damping: Theme.damping; epsilon: b.eps }
}
