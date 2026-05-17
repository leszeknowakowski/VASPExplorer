from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
import re
import sys
from pathlib import Path
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


class ParsedDiagram:
    def __init__(self, alpha: SpinData, beta: SpinData):
        self.alpha = alpha
        self.beta = beta


@dataclass(frozen=True)
class OrbitalMatch:
    source_mo_index: int
    target_mo_index: int
    source_mo_label: str
    target_mo_label: str
    score: float
    compared_coefficients: int
    matching_coefficients: int
    matched_atomic_orbitals: Tuple[str, ...]


@dataclass(frozen=True)
class OrbitalTrackStep:
    file_index: int
    path: str
    spin: str
    mo_index: int
    mo_label: str
    mo_energy: float
    score_from_previous: Optional[float] = None
    compared_coefficients: Optional[int] = None
    matching_coefficients: Optional[int] = None
    matched_atomic_orbitals: Tuple[str, ...] = ()


@dataclass
class OrbitalTrack:
    spin: str
    start_mo_index: int
    start_mo_label: str
    steps: List[OrbitalTrackStep]


@dataclass
class OrbitalTrackingSequence:
    paths: List[str]
    spin: str
    tracks: List[OrbitalTrack]
    transition_matches: List[List[OrbitalMatch]]


class LobsterModel:
    """Handles file parsing and data preparation."""

    @staticmethod
    def _print_matching_output(sequence):
        for track in sequence.tracks:
            print(f"\nTrack starting from {track.start_mo_label} / MO index {track.start_mo_index}")
            for step in track.steps:
                file_name = Path(step.path).name
                if step.score_from_previous is None:
                    print(
                        f"  file {step.file_index}: {file_name} -> "
                        f"{step.mo_label} index={step.mo_index}, energy={step.mo_energy:.4f}"
                    )
                else:
                    print(
                        f"  file {step.file_index}: {file_name} -> "
                        f"{step.mo_label} index={step.mo_index}, energy={step.mo_energy:.4f}, "
                        f"score={step.score_from_previous:.2f}, "
                        f"matched={step.matching_coefficients}/{step.compared_coefficients}, "
                        f"AOs={', '.join(step.matched_atomic_orbitals)}"
                    )

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
    def _validate_similarity_options(tolerance: float, coefficient_threshold: float):
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        if coefficient_threshold < 0:
            raise ValueError("coefficient_threshold must be non-negative")

    @staticmethod
    def _mo_count(spin_data: SpinData) -> int:
        return int(np.asarray(spin_data.coefficient_matrix).shape[1])

    @staticmethod
    def _mo_label(spin_data: SpinData, mo_index: int) -> str:
        if 0 <= mo_index < len(spin_data.molecular_orbitals):
            return spin_data.molecular_orbitals[mo_index]
        return str(mo_index)

    @staticmethod
    def _mo_energy(spin_data: SpinData, mo_index: int) -> float:
        if 0 <= mo_index < len(spin_data.mo_energies):
            return float(spin_data.mo_energies[mo_index])
        return float("nan")

    @staticmethod
    def _select_spin_data(diagram: ParsedDiagram, spin: str) -> SpinData:
        if spin == "alpha":
            return diagram.alpha
        if spin == "beta":
            return diagram.beta
        raise ValueError("spin must be 'alpha' or 'beta'")

    @staticmethod
    def _within_relative_tolerance(reference: float, value: float, tolerance: float) -> bool:
        reference = abs(float(reference))
        value = abs(float(value))
        if reference == 0:
            return value == 0
        return abs(value - reference) <= (tolerance * reference) + 1e-12

    @classmethod
    def dominant_coefficients(
            cls,
            spin_data: SpinData,
            mo_index: int,
            coefficient_threshold: float = 0.3,
    ) -> List[Tuple[str, float, float]]:
        cls._validate_similarity_options(0.0, coefficient_threshold)
        coeff = np.asarray(spin_data.coefficient_matrix, dtype=float)
        labels = spin_data.atomic_orbital_labels

        if coeff.ndim != 2:
            raise ValueError("coefficient_matrix must be a 2D array")
        if len(labels) != coeff.shape[0]:
            raise ValueError("atomic_orbital_labels length must match coefficient_matrix rows")
        if not 0 <= mo_index < coeff.shape[1]:
            raise IndexError("mo_index out of range")

        column = coeff[:, mo_index]
        order = np.argsort(np.abs(column))[::-1]
        dominant = []

        for ao_index in order:
            value = float(column[ao_index])
            abs_value = abs(value)
            if abs_value < coefficient_threshold:
                continue
            dominant.append((labels[ao_index], value, abs_value))

        return dominant

    @classmethod
    def coefficient_similarity_details(
            cls,
            left: SpinData,
            source_mo_index: int,
            right: SpinData,
            target_mo_index: int,
            tolerance: float = 0.20,
            coefficient_threshold: float = 0.3,
    ) -> Tuple[float, int, int, Tuple[str, ...]]:
        cls._validate_similarity_options(tolerance, coefficient_threshold)

        source_coefficients = cls.dominant_coefficients(
            left,
            source_mo_index,
            coefficient_threshold=coefficient_threshold,
        )
        target_matrix = np.asarray(right.coefficient_matrix, dtype=float)

        if target_matrix.ndim != 2:
            raise ValueError("coefficient_matrix must be a 2D array")
        if len(right.atomic_orbital_labels) != target_matrix.shape[0]:
            raise ValueError("atomic_orbital_labels length must match coefficient_matrix rows")
        if not 0 <= target_mo_index < target_matrix.shape[1]:
            raise IndexError("target_mo_index out of range")

        target_by_label = {
            label: abs(float(target_matrix[ao_index, target_mo_index]))
            for ao_index, label in enumerate(right.atomic_orbital_labels)
        }

        matched_labels = []
        for label, _source_value, source_abs in source_coefficients:
            target_abs = target_by_label.get(label)
            if target_abs is None:
                continue
            if cls._within_relative_tolerance(source_abs, target_abs, tolerance):
                matched_labels.append(label)

        compared = len(source_coefficients)
        matching = len(matched_labels)
        score = matching / compared if compared else 0.0
        return score, compared, matching, tuple(matched_labels)

    @classmethod
    def coefficient_similarity(
            cls,
            left: SpinData,
            source_mo_index: int,
            right: SpinData,
            target_mo_index: int,
            tolerance: float = 0.20,
            coefficient_threshold: float = 0.3,
    ) -> Tuple[float, int, int]:
        score, compared, matching, _matched_labels = cls.coefficient_similarity_details(
            left,
            source_mo_index,
            right,
            target_mo_index,
            tolerance=tolerance,
            coefficient_threshold=coefficient_threshold,
        )
        return score, compared, matching

    @classmethod
    def match_spin_data(
            cls,
            left: SpinData,
            right: SpinData,
            tolerance: float = 0.20,
            min_score: float = 1.0,
            coefficient_threshold: float = 0.3,
            one_to_one: bool = True,
            source_mo_indices: Optional[Sequence[int]] = None,
            target_mo_indices: Optional[Sequence[int]] = None,
    ) -> List[OrbitalMatch]:
        cls._validate_similarity_options(tolerance, coefficient_threshold)
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")

        left_mo_count = cls._mo_count(left)
        right_mo_count = cls._mo_count(right)
        if source_mo_indices is None:
            source_indices = list(range(left_mo_count))
        elif isinstance(source_mo_indices, int):
            source_indices = [source_mo_indices]
        else:
            source_indices = list(source_mo_indices)

        if target_mo_indices is None:
            target_indices = list(range(right_mo_count))
        elif isinstance(target_mo_indices, int):
            target_indices = [target_mo_indices]
        else:
            target_indices = list(target_mo_indices)

        for source_mo_index in source_indices:
            if not 0 <= source_mo_index < left_mo_count:
                raise IndexError("source_mo_indices contains an out-of-range MO index")
        for target_mo_index in target_indices:
            if not 0 <= target_mo_index < right_mo_count:
                raise IndexError("target_mo_indices contains an out-of-range MO index")

        candidates = []
        for source_mo_index in source_indices:
            for target_mo_index in target_indices:
                score, compared, matching, matched_labels = cls.coefficient_similarity_details(
                    left,
                    source_mo_index,
                    right,
                    target_mo_index,
                    tolerance=tolerance,
                    coefficient_threshold=coefficient_threshold,
                )
                if compared == 0 or score + 1e-12 < min_score:
                    continue
                candidates.append(OrbitalMatch(
                    source_mo_index=source_mo_index,
                    target_mo_index=target_mo_index,
                    source_mo_label=cls._mo_label(left, source_mo_index),
                    target_mo_label=cls._mo_label(right, target_mo_index),
                    score=score,
                    compared_coefficients=compared,
                    matching_coefficients=matching,
                    matched_atomic_orbitals=matched_labels,
                ))

        candidates.sort(key=lambda match: (
            -match.score,
            -match.matching_coefficients,
            -match.compared_coefficients,
            match.source_mo_index,
            match.target_mo_index,
        ))

        if one_to_one:
            used_sources = set()
            used_targets = set()
            matches = []
            for match in candidates:
                if match.source_mo_index in used_sources or match.target_mo_index in used_targets:
                    continue
                used_sources.add(match.source_mo_index)
                used_targets.add(match.target_mo_index)
                matches.append(match)
        else:
            matches = candidates

        return sorted(matches, key=lambda match: (match.source_mo_index, match.target_mo_index))

    @classmethod
    def _track_step(
            cls,
            file_index: int,
            path: str,
            spin: str,
            spin_data: SpinData,
            mo_index: int,
            match: Optional[OrbitalMatch] = None,
    ) -> OrbitalTrackStep:
        return OrbitalTrackStep(
            file_index=file_index,
            path=path,
            spin=spin,
            mo_index=mo_index,
            mo_label=cls._mo_label(spin_data, mo_index),
            mo_energy=cls._mo_energy(spin_data, mo_index),
            score_from_previous=match.score if match else None,
            compared_coefficients=match.compared_coefficients if match else None,
            matching_coefficients=match.matching_coefficients if match else None,
            matched_atomic_orbitals=match.matched_atomic_orbitals if match else (),
        )

    @classmethod
    def track_orbitals(
            cls,
            paths: Sequence[str],
            spin: str = "alpha",
            tolerance: float = 0.20,
            min_score: float = 1.0,
            coefficient_threshold: float = 0.3,
            start_mo_indices: Optional[Sequence[int]] = None,
            one_to_one: bool = True,
    ) -> OrbitalTrackingSequence:
        cls._validate_similarity_options(tolerance, coefficient_threshold)
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")

        path_list = [str(path) for path in paths]
        diagrams = cls.load_many(path_list)
        if not diagrams:
            return OrbitalTrackingSequence(path_list, spin, [], [])

        spin_data_by_file = [cls._select_spin_data(diagram, spin) for diagram in diagrams]
        first_spin_data = spin_data_by_file[0]
        mo_count = cls._mo_count(first_spin_data)

        if start_mo_indices is None:
            start_indices = list(range(mo_count))
        elif isinstance(start_mo_indices, int):
            start_indices = [start_mo_indices]
        else:
            start_indices = list(start_mo_indices)

        for mo_index in start_indices:
            if not 0 <= mo_index < mo_count:
                raise IndexError("start_mo_indices contains an out-of-range MO index")

        tracks = [
            OrbitalTrack(
                spin=spin,
                start_mo_index=mo_index,
                start_mo_label=cls._mo_label(first_spin_data, mo_index),
                steps=[cls._track_step(0, path_list[0], spin, first_spin_data, mo_index)],
            )
            for mo_index in start_indices
        ]

        transition_matches = []
        for file_index in range(len(spin_data_by_file) - 1):
            active_source_indices = [
                track.steps[-1].mo_index
                for track in tracks
                if track.steps[-1].file_index == file_index
            ]
            matches = cls.match_spin_data(
                spin_data_by_file[file_index],
                spin_data_by_file[file_index + 1],
                tolerance=tolerance,
                min_score=min_score,
                coefficient_threshold=coefficient_threshold,
                one_to_one=one_to_one,
                source_mo_indices=active_source_indices,
            )
            transition_matches.append(matches)

            matches_by_source = {}
            for match in matches:
                matches_by_source.setdefault(match.source_mo_index, match)

            for track in tracks:
                last_step = track.steps[-1]
                if last_step.file_index != file_index:
                    continue
                match = matches_by_source.get(last_step.mo_index)
                if match is None:
                    continue
                next_spin_data = spin_data_by_file[file_index + 1]
                track.steps.append(cls._track_step(
                    file_index + 1,
                    path_list[file_index + 1],
                    spin,
                    next_spin_data,
                    match.target_mo_index,
                    match,
                ))

        return OrbitalTrackingSequence(path_list, spin, tracks, transition_matches)


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
