from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple
import re
import sys
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QCloseEvent
import numpy as np
import os
import pyqtgraph as pg
from lobster.cube_reader import CubeManager
from structure_plot import QtInteractor

ORB_LINE_WIDTH = 3.5

@dataclass
class SpinData:
    molecular_orbitals: List[str]
    atomic_orbital_labels: List[str]
    atomic_groups: Dict[str, List[str]]
    ao_energies_by_group: List[np.ndarray]
    mo_energies: np.ndarray
    coefficient_matrix: np.ndarray


@dataclass
class OrbitalMatch:
    source_file_index: int
    target_file_index: int
    source_mo_index: int
    target_mo_index: int
    source_mo_label: str
    target_mo_label: str
    score: float
    compared_coefficients: int
    matching_coefficients: int


@dataclass
class OrbitalTrackStep:
    file_index: int
    file_path: str
    mo_index: int
    mo_label: str
    mo_energy: float


@dataclass
class OrbitalTrack:
    track_id: int
    steps: List[OrbitalTrackStep] = field(default_factory=list)


@dataclass
class TrackedDiagramSequence:
    paths: List[str]
    diagrams: List["ParsedDiagram"]
    spin: str
    tolerance: float
    min_score: float
    coefficient_cutoff: float
    matches: List[List[OrbitalMatch]]
    tracks: List[OrbitalTrack]


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
        ao_labels = [str(r[0]) for r in atomic_rows]
        ao_energies = np.array([r[1] for r in atomic_rows], dtype=float)
        coeff = np.array([r[2:] for r in atomic_rows], dtype=float)

        group_map = {}
        group_energies = {}

        for lbl, e in zip(ao_labels, ao_energies):
            atom = lbl.split("_", 1)[0]
            group_map.setdefault(atom, []).append(lbl)
            group_energies.setdefault(atom, []).append(e)

        return SpinData(
            molecular_orbitals,
            ao_labels,
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

    @classmethod
    def load_many(cls, paths: Sequence[str]) -> List[ParsedDiagram]:
        return [cls.load(path) for path in paths]

    @staticmethod
    def spin_data(diagram: ParsedDiagram, spin: str) -> SpinData:
        if spin == "alpha":
            return diagram.alpha
        if spin == "beta":
            return diagram.beta
        raise ValueError("spin must be 'alpha' or 'beta'")

    @staticmethod
    def _aligned_coefficients(
            left: SpinData,
            left_mo_index: int,
            right: SpinData,
            right_mo_index: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        right_label_to_index = {
            label: i for i, label in enumerate(right.atomic_orbital_labels)
        }

        left_indices = []
        right_indices = []
        for left_i, label in enumerate(left.atomic_orbital_labels):
            right_i = right_label_to_index.get(label)
            if right_i is not None:
                left_indices.append(left_i)
                right_indices.append(right_i)

        if not left_indices:
            raise ValueError("No common atomic orbital labels found between diagrams")

        return (
            left.coefficient_matrix[left_indices, left_mo_index],
            right.coefficient_matrix[right_indices, right_mo_index],
        )

    @classmethod
    def coefficient_similarity(
            cls,
            left: SpinData,
            left_mo_index: int,
            right: SpinData,
            right_mo_index: int,
            tolerance: float = 0.20,
            coefficient_cutoff: float = 0.0,
            absolute_tolerance: float = 1e-12,
    ) -> Tuple[float, int, int]:
        left_coeff, right_coeff = cls._aligned_coefficients(
            left, left_mo_index, right, right_mo_index
        )

        left_abs = np.abs(left_coeff)
        right_abs = np.abs(right_coeff)

        if coefficient_cutoff > 0:
            mask = (left_abs >= coefficient_cutoff) | (right_abs >= coefficient_cutoff)
            left_abs = left_abs[mask]
            right_abs = right_abs[mask]

        compared = len(left_abs)
        if compared == 0:
            return 0.0, 0, 0

        close = np.isclose(
            left_abs,
            right_abs,
            rtol=tolerance,
            atol=absolute_tolerance,
        )
        matching = int(np.count_nonzero(close))
        return matching / compared, compared, matching

    @classmethod
    def match_spin_data(
            cls,
            left: SpinData,
            right: SpinData,
            source_file_index: int = 0,
            target_file_index: int = 1,
            tolerance: float = 0.20,
            min_score: float = 0.80,
            coefficient_cutoff: float = 0.0,
    ) -> List[OrbitalMatch]:
        candidates = []
        for left_mo_index, left_label in enumerate(left.molecular_orbitals):
            for right_mo_index, right_label in enumerate(right.molecular_orbitals):
                score, compared, matching = cls.coefficient_similarity(
                    left,
                    left_mo_index,
                    right,
                    right_mo_index,
                    tolerance=tolerance,
                    coefficient_cutoff=coefficient_cutoff,
                )
                if score >= min_score:
                    candidates.append(OrbitalMatch(
                        source_file_index=source_file_index,
                        target_file_index=target_file_index,
                        source_mo_index=left_mo_index,
                        target_mo_index=right_mo_index,
                        source_mo_label=left_label,
                        target_mo_label=right_label,
                        score=score,
                        compared_coefficients=compared,
                        matching_coefficients=matching,
                    ))

        candidates.sort(key=lambda match: match.score, reverse=True)
        used_left = set()
        used_right = set()
        matches = []
        for match in candidates:
            if match.source_mo_index in used_left or match.target_mo_index in used_right:
                continue
            used_left.add(match.source_mo_index)
            used_right.add(match.target_mo_index)
            matches.append(match)

        matches.sort(key=lambda match: match.source_mo_index)
        return matches

    @classmethod
    def track_orbitals(
            cls,
            paths: Sequence[str],
            spin: str = "alpha",
            tolerance: float = 0.20,
            min_score: float = 0.80,
            coefficient_cutoff: float = 0.0,
    ) -> TrackedDiagramSequence:
        paths = list(paths)
        diagrams = cls.load_many(paths)
        spin_data_by_file = [cls.spin_data(diagram, spin) for diagram in diagrams]

        matches_by_pair = []
        for file_i in range(len(spin_data_by_file) - 1):
            matches_by_pair.append(cls.match_spin_data(
                spin_data_by_file[file_i],
                spin_data_by_file[file_i + 1],
                source_file_index=file_i,
                target_file_index=file_i + 1,
                tolerance=tolerance,
                min_score=min_score,
                coefficient_cutoff=coefficient_cutoff,
            ))

        tracks = cls._build_tracks(paths, spin_data_by_file, matches_by_pair)
        return TrackedDiagramSequence(
            paths=paths,
            diagrams=diagrams,
            spin=spin,
            tolerance=tolerance,
            min_score=min_score,
            coefficient_cutoff=coefficient_cutoff,
            matches=matches_by_pair,
            tracks=tracks,
        )

    @staticmethod
    def _track_step(
            paths: Sequence[str],
            spin_data_by_file: Sequence[SpinData],
            file_index: int,
            mo_index: int,
    ) -> OrbitalTrackStep:
        spin_data = spin_data_by_file[file_index]
        return OrbitalTrackStep(
            file_index=file_index,
            file_path=paths[file_index],
            mo_index=mo_index,
            mo_label=spin_data.molecular_orbitals[mo_index],
            mo_energy=float(spin_data.mo_energies[mo_index]),
        )

    @classmethod
    def _build_tracks(
            cls,
            paths: Sequence[str],
            spin_data_by_file: Sequence[SpinData],
            matches_by_pair: Sequence[Sequence[OrbitalMatch]],
    ) -> List[OrbitalTrack]:
        active_tracks: Dict[int, OrbitalTrack] = {}
        tracks: List[OrbitalTrack] = []
        next_track_id = 1

        if not spin_data_by_file:
            return tracks

        for mo_index in range(len(spin_data_by_file[0].molecular_orbitals)):
            track = OrbitalTrack(track_id=next_track_id)
            next_track_id += 1
            track.steps.append(cls._track_step(paths, spin_data_by_file, 0, mo_index))
            tracks.append(track)
            active_tracks[mo_index] = track

        for pair_i, matches in enumerate(matches_by_pair):
            next_active_tracks = {}
            matched_targets = set()

            for match in matches:
                track = active_tracks.get(match.source_mo_index)
                if track is None:
                    track = OrbitalTrack(track_id=next_track_id)
                    next_track_id += 1
                    track.steps.append(cls._track_step(
                        paths,
                        spin_data_by_file,
                        pair_i,
                        match.source_mo_index,
                    ))
                    tracks.append(track)

                track.steps.append(cls._track_step(
                    paths,
                    spin_data_by_file,
                    pair_i + 1,
                    match.target_mo_index,
                ))
                next_active_tracks[match.target_mo_index] = track
                matched_targets.add(match.target_mo_index)

            for mo_index in range(len(spin_data_by_file[pair_i + 1].molecular_orbitals)):
                if mo_index in matched_targets:
                    continue
                track = OrbitalTrack(track_id=next_track_id)
                next_track_id += 1
                track.steps.append(cls._track_step(
                    paths,
                    spin_data_by_file,
                    pair_i + 1,
                    mo_index,
                ))
                tracks.append(track)
                next_active_tracks[mo_index] = track

            active_tracks = next_active_tracks

        return tracks


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
        basename = os.path.basename(path).split("_")[0]
        self.cube_manager.load_directory(os.path.dirname(path), basename)
        self.cube_manager.render_all_screenshots()
        self.save_mo_images()
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
        spin_data = self.active()

        insertion = '1' if self.spin == "alpha" else '2'

        lst = label.split("_")
        lst.insert(2, insertion)
        cube_name = "_".join(lst)

        for file in self.files:
            if cube_name in file:
                if file.endswith(".cube"):
                    return file

        return None

    @staticmethod
    def spread_positions(energies, x_center, tol=2):
        rounded = np.round(energies / tol) * tol
        out = [None] * len(energies)
        for r in np.unique(rounded):
            idx = np.where(rounded == r)[0]
            offsets = [0.0] if len(idx) == 1 else np.linspace(-0.5, 0.5, len(idx))
            for i, dx in zip(idx, offsets):
                out[i] = (energies[i], x_center + dx)

        return out

    def save_mo_images(self):
        qm = QtWidgets.QMessageBox()
        ret = qm.question(None, '', "Do You want to save MO images?", qm.Yes | qm.No)
        if ret == qm.Yes:
            from pyqtgraph.exporters import ImageExporter
            for mo_name, mo_image in self.cube_manager.screenshots.items():
                imv = pg.ImageView()
                imv.setImage(mo_image)
                imv.getView().addItem(pg.LabelItem(mo_name, color="b"))
                ex = ImageExporter(imv.scene)
                ex.parameters()['width'] = 5000
                ex.export(mo_name+".jpg")


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

        self.vm.data_changed.connect(self.first_render)

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

    def first_render(self):
        self.mo_items = []
        self.ao_items = []
        self.conn_items = []
        self.mo_labels = []
        self.ao_labels = []
        self.plot.clear()
        spin_data = self.vm.active()
        if not spin_data:
            return

        group_names = list(spin_data.atomic_groups.keys())
        x_positions = [(i + 1) * 3 + 5 for i in range(len(group_names) + 1)]

        mo_x = x_positions.pop(len(group_names) // 2)
        ao_x = x_positions

        ao_positions = []

        for i, energies in enumerate(spin_data.ao_energies_by_group):
            pts = self.vm.spread_positions(energies, ao_x[i])
            labels = spin_data.atomic_groups[group_names[i]]

            for k, (e, x) in enumerate(pts):
                item = self.plot.plot([x - 0.15, x + 0.15], [e, e], pen="k", width=ORB_LINE_WIDTH)
                item.ao_index = len(self.ao_items)
                self.ao_items.append(item)

                label = pg.TextItem(labels[k], anchor=(0.5, 0))
                label.setPos(x, e - 0.1)
                label.ao_index = len(self.ao_labels)
                self.ao_labels.append(label)
                self.plot.addItem(label)

            ao_positions.extend(pts)

        mo_positions = self.vm.spread_positions(spin_data.mo_energies, mo_x)
        for j, (e, x) in enumerate(mo_positions):
            item = self.plot.plot([x - 0.15, x + 0.15], [e, e], pen="b", width=ORB_LINE_WIDTH)
            item.mo_index = j
            self.mo_items.append(item)

            label = pg.TextItem(spin_data.molecular_orbitals[j], anchor=(0.5, 0))
            label.setPos(x, e - 0.1)
            label.mo_index = j
            self.mo_labels.append(label)
            self.plot.addItem(label)

        for i in range(spin_data.coefficient_matrix.shape[0]):
            for j in range(spin_data.coefficient_matrix.shape[1]):
                val = spin_data.coefficient_matrix[i, j]
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

        closest_mo = None
        min_dist = 3  # pixels

        for j, item in enumerate(self.mo_items):
            data = item.getData()
            x_vals = data[0]
            y_val = data[1][0]

            x_min = np.min(x_vals)
            x_max = np.max(x_vals)

            # map segment endpoints to scene (pixel space)
            p1 = vb.mapViewToScene(QtCore.QPointF(x_min, y_val))
            p2 = vb.mapViewToScene(QtCore.QPointF(x_max, y_val))

            px, py = pos.x(), pos.y()

            # check if mouse is horizontally within the segment
            if p1.x() <= px <= p2.x() or p2.x() <= px <= p1.x():
                dx = 0
            else:
                dx = min(abs(px - p1.x()), abs(px - p2.x()))

            dy = abs(py - p1.y())

            dist = (dx ** 2 + dy ** 2) ** 0.5

            if dist < min_dist:
                closest_mo = j
                min_dist = dist

        self.highlight_mo(closest_mo)

    def highlight_mo(self, mo_index):
        # reset visuals (unchanged)
        for item in self.mo_items:
            item.setPen(pg.mkPen("b", width=ORB_LINE_WIDTH))
        for item in self.ao_items:
            item.setPen(pg.mkPen("k", width=ORB_LINE_WIDTH))
        for item in self.conn_items:
            item.setPen(pg.mkPen(width=1))

        for label in self.mo_labels:
            label.setColor("k")
        for label in self.ao_labels:
            label.setColor("k")

        # hide window if nothing selected
        if mo_index is None:
            self.hover_window.hide()
            return

        # highlight MO
        self.mo_items[mo_index].setPen(pg.mkPen("r", width=ORB_LINE_WIDTH+1))
        self.mo_labels[mo_index].setColor("r")

        for item in self.conn_items:
            if item.mo_index == mo_index:
                item.setPen(pg.mkPen("r", width=1.5))
                ao_i = item.ao_index
                self.ao_items[ao_i].setPen(pg.mkPen("r", width=ORB_LINE_WIDTH+1))
                self.ao_labels[ao_i].setColor("r")

        # show screenshot
        spin_data = self.vm.active()
        mo_label = spin_data.molecular_orbitals[mo_index]
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
        dialog = MODialog(self, self.vm, mo_index)
        dialog.resize(900, 600)
        dialog.exec_()


class MODialog(QtWidgets.QDialog):
    def __init__(self, parent, vm, mo_index):
        super().__init__(parent)

        self.vm = vm
        self.mo_index = mo_index

        spin_data = self.vm.active()
        self.coeffs = spin_data.coefficient_matrix[:, mo_index]
        self.mo_label = spin_data.molecular_orbitals[mo_index]

        self.setWindowTitle(f"MO {self.mo_label}")
        self.resize(900, 600)

        layout = QtWidgets.QHBoxLayout(self)

        # left panel: table
        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Atomic Orbital", "Coefficient"])
        table.setRowCount(len(self.coeffs))

        for i, val in enumerate(self.coeffs):
            ao_label = spin_data.atomic_orbital_labels[i]
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

        # right: 3d view
        self.pv_widget = QtInteractor()
        self.pv_widget.enable_anti_aliasing('msaa', multi_samples=16)
        layout.addWidget(self.pv_widget, 2)

        # load cube
        cube_name = self.vm.get_cube_for_mo(self.mo_label)

        if cube_name:
            cube = self.vm.cube_manager.cubes[cube_name]
            self.vm.cube_manager.default_plotter_setup(self.pv_widget)
            self.vm.cube_manager.add_to_plotter(cube, self.pv_widget)
            self.pv_widget.reset_camera()

    def closeEvent(self, QCloseEvent):
        self.pv_widget.Finalize()
        super().closeEvent(QCloseEvent)


def main():
    app = QtWidgets.QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)

    vm = MODiagramViewModel()

    view = MODiagramView(vm)
    pth = r"D:\syncme\modelowanie DFT\co3o4_new_new\9.deep_o2_reduction\GOOD\1.spin_up\HSE\1.gas_to_metaloxo\2.1_almost_desorbed_small\1.mofe_o2\O2_1.MO_Diagram.lobster"
    view.vm.load_file(pth)
    view.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
