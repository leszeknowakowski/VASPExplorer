import os
import re
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

from lobster.cube_reader import CubeData, CubeIsosurfaceControlWindow, CubeManager
from lobster.mo_diagram import FlowChartFrame, LobsterModel, MODiagramViewModel

MO_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff")
CUBE_EXTENSIONS = (".cube",)


class _FitWidthScrollArea(QtWidgets.QScrollArea):
    def sizeHint(self):
        return QtCore.QSize(600, 520)

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        widget = self.widget()
        if widget is not None:
            widget.setFixedWidth(self.viewport().width())


class _ClickableImageLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.pixmap() is not None:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class _FlowChartPanel(QtWidgets.QWidget):
    def __init__(self, path: str, frames, coefficient_threshold: float):
        super().__init__()
        self.path = path
        self.frames = list(frames)
        self.coefficient_threshold = float(coefficient_threshold)
        self.region_items = []
        self.current_mo_pixmap = None
        self.current_mo_image_path = None
        self.current_cube_path = None

        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.title = QtWidgets.QLabel(self.path_label(path))
        self.title.setToolTip(path)
        self.title.setWordWrap(True)
        self.title.setMinimumWidth(0)
        self.title.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(self.title)

        self.mo_combo = QtWidgets.QComboBox()
        self.mo_combo.setMinimumWidth(0)
        self.mo_combo.setMinimumContentsLength(8)
        self.mo_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.mo_combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.default_combo_font = QtGui.QFont(self.mo_combo.font())
        self.default_combo_palette = QtGui.QPalette(self.mo_combo.palette())
        self.mo_combo.currentIndexChanged.connect(self.on_current_frame_changed)
        layout.addWidget(self.mo_combo)

        self.plot = pg.PlotWidget(background="w")
        self.plot.setMinimumWidth(0)
        self.plot.setMinimumHeight(520)
        self.plot.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.plot.setLabel("left", "Energy", units="eV")
        self.plot.setLabel("bottom", "DOS")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        layout.addWidget(self.plot, 1)

        self.mo_image_label = _ClickableImageLabel()
        self.mo_image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.mo_image_label.setMinimumHeight(0)
        self.mo_image_label.setFixedHeight(230)
        self.mo_image_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.mo_image_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.mo_image_label.clicked.connect(self.open_current_cube_plotter)
        self.mo_image_label.hide()
        layout.addWidget(self.mo_image_label)

        self.populate_combo()

    def sizeHint(self):
        return QtCore.QSize(240, 730)

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_mo_image_pixmap()

    @staticmethod
    def path_label(path: str) -> str:
        file_path = Path(path)
        parent = file_path.parent.name
        if parent:
            return f"{parent} / {file_path.name}"
        return file_path.name

    @staticmethod
    def frame_label(frame: FlowChartFrame) -> str:
        coefficients = ", ".join(
            f"{item.atomic_orbital_label} {item.coefficient:+.3f}"
            for item in frame.contributions
        )
        details = f"{frame.spin[0]}, E={frame.mo_energy:.1f}"
        if coefficients:
            details += f", {coefficients}"
        return f"{frame.mo_label.split('_')[-1]} ({details})"

    @staticmethod
    def normalized_image_key(value: str) -> str:
        return "".join(char.lower() for char in str(value) if char.isalnum())

    @staticmethod
    def unique_labels(labels):
        candidates = []
        for label in labels:
            label = str(label).strip()
            if label and label not in candidates:
                candidates.append(label)
        return candidates

    @classmethod
    def filename_matches_candidate(cls, stem: str, candidate: str) -> bool:
        candidate = str(candidate).strip()
        if not candidate:
            return False

        stem_text = str(stem).lower()
        candidate_text = candidate.lower()
        if cls.normalized_image_key(stem_text) == cls.normalized_image_key(candidate_text):
            return True

        pattern = rf"(?<![a-z0-9]){re.escape(candidate_text)}(?![a-z0-9])"
        return re.search(pattern, stem_text) is not None

    @staticmethod
    def spin_insertion(spin: str) -> str:
        return "1" if spin == "alpha" else "2"

    @staticmethod
    def opposite_spin_insertion(spin: str) -> str:
        return "2" if spin == "alpha" else "1"

    @staticmethod
    def raw_name_labels(frame: FlowChartFrame):
        return [
            frame.mo_label,
            frame.dos_orbital_label,
            frame.mo_label.split("_")[-1],
        ]

    @classmethod
    def spin_qualified_name_candidates(cls, frame: FlowChartFrame, insertion: str):
        labels = []
        diagram_prefix = Path(frame.path).name.split("_", 1)[0]

        for label in (frame.mo_label, frame.dos_orbital_label):
            label = str(label).strip()
            if not label:
                continue

            parts = str(label).split("_")
            if len(parts) >= 2:
                inserted_after_prefix = list(parts)
                inserted_after_prefix.insert(2, insertion)
                labels.append("_".join(inserted_after_prefix))

                inserted_before_orbital = list(parts)
                inserted_before_orbital.insert(len(inserted_before_orbital) - 1, insertion)
                labels.append("_".join(inserted_before_orbital))

            if diagram_prefix and not label.lower().startswith(f"{diagram_prefix.lower()}_"):
                labels.append(f"{diagram_prefix}_{insertion}_{label}")
                labels.append(f"{diagram_prefix}_{label}_{insertion}")

        return cls.unique_labels(labels)

    @classmethod
    def image_name_candidates(cls, frame: FlowChartFrame):
        labels = cls.spin_qualified_name_candidates(frame, cls.spin_insertion(frame.spin))
        labels.extend(cls.raw_name_labels(frame))
        return cls.unique_labels(labels)

    @staticmethod
    def name_tokens(value: str):
        return re.findall(r"[a-z0-9]+", str(value).lower())

    @classmethod
    def spin_marker_before_candidate(cls, stem: str, candidate: str):
        stem_tokens = cls.name_tokens(stem)
        candidate_tokens = cls.name_tokens(candidate)
        if not stem_tokens or not candidate_tokens:
            return None

        candidate_length = len(candidate_tokens)
        for index in range(0, len(stem_tokens) - candidate_length + 1):
            if stem_tokens[index:index + candidate_length] != candidate_tokens:
                continue
            if index > 0 and stem_tokens[index - 1] in {"1", "2"}:
                return stem_tokens[index - 1]
        return None

    @classmethod
    def filename_matches_frame_spin(cls, stem: str, frame: FlowChartFrame, candidates):
        desired_marker = cls.spin_insertion(frame.spin)
        opposite_marker = cls.opposite_spin_insertion(frame.spin)

        desired_candidates = cls.spin_qualified_name_candidates(frame, desired_marker)
        if any(cls.filename_matches_candidate(stem, candidate) for candidate in desired_candidates):
            return True

        opposite_candidates = cls.spin_qualified_name_candidates(frame, opposite_marker)
        if any(cls.filename_matches_candidate(stem, candidate) for candidate in opposite_candidates):
            return False

        markers = [
            marker
            for candidate in candidates
            for marker in [cls.spin_marker_before_candidate(stem, candidate)]
            if marker is not None
        ]
        if desired_marker in markers:
            return True
        if opposite_marker in markers:
            return False
        return True

    @classmethod
    def find_mo_image(cls, frame: FlowChartFrame):
        return cls.find_matching_file(frame, MO_IMAGE_EXTENSIONS)

    @classmethod
    def find_mo_cube(cls, frame: FlowChartFrame):
        return cls.find_matching_file(frame, CUBE_EXTENSIONS)

    @classmethod
    def find_matching_file(cls, frame: FlowChartFrame, extensions):
        directory = Path(frame.path).parent
        if not directory.is_dir():
            return None

        candidates = cls.image_name_candidates(frame)
        for candidate in candidates:
            for suffix in extensions:
                match_path = directory / f"{candidate}{suffix}"
                if match_path.is_file() and cls.filename_matches_frame_spin(match_path.stem, frame, candidates):
                    return match_path

        normalized_candidates = {cls.normalized_image_key(candidate) for candidate in candidates}
        for match_path in directory.iterdir():
            if match_path.suffix.lower() not in extensions:
                continue
            normalized_stem = cls.normalized_image_key(match_path.stem)
            if normalized_stem in normalized_candidates:
                if cls.filename_matches_frame_spin(match_path.stem, frame, candidates):
                    return match_path
                continue
            if any(cls.filename_matches_candidate(match_path.stem, candidate) for candidate in candidates):
                if cls.filename_matches_frame_spin(match_path.stem, frame, candidates):
                    return match_path
        return None

    def frame_is_above_threshold(self, frame: FlowChartFrame) -> bool:
        return any(
            item.abs_coefficient + 1e-12 >= self.coefficient_threshold
            for item in frame.contributions
        )

    def populate_combo(self):
        self.mo_combo.blockSignals(True)
        self.mo_combo.clear()
        if not self.frames:
            self.mo_combo.addItem("No MO DOS traces")
            self.mo_combo.setEnabled(False)
        else:
            self.mo_combo.setEnabled(True)
            for frame in self.frames:
                self.mo_combo.addItem(self.frame_label(frame), frame)
                index = self.mo_combo.count() - 1
                if self.frame_is_above_threshold(frame):
                    font = self.mo_combo.font()
                    font.setBold(True)
                    self.mo_combo.setItemData(index, QtGui.QBrush(QtCore.Qt.red), QtCore.Qt.ForegroundRole)
                    self.mo_combo.setItemData(index, font, QtCore.Qt.FontRole)
        self.mo_combo.blockSignals(False)
        self.on_current_frame_changed()

    def current_frame(self):
        if not self.frames:
            return None
        return self.mo_combo.currentData()

    def on_current_frame_changed(self):
        frame = self.current_frame()
        font = QtGui.QFont(self.default_combo_font)
        font.setBold(bool(frame and self.frame_is_above_threshold(frame)))
        self.mo_combo.setFont(font)

        palette = QtGui.QPalette(self.default_combo_palette)
        if frame and self.frame_is_above_threshold(frame):
            palette.setColor(QtGui.QPalette.Text, QtCore.Qt.red)
            palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.red)
        self.mo_combo.setPalette(palette)

        self.plot_current_frame()
        self.update_mo_image()

    def update_mo_image(self):
        self.current_mo_pixmap = None
        self.current_mo_image_path = None
        self.current_cube_path = None
        self.mo_image_label.clear()
        self.mo_image_label.hide()

        frame = self.current_frame()
        if frame is None:
            return

        image_path = self.find_mo_image(frame)
        if image_path is None:
            return

        pixmap = QtGui.QPixmap(str(image_path))
        if pixmap.isNull():
            return

        self.current_mo_pixmap = pixmap
        self.current_mo_image_path = image_path
        self.current_cube_path = self.find_mo_cube(frame)
        if self.current_cube_path is None:
            self.mo_image_label.setToolTip(f"{image_path}\nNo matching cube file found.")
        else:
            self.mo_image_label.setToolTip(f"{image_path}\nClick to open {self.current_cube_path.name}")
        self.mo_image_label.show()
        self.update_mo_image_pixmap()

    def open_current_cube_plotter(self):
        frame = self.current_frame()
        if frame is None:
            return

        cube_path = self.current_cube_path or self.find_mo_cube(frame)
        if cube_path is None:
            QtWidgets.QMessageBox.information(
                self,
                "Cube Viewer",
                f"No matching cube file was found for {frame.mo_label} ({frame.spin}).",
            )
            return

        try:
            manager = CubeManager()
            cube = CubeData(str(cube_path))
            dialog = CubeIsosurfaceControlWindow(manager, cube, self)
            dialog.setWindowTitle(f"Cube: {cube_path.name}")
            dialog.exec_()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Cube Viewer",
                f"Could not open cube file:\n{cube_path}\n\n{exc}",
            )

    def update_mo_image_pixmap(self):
        if self.current_mo_pixmap is None or self.current_mo_pixmap.isNull():
            return

        size = self.mo_image_label.contentsRect().size()
        if size.width() <= 0 or size.height() <= 0:
            return

        scaled = self.current_mo_pixmap.scaled(
            size,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.mo_image_label.setPixmap(scaled)

    def plot_current_frame(self):
        self.plot.clear()
        self.region_items = []

        frame = self.current_frame()
        if frame is None:
            return

        values = np.asarray(frame.dos_values, dtype=float)
        energies = np.asarray(frame.energies, dtype=float)
        plot_values = -values if frame.spin == "beta" else values
        color = "#1f77b4" if frame.spin == "beta" else "#d62728"

        self.plot.plot(
            plot_values,
            energies,
            pen=pg.mkPen(color=color, width=2),
        )

        zero_line = pg.InfiniteLine(pos=0.0, angle=90, pen=pg.mkPen("#666666", width=1))
        zero_line.setZValue(-5)
        self.plot.addItem(zero_line)

        brush = pg.mkBrush(44, 160, 44, 45)
        pen = pg.mkPen(44, 160, 44, 90)
        for start, end in frame.intervals:
            if end <= start:
                continue
            region = pg.LinearRegionItem(
                values=(float(start), float(end)),
                orientation=pg.LinearRegionItem.Horizontal,
                brush=brush,
                pen=pen,
                movable=False,
            )
            region.setZValue(-10)
            self.plot.addItem(region)
            self.region_items.append(region)

        self.plot.enableAutoRange()


class _CoefficientsDialog(QtWidgets.QDialog):
    def __init__(self, parent, rows, threshold: float):
        super().__init__(parent)
        self.rows = rows
        self.threshold = threshold

        self.setWindowTitle("MO Coefficients")
        self.resize(1050, 650)

        layout = QtWidgets.QVBoxLayout(self)

        self.table = QtWidgets.QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(self.table, 1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.populate_table()

    def populate_table(self):
        mo_keys = []
        mo_meta = {}
        ao_labels = []
        coefficients = {}

        for row in self.rows:
            mo_key = (
                row["file_index"],
                row["path"],
                row["spin"],
                row["mo_index"],
                row["mo_label"],
            )
            if mo_key not in mo_meta:
                mo_meta[mo_key] = row
                mo_keys.append(mo_key)

            ao_label = row["atomic_orbital_label"]
            if ao_label not in ao_labels:
                ao_labels.append(ao_label)

            coefficients[(ao_label, mo_key)] = row

        self.table.setSortingEnabled(False)
        self.table.setColumnCount(len(mo_keys) + 1)
        self.table.setRowCount(len(ao_labels))
        self.table.setHorizontalHeaderLabels(
            ["Atomic orbital"] + [self._mo_header(mo_meta[key]) for key in mo_keys]
        )

        for row_index, ao_label in enumerate(ao_labels):
            ao_item = QtWidgets.QTableWidgetItem(ao_label)
            self.table.setItem(row_index, 0, ao_item)

            for column_index, mo_key in enumerate(mo_keys, start=1):
                row = coefficients.get((ao_label, mo_key))
                if row is None:
                    item = QtWidgets.QTableWidgetItem("")
                    self.table.setItem(row_index, column_index, item)
                    continue

                item = QtWidgets.QTableWidgetItem(f"{row['coefficient']:+.6f}")
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                item.setData(QtCore.Qt.UserRole, row["coefficient"])
                item.setToolTip(self._coefficient_tooltip(row))
                if row["coefficient"] < 0:
                    item.setForeground(QtCore.Qt.darkBlue)
                elif row["coefficient"] > 0:
                    item.setForeground(QtCore.Qt.darkRed)
                self._highlight_if_selected(item, row["abs_coefficient"])
                self.table.setItem(row_index, column_index, item)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    @staticmethod
    def _mo_header(row):
        return (
            f"{_FlowChartPanel.path_label(row['path'])}".split("/")[0] + f"{row['spin']}\n"
            f"{row['mo_label']}\n"
            f"E={row['mo_energy']:.3f} eV"
        )

    @staticmethod
    def _coefficient_tooltip(row):
        return (
            f"{row['path']}\n"
            f"{row['spin']} {row['mo_label']} index={row['mo_index']} "
            f"E={row['mo_energy']:.4f} eV\n"
            f"{row['atomic_orbital_label']}: {row['coefficient']:+.6f}"
        )

    def _highlight_if_selected(self, item, abs_coefficient: float):
        if abs_coefficient + 1e-12 < self.threshold:
            return
        font = item.font()
        font.setBold(True)
        item.setFont(font)


class FlowChart(QtWidgets.QMainWindow):
    def __init__(self, directory=None, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.base_dir = directory or getattr(parent, "dir", None) or os.getcwd()
        self.paths = []
        self.first_diagram = None
        self.flow_data = None
        self.diagram_cache = {}

        self.setWindowTitle("LOBSTER Flow Chart")
        self.resize(1400, 800)

        self._build_ui()
        self.load_directory(self.base_dir)

    def _build_ui(self):
        container = QtWidgets.QWidget()
        self.setCentralWidget(container)
        layout = QtWidgets.QVBoxLayout(container)

        controls = QtWidgets.QVBoxLayout()
        layout.addLayout(controls)

        file_controls = QtWidgets.QHBoxLayout()
        selection_controls = QtWidgets.QHBoxLayout()
        threshold_controls = QtWidgets.QHBoxLayout()
        controls.addLayout(file_controls)
        controls.addLayout(selection_controls)
        controls.addLayout(threshold_controls)

        self.directory_label = QtWidgets.QLabel()
        self.directory_label.setMinimumWidth(0)
        self.directory_label.setWordWrap(True)
        self.directory_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        file_controls.addWidget(self.directory_label, 1)

        choose_dir = QtWidgets.QPushButton("Choose Directory")
        choose_dir.clicked.connect(self.choose_directory)
        file_controls.addWidget(choose_dir)

        self.spin_combo = QtWidgets.QComboBox()
        self.spin_combo.addItem("Both spins", ("alpha", "beta"))
        self.spin_combo.addItem("Alpha", ("alpha",))
        self.spin_combo.addItem("Beta", ("beta",))
        selection_controls.addWidget(QtWidgets.QLabel("Spin"))
        selection_controls.addWidget(self.spin_combo)

        self.atom_combo = QtWidgets.QComboBox()
        self.atom_combo.currentTextChanged.connect(self.populate_orbitals)
        selection_controls.addWidget(QtWidgets.QLabel("Atom"))
        selection_controls.addWidget(self.atom_combo)

        self.orbital_combo = QtWidgets.QComboBox()
        selection_controls.addWidget(QtWidgets.QLabel("AO"))
        selection_controls.addWidget(self.orbital_combo)
        selection_controls.addStretch(1)

        self.ao_threshold = QtWidgets.QDoubleSpinBox()
        self.ao_threshold.setRange(0.0, 10.0)
        self.ao_threshold.setDecimals(3)
        self.ao_threshold.setSingleStep(0.05)
        self.ao_threshold.setValue(0.3)
        threshold_controls.addWidget(QtWidgets.QLabel("Min |coef|"))
        threshold_controls.addWidget(self.ao_threshold)

        self.dos_threshold = QtWidgets.QDoubleSpinBox()
        self.dos_threshold.setRange(0.0, 1.0)
        self.dos_threshold.setDecimals(3)
        self.dos_threshold.setSingleStep(0.05)
        self.dos_threshold.setValue(0.1)
        threshold_controls.addWidget(QtWidgets.QLabel("DOS threshold"))
        threshold_controls.addWidget(self.dos_threshold)

        plot_button = QtWidgets.QPushButton("Plot")
        plot_button.clicked.connect(lambda: self.refresh_flow(show_errors=True))
        threshold_controls.addWidget(plot_button)

        coefficients_button = QtWidgets.QPushButton("Show coefficients")
        coefficients_button.clicked.connect(self.show_coefficients)
        threshold_controls.addWidget(coefficients_button)

        threshold_controls.addStretch(1)

        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.scroll = _FitWidthScrollArea()
        self.scroll.setMinimumWidth(0)
        self.scroll.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        layout.addWidget(self.scroll, 1)

        self.panel_widget = QtWidgets.QWidget()
        self.panel_widget.setMinimumWidth(0)
        self.panel_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.panel_layout = QtWidgets.QHBoxLayout(self.panel_widget)
        self.panel_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_layout.setSpacing(8)
        self.panel_layout.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        self.scroll.setWidget(self.panel_widget)

    def choose_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose directory with MO diagrams",
            self.base_dir,
        )
        if directory:
            self.load_directory(directory)

    def load_directory(self, directory: str):
        self.base_dir = str(directory)
        self.directory_label.setText(self.base_dir)
        self.paths = MODiagramViewModel.find_mo_diagram_paths(self.base_dir)
        self.diagram_cache = {}
        self.clear_panels()

        if not self.paths:
            self.first_diagram = None
            self.atom_combo.clear()
            self.orbital_combo.clear()
            self.status_label.setText("No *MO_Diagram.lobster files found.")
            return

        try:
            self.first_diagram = LobsterModel.load(self.paths[0])
            self.diagram_cache[self.paths[0]] = self.first_diagram
        except Exception as exc:
            self.first_diagram = None
            self.status_label.setText(f"Could not load first MO diagram: {exc}")
            return

        self.populate_atoms()
        self.status_label.setText(f"Found {len(self.paths)} MO diagram file(s).")
        self.refresh_flow(show_errors=False)

    def populate_atoms(self):
        if self.first_diagram is None:
            return

        atoms = []
        for spin_data in (self.first_diagram.alpha, self.first_diagram.beta):
            for atom in spin_data.atomic_groups:
                if atom not in atoms:
                    atoms.append(atom)

        self.atom_combo.blockSignals(True)
        self.atom_combo.clear()
        self.atom_combo.addItems(atoms)
        self.atom_combo.blockSignals(False)

        if atoms:
            self.populate_orbitals(atoms[0])

    def populate_orbitals(self, atom: str):
        self.orbital_combo.clear()
        if self.first_diagram is None or not atom:
            return

        labels = []
        for spin_data in (self.first_diagram.alpha, self.first_diagram.beta):
            for label in spin_data.atomic_groups.get(atom, []):
                if label not in labels:
                    labels.append(label)

        for label in labels:
            self.orbital_combo.addItem(LobsterModel._ao_name(label), label)

    def selected_spins(self):
        return self.spin_combo.currentData()

    def selected_atomic_orbital(self):
        return self.orbital_combo.currentData()

    def selected_frames(self):
        frames = []
        for index in range(self.panel_layout.count()):
            widget = self.panel_layout.itemAt(index).widget()
            if isinstance(widget, _FlowChartPanel):
                frame = widget.current_frame()
                if frame is not None:
                    frames.append(frame)
        return frames

    def diagram_for_path(self, path: str):
        if path not in self.diagram_cache:
            self.diagram_cache[path] = LobsterModel.load(path)
        return self.diagram_cache[path]

    def show_coefficients(self):
        frames = self.selected_frames()
        if not frames:
            QtWidgets.QMessageBox.information(
                self,
                "MO Coefficients",
                "No molecular orbitals are currently selected.",
            )
            return

        rows = []
        errors = []
        for frame in frames:
            try:
                diagram = self.diagram_for_path(frame.path)
                spin_data = LobsterModel._select_spin_data(diagram, frame.spin)
                coefficient_matrix = np.asarray(spin_data.coefficient_matrix, dtype=float)
                if not 0 <= frame.mo_index < coefficient_matrix.shape[1]:
                    raise IndexError(f"MO index out of range: {frame.mo_index}")
            except Exception as exc:
                errors.append(f"{Path(frame.path).name} {frame.mo_label}: {exc}")
                continue

            for ao_index, atomic_orbital_label in enumerate(spin_data.atomic_orbital_labels):
                coefficient = float(coefficient_matrix[ao_index, frame.mo_index])
                rows.append({
                    "file_index": frame.file_index,
                    "path": frame.path,
                    "spin": frame.spin,
                    "mo_index": frame.mo_index,
                    "mo_label": frame.mo_label,
                    "mo_energy": frame.mo_energy,
                    "atomic_orbital_label": atomic_orbital_label,
                    "coefficient": coefficient,
                    "abs_coefficient": abs(coefficient),
                })

        if not rows:
            message = "No coefficients could be loaded for the selected molecular orbitals."
            if errors:
                message += "\n\n" + "\n".join(errors[:8])
            QtWidgets.QMessageBox.warning(self, "MO Coefficients", message)
            return

        if errors:
            self.status_label.setText("; ".join(errors[:3]))

        dialog = _CoefficientsDialog(self, rows, float(self.ao_threshold.value()))
        dialog.exec_()

    def refresh_flow(self, show_errors=True):
        self.clear_panels()

        atomic_orbital = self.selected_atomic_orbital()
        if not self.paths or not atomic_orbital:
            return

        self.flow_data = LobsterModel.build_flow_chart_data(
            self.paths,
            [atomic_orbital],
            ao_coefficient_threshold=float(self.ao_threshold.value()),
            dos_threshold_fraction=float(self.dos_threshold.value()),
            spins=self.selected_spins(),
            strict=False,
        )

        frames_by_file = self.flow_data.frames_by_file()
        for file_index, path in enumerate(self.paths):
            panel = _FlowChartPanel(
                path,
                frames_by_file.get(file_index, []),
                coefficient_threshold=float(self.ao_threshold.value()),
            )
            self.panel_layout.addWidget(panel, 1)

        highlighted_frames = [
            frame for frame in self.flow_data.frames
            if any(
                item.abs_coefficient + 1e-12 >= float(self.ao_threshold.value())
                for item in frame.contributions
            )
        ]
        if self.flow_data.frames:
            self.status_label.setText(
                f"{len(self.flow_data.frames)} MO DOS trace(s) available; "
                f"{len(highlighted_frames)} above threshold for {atomic_orbital}."
            )
        else:
            self.status_label.setText("No LCFO DOS traces were found.")

        if self.flow_data.errors and show_errors:
            details = "\n".join(self.flow_data.errors[:8])
            if len(self.flow_data.errors) > 8:
                details += f"\n... and {len(self.flow_data.errors) - 8} more"
            QtWidgets.QMessageBox.warning(self, "Flow Chart", details)

    def clear_panels(self):
        while self.panel_layout.count():
            item = self.panel_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
