import pyqtgraph as pg
import numpy as np
from pyqtgraph import colormap
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import sys

class ColorHandle(pg.GraphicsObject):
    sigMoved = QtCore.Signal()
    sigColorChanged = QtCore.Signal()

    def __init__(self, pos=0.5, color=(255, 0, 0), horizontal=True):
        super().__init__()
        self.color_pos = float(pos)
        self.color = QtGui.QColor(*color)
        self.horizontal = horizontal
        self.size = 10

        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)
        self.setZValue(2000)

    def boundingRect(self):
        s = self.size
        return QtCore.QRectF(-s / 2, -s, s, s)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        s = self.size
        h = s * 0.45

        if self.horizontal:
            polygon = QtGui.QPolygonF([
                QtCore.QPointF(0, 0),
                QtCore.QPointF(-s / 2, -h),
                QtCore.QPointF(s / 2, -h),
            ])
        else:
            polygon = QtGui.QPolygonF([
                QtCore.QPointF(0, 0),
                QtCore.QPointF(h, -s / 2),
                QtCore.QPointF(h, s / 2),
            ])

        painter.setPen(pg.mkPen("k", width=2))
        painter.setBrush(pg.mkBrush(self.color))
        painter.drawPolygon(polygon)

    def mouseMoveEvent(self, ev):
        super().mouseMoveEvent(ev)

        parent = self.parentItem()
        if parent is None:
            return

        p = self.pos()

        if self.horizontal:
            x = float(np.clip(p.x(), 0, 255))
            self.setPos(x, -0.08)
            self.color_pos = x / 255.0
        else:
            y = float(np.clip(p.y(), 0, 255))
            self.setPos(-0.08, y)
            self.color_pos = y / 255.0

        self.sigMoved.emit()
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        color = QtWidgets.QColorDialog.getColor(self.color)

        if color.isValid():
            self.color = color
            self.update()
            self.sigColorChanged.emit()

        ev.accept()

class EditableColorBarItem(pg.ColorBarItem):
    sigColorHandlesChanged = QtCore.Signal()

    def __init__(self, *args, editable_cmap=True, **kwargs):
        self.editable_cmap = editable_cmap
        self.color_handles = []

        super().__init__(*args, **kwargs)

        if self.editable_cmap:
            self._initColorHandles()

    def setColorMap(self, colorMap):
        super().setColorMap(colorMap)

        if getattr(self, "editable_cmap", False):
            self._initColorHandles()

    def _initColorHandles(self):
        if self._colorMap is None:
            self._colorMap = colormap.get("viridis")

        self._clearColorHandles()

        n_handles = 7

        idx = np.linspace(
            0,
            len(self._colorMap.pos) - 1,
            n_handles,
            dtype=int
        )

        pos = np.asarray(self._colorMap.pos)[idx]
        colors = np.array(np.asarray(self._colorMap.color)[idx] * 255, dtype=np.ubyte)

        if pos.max() > pos.min():
            pos = (pos - pos.min()) / (pos.max() - pos.min())
        else:
            pos = np.linspace(0.0, 1.0, len(colors))

        for p, c in zip(pos, colors):
            self.addColorHandle(float(p), tuple(c[:4]))

    def _clearColorHandles(self):
        for handle in self.color_handles:
            self.getViewBox().removeItem(handle)

        self.color_handles.clear()

    def addColorHandle(self, pos=0.5, color=(255, 0, 0, 255)):
        handle = ColorHandle(
            pos=pos,
            color=color,
            horizontal=self.horizontal,
        )

        handle.sigMoved.connect(self._colorHandleChanged)
        handle.sigColorChanged.connect(self._colorHandleChanged)

        self.color_handles.append(handle)
        self.getViewBox().addItem(handle)
        self._setColorHandlePos(handle)

        return handle

    def setColorHandlePosition(self, handle, pos):
        if handle not in self.color_handles:
            return

        handle.color_pos = float(np.clip(pos, 0.0, 1.0))
        self._setColorHandlePos(handle)
        self._colorHandleChanged()

    def _setColorHandlePos(self, handle):
        p = float(np.clip(handle.color_pos, 0.0, 1.0))

        if self.horizontal:
            handle.setPos(p * 255.0, -0.08)
        else:
            handle.setPos(-0.08, p * 255.0)

    def _colorHandleChanged(self):
        handles = sorted(self.color_handles, key=lambda h: h.color_pos)

        pos = np.array(
            [np.clip(h.color_pos, 0.0, 1.0) for h in handles],
            dtype=float,
        )

        colors = np.array(
            [
                [
                    h.color.red(),
                    h.color.green(),
                    h.color.blue(),
                    h.color.alpha(),
                ]
                for h in handles
            ],
            dtype=np.ubyte,
        )

        # avoid duplicated stop positions
        for i in range(1, len(pos)):
            if pos[i] <= pos[i - 1]:
                pos[i] = min(1.0, pos[i - 1] + 1e-6)

        self._colorMap = colormap.ColorMap(pos, colors)
        self._update_items(update_cmap=True)
        self.sigColorHandlesChanged.emit()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Editable ColorBarItem example")
        self.resize(900, 700)

        self.graphics = pg.GraphicsLayoutWidget()
        self.setCentralWidget(self.graphics)

        self.plot = self.graphics.addPlot(row=0, col=0)
        self.plot.setAspectLocked(True)
        self.plot.invertY(False)

        data = np.random.normal(size=(200, 200))
        data += np.hypot(*np.indices(data.shape)) / 80.0

        self.image = pg.ImageItem(data)
        self.plot.addItem(self.image)
        self.plot.autoRange()

        levels = (float(np.nanmin(data)), float(np.nanmax(data)))

        self.colorbar = EditableColorBarItem(
            values=levels,
            colorMap="viridis",
            width=30,
            orientation="vertical",
            interactive=True,
            label="Intensity",
        )

        self.colorbar.setImageItem(self.image)
        self.graphics.addItem(self.colorbar, row=0, col=1)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())
