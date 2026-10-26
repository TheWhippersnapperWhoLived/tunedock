import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property string path
    property color color: Theme.fgSurface
    property real size: 24
    width: size; height: size
    Shape {
        width: 24; height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: root.color
            strokeColor: "transparent"
            fillRule: ShapePath.WindingFill
            PathSvg { path: root.path }
        }
    }
}
