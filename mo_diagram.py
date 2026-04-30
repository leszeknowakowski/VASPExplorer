from dataclasses import dataclass
from typing import Dict, List, Tuple
import re
import sys
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QCloseEvent
import numpy as np
import os
import pyqtgraph as pg
from cube_reader import CubeManager
from pyvistaqt import QtInteractor


@dataclass
class SpinData:
    molecular_orbitals: List[str]
    atomic_orbital_labels: List[str]
    atomic_groups: Dict[str, List[str]]
    ao_energies_by_group: List[np.ndarray]
    mo_energies: np.ndarray
    coefficient_matrix: np.ndarray


class ParsedDiagram:
    def __init__(self, alpha: SpinData, beta: SpinData):
        self.alpha = alpha
        self.beta = beta


class LobsterModel:
    """Handles file parsing and data preparation."""

    @staticmethod
    def _parse_token(token: str):
        token = token.strip()
        if token == "":
            return ""
        try:
            return float(token.replace("D", "E"))
        except ValueError:
            return token

    @classmethod
    def read_table(cls, path: str):
        rows = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                parts = re.split(r"\s+", raw)
                rows.append([cls._parse_token(p) for p in parts])
        return rows

    @staticmethod
    def _split_spin(rows):
        molecular_orbitals = [str(x) for x in rows[1]]
        mo_energies = np.array(rows[2][2:], dtype=float)

        atomic_rows = rows[3:]
        labels = [str(r[0]) for r in atomic_rows]
        ao_energies = np.array([r[1] for r in atomic_rows], dtype=float)
        coeff = np.array([r[2:] for r in atomic_rows], dtype=float)

        group_map = {}
        group_energies = {}

        for lbl, e in zip(labels, ao_energies):
            atom = lbl.split("_", 1)[0]
            group_map.setdefault(atom, []).append(lbl)
            group_energies.setdefault(atom, []).append(e)

        return SpinData(
            molecular_orbitals,
            labels,
            group_map,
            [np.array(v) for v in group_energies.values()],
            mo_energies,
            coeff,
        )

    @classmethod
    def load(cls, path: str) -> ParsedDiagram:
        rows = cls.read_table(path)
        half = len(rows) // 2

        alpha = cls._split_spin(rows[:half])
        beta = cls._split_spin(rows[half:])

        return ParsedDiagram(alpha, beta)


class MODiagramViewModel(QtCore.QObject):
    """Application logic + state."""

    data_changed = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.diagram = None
        self.spin = "alpha"
        self.threshold = 0.3

    def load_file(self, path: str):
        from pathlib import Path
        if not Path(path).exists():
            return
        self.diagram = LobsterModel.load(path)
        self.data_changed.emit()
        self.cube_manager = CubeManager()
        self.cube_manager.load_directory(os.path.dirname(path))
        self.cube_manager.render_all_screenshots()
        self.files = os.listdir(os.path.dirname(path))

    def set_spin(self, spin: str):
        self.spin = spin
        self.data_changed.emit()

    def set_threshold(self, value: int):
        self.threshold = value / 100.0
        self.data_changed.emit()

    def active(self):
        if not self.diagram:
            return None
        return self.diagram.alpha if self.spin == "alpha" else self.diagram.beta

    def get_cube_for_mo(self, label):
        sd = self.active()

        insertion = '1' if self.spin == "alpha" else '2'

        lst = label.split("_")
        lst.insert(2, insertion)
        cube_name = "_".join(lst)

        for file in self.files:
            if cube_name in file:
                return file

        return None

    @staticmethod
    def spread_positions(energies, x_center, tol=2):
        rounded = np.round(energies / tol) * tol
        out = []
        for r in np.unique(rounded):
            idx = np.where(rounded == r)[0]
            offsets = [0.0] if len(idx) == 1 else np.linspace(-0.5, 0.5, len(idx))
            for i, dx in zip(idx, offsets):
                out.append((energies[i], x_center + dx))
        return sorted(out, key=lambda t: t[0])


class MODiagramView(QtWidgets.QMainWindow):
    def __init__(self, vm: MODiagramViewModel):
        super().__init__()
        self.vm = vm
        self.setWindowTitle("MO Diagram (MVVM)")
        self.resize(1200, 800)

        self.plot = pg.PlotWidget(background="w")
        self.setCentralWidget(self.plot)

        self.proxy = pg.SignalProxy(
            self.plot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.on_mouse_moved
        )

        self.hover_window = QtWidgets.QDialog()
        self.hover_window.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )

        layout = QtWidgets.QVBoxLayout(self.hover_window)
        self.hover_img = pg.ImageView()
        self.hover_img.ui.histogram.hide()
        self.hover_img.ui.roiBtn.hide()
        self.hover_img.ui.menuBtn.hide()
        layout.addWidget(self.hover_img)
        self.hover_window.resize(500, 500)

        self.plot.scene().sigMouseClicked.connect(self.on_mouse_clicked)

        self._build_toolbar()

        self.vm.data_changed.connect(self.render)

    def _build_toolbar(self):
        tb = QtWidgets.QToolBar()
        self.addToolBar(tb)

        btn = QtWidgets.QPushButton("Open")
        btn.clicked.connect(self.open_file)
        tb.addWidget(btn)

        self.spin = QtWidgets.QComboBox()
        self.spin.addItems(["alpha", "beta"])
        self.spin.currentTextChanged.connect(self.vm.set_spin)
        tb.addWidget(self.spin)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(30)
        self.slider.valueChanged.connect(self.vm.set_threshold)
        tb.addWidget(self.slider)

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open", os.getcwd()
        )
        if path:
            self.vm.load_file(path)

    def render(self):
        self.mo_items = []
        self.ao_items = []
        self.conn_items = []
        self.mo_labels = []
        self.ao_labels = []
        self.plot.clear()
        sd = self.vm.active()
        if not sd:
            return

        group_names = list(sd.atomic_groups.keys())
        x_positions = [(i + 1) * 3 + 5 for i in range(len(group_names) + 1)]

        mo_x = x_positions.pop(len(group_names) // 2)
        ao_x = x_positions

        ao_positions = []

        for i, energies in enumerate(sd.ao_energies_by_group):
            pts = self.vm.spread_positions(energies, ao_x[i])
            labels = sd.atomic_groups[group_names[i]]

            for k, (e, x) in enumerate(pts):
                item = self.plot.plot([x - 0.15, x + 0.15], [e, e], pen="k")
                item.ao_index = len(self.ao_items)
                self.ao_items.append(item)

                label = pg.TextItem(labels[k], anchor=(0.5, 0))
                label.setPos(x, e - 0.5)
                label.ao_index = len(self.ao_labels)
                self.ao_labels.append(label)
                self.plot.addItem(label)

            ao_positions.extend(pts)

        mo_positions = self.vm.spread_positions(sd.mo_energies, mo_x)
        for j, (e, x) in enumerate(mo_positions):
            item = self.plot.plot([x - 0.15, x + 0.15], [e, e], pen="b")
            item.mo_index = j
            self.mo_items.append(item)

            label = pg.TextItem(sd.molecular_orbitals[j], anchor=(0.5, 0))
            label.setPos(x, e - 0.5)
            label.mo_index = j
            self.mo_labels.append(label)
            self.plot.addItem(label)

        for i in range(sd.coefficient_matrix.shape[0]):
            for j in range(sd.coefficient_matrix.shape[1]):
                val = sd.coefficient_matrix[i, j]
                if abs(val) < self.vm.threshold:
                    continue

                item = self.plot.plot(
                    [ao_positions[i][1], mo_positions[j][1]],
                    [ao_positions[i][0], mo_positions[j][0]],
                    pen=pg.mkPen(width=1)
                )
                item.ao_index = i
                item.mo_index = j
                self.conn_items.append(item)

    def on_mouse_moved(self, evt):
        pos = evt[0]
        vb = self.plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)

        x = mouse_point.x()
        y = mouse_point.y()

        closest_mo = None
        min_dist = 0.3  # sensitivity

        # find closest MO
        for j, item in enumerate(self.mo_items):
            data = item.getData()
            y_mo = data[1][0]
            x_mo = np.mean(data[0])

            dist = abs(y - y_mo) + abs(x - x_mo)
            if dist < min_dist:
                closest_mo = j
                min_dist = dist

        self.highlight_mo(closest_mo)

    def highlight_mo(self, mo_index):
        # reset visuals (unchanged)
        for item in self.mo_items:
            item.setPen("b")
        for item in self.ao_items:
            item.setPen("k")
        for item in self.conn_items:
            item.setPen(pg.mkPen(width=1))

        for label in self.mo_labels:
            label.setColor("k")
        for label in self.ao_labels:
            label.setColor("k")

        # -------------------------
        # hide window if nothing selected
        # -------------------------
        if mo_index is None:
            self.hover_window.hide()
            return

        # highlight MO
        self.mo_items[mo_index].setPen(pg.mkPen("r", width=2))
        self.mo_labels[mo_index].setColor("r")

        for item in self.conn_items:
            if item.mo_index == mo_index:
                item.setPen(pg.mkPen("r", width=1.5))
                ao_i = item.ao_index
                self.ao_items[ao_i].setPen(pg.mkPen("r", width=2))
                self.ao_labels[ao_i].setColor("r")

        # -------------------------
        # show screenshot
        # -------------------------
        sd = self.vm.active()
        mo_label = sd.molecular_orbitals[mo_index]
        cube_name = self.vm.get_cube_for_mo(mo_label)

        if cube_name:
            shot = self.vm.cube_manager.screenshots.get(cube_name)
            if shot is not None:
                self.hover_img.setImage(shot, axes={'x': 1, 'y': 0, 'c': 2})

                # position near cursor / window
                cursor_pos = QtGui.QCursor.pos()
                self.hover_window.move(cursor_pos + QtCore.QPoint(20, 20))
                self.hover_window.show()

    def on_mouse_clicked(self, evt):
        self.hover_window.hide()
        pos = evt.scenePos()
        vb = self.plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)

        x = mouse_point.x()
        y = mouse_point.y()

        closest_mo = None
        min_dist = 0.3

        for j, item in enumerate(self.mo_items):
            data = item.getData()
            y_mo = data[1][0]
            x_mo = np.mean(data[0])

            dist = abs(y - y_mo) + abs(x - x_mo)
            if dist < min_dist:
                closest_mo = j
                min_dist = dist

        if closest_mo is not None:
            self.show_mo_popup(closest_mo)

    def show_mo_popup(self, mo_index):
        sd = self.vm.active()
        coeffs = sd.coefficient_matrix[:, mo_index]
        mo_label = sd.molecular_orbitals[mo_index]

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"MO {mo_label}")
        dialog.resize(900, 600)

        layout = QtWidgets.QHBoxLayout(dialog)

        # -------------------------
        # LEFT: TABLE
        # -------------------------
        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Atomic Orbital", "Coefficient"])
        table.setRowCount(len(coeffs))

        for i, val in enumerate(coeffs):
            ao_label = sd.atomic_orbital_labels[i]
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(ao_label))

            item = QtWidgets.QTableWidgetItem(f"{val:.4f}")
            if abs(val) > 0.3:
                item.setForeground(QtCore.Qt.red)
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            table.setItem(i, 1, item)

        table.resizeColumnsToContents()
        layout.addWidget(table, 1)

        # -------------------------
        # RIGHT: 3D VIEW
        # -------------------------
        pv_widget = QtInteractor(dialog)
        layout.addWidget(pv_widget, 2)

        # load cube
        cube_name = self.vm.get_cube_for_mo(mo_label)

        if cube_name:
            cube = self.vm.cube_manager.cubes[cube_name]
            self.vm.cube_manager.add_to_plotter(cube, pv_widget)

            pv_widget.reset_camera()

        dialog.exec_()

        def cleanup():
            try:
                self.pv_widget.close()
                self.pv_widget.interactor.Finalize()
                self.pv_widget.deleteLater()
            except Exception:
                pass

        dialog.finished.connect(cleanup)




def main():
    app = QtWidgets.QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)

    vm = MODiagramViewModel()

    view = MODiagramView(vm)
    # pth = r"D:\syncme\modelowanie DFT\co3o4_new_new\9.deep_o2_reduction\GOOD\1.spin_up\HSE\1.gas_to_metaloxo\2.1_almost_desorbed_small\1.mofe_o2\O2_1.MO_Diagram.lobster"
    # view.vm.load_file(pth)
    view.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()