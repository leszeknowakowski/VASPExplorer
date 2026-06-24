import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

try:
    from pymatgen.electronic_structure.core import Spin
    from pymatgen.io.lobster.outputs import Cohpcar, get_orb_from_str
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    third_party = repo_root / "third_party"
    if third_party.is_dir():
        sys.path.insert(0, str(third_party))
    from pymatgen.electronic_structure.core import Spin
    from pymatgen.io.lobster.outputs import Cohpcar, get_orb_from_str


LOCAL_COHPCAR_FILENAME = "COHPCAR.lobster"
TOTAL_INTERACTION_KEY = "__total__"
CLASSIC_DOS_COLORS_ID = "__classic_dos_colors__"

CLASSIC_DOS_COLORS = [
    "#FF6B6B",
    "#FFD93D",
    "#6BCB77",
    "#4D96FF",
    "#F38BA0",
    "#6A4C93",
    "#FFA41B",
    "#00CFC1",
    "#E4572E",
    "#9D4EDD",
]


@dataclass
class CohpBondMetadata:
    bond_key: str
    pair_label: str
    length: float | None = None
    interaction_labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CohpPlotEntry:
    bond_key: str
    interaction_key: str


class CohpcarDataset:
    """Small adapter over pymatgen's Cohpcar object for UI selection."""

    HEADER_PATTERN = re.compile(
        r"^\s*No\.(?P<bond>\d+):(?P<body>.*?)\((?P<length>[-+0-9.eE]+)\)\s*$"
    )

    def __init__(self, filename):
        self.filename = Path(filename)
        self.cohpcar = Cohpcar(filename=str(self.filename))
        self.energies = np.asarray(self.cohpcar.energies)
        self.cohp_data = self.cohpcar.cohp_data
        self.orb_res_cohp = self.cohpcar.orb_res_cohp or {}
        self.bond_keys = [
            key for key in self.cohp_data.keys() if key != "average"
        ]
        self.metadata = self._read_header_metadata()

        if not self.bond_keys:
            raise ValueError(f"No bonds found in COHPCAR file: {filename}")

    def _read_header_metadata(self):
        metadata: dict[str, CohpBondMetadata] = {}

        try:
            lines = self.filename.read_text(encoding="utf-8").splitlines()
        except OSError:
            return metadata

        if len(lines) < 3:
            return metadata

        try:
            number_of_header_entries = int(lines[1].split()[0]) - 1
        except (IndexError, ValueError):
            return metadata

        for line in lines[3 : 3 + number_of_header_entries]:
            parsed = self._parse_header_line(line)
            if parsed is None:
                continue

            bond_key, pair_label, length, interaction_key, interaction_label = parsed
            bond_metadata = metadata.setdefault(
                bond_key,
                CohpBondMetadata(
                    bond_key=bond_key,
                    pair_label=pair_label,
                    length=length,
                ),
            )

            if interaction_key is None:
                bond_metadata.pair_label = pair_label
                bond_metadata.length = length
            else:
                bond_metadata.interaction_labels[interaction_key] = interaction_label

        return metadata

    @classmethod
    def _parse_header_line(cls, line):
        match = cls.HEADER_PATTERN.match(line)
        if match is None:
            return None

        body = match.group("body")
        if "->" not in body:
            return None

        left_site, right_site = body.split("->", maxsplit=1)
        left_atom, left_orbital = cls._split_atom_orbital(left_site)
        right_atom, right_orbital = cls._split_atom_orbital(right_site)
        bond_key = match.group("bond")
        length = float(match.group("length"))
        pair_label = f"{left_atom} -> {right_atom}"

        if left_orbital is None or right_orbital is None:
            return bond_key, pair_label, length, None, None

        interaction_key = cls._orbital_key(left_orbital, right_orbital)
        interaction_label = (
            f"{left_atom}[{left_orbital}] -> {right_atom}[{right_orbital}]"
        )
        return bond_key, pair_label, length, interaction_key, interaction_label

    @staticmethod
    def _split_atom_orbital(site):
        site = site.strip()
        if "[" not in site:
            return site, None

        atom, orbital = site.split("[", maxsplit=1)
        return atom, orbital.rstrip("]")

    @staticmethod
    def _orbital_key(left_orbital, right_orbital):
        try:
            return get_orb_from_str([left_orbital, right_orbital])[0]
        except Exception:
            return f"{left_orbital}-{right_orbital}".replace("_", "")

    def bond_count(self):
        return len(self.bond_keys)

    def bond_display_label(self, bond_key):
        metadata = self._metadata_for_bond(bond_key)
        if metadata.length is None:
            return f"No.{bond_key}: {metadata.pair_label}"
        return f"No.{bond_key}: {metadata.pair_label} ({metadata.length:.4f} A)"

    def interaction_keys(self, bond_key):
        keys = []
        if self._has_total_curve(bond_key):
            keys.append(TOTAL_INTERACTION_KEY)

        keys.extend(self.orb_res_cohp.get(bond_key, {}).keys())
        return keys

    def interaction_label(self, bond_key, interaction_key):
        metadata = self._metadata_for_bond(bond_key)

        if interaction_key == TOTAL_INTERACTION_KEY:
            return f"Total {metadata.pair_label}"

        return metadata.interaction_labels.get(interaction_key, interaction_key)

    def interaction_curves(self, bond_key, interaction_key):
        if interaction_key == TOTAL_INTERACTION_KEY:
            return self.cohp_data[bond_key]["COHP"]

        return self.orb_res_cohp[bond_key][interaction_key]["COHP"]

    def resolve_interaction_key(self, bond_key, interaction_key):
        if interaction_key == TOTAL_INTERACTION_KEY:
            return interaction_key if self._has_total_curve(bond_key) else None

        orbital_data = self.orb_res_cohp.get(bond_key, {})
        if interaction_key in orbital_data:
            return interaction_key

        normalized_key = self._normalize_interaction_key(interaction_key)
        for candidate in orbital_data:
            if self._normalize_interaction_key(candidate) == normalized_key:
                return candidate

        return None

    @staticmethod
    def _normalize_interaction_key(interaction_key):
        return interaction_key.replace("_", "").replace("^", "")

    def _has_total_curve(self, bond_key):
        bond_data = self.cohp_data.get(bond_key, {})
        return bool(bond_data.get("COHP"))

    def _metadata_for_bond(self, bond_key):
        if bond_key in self.metadata:
            return self.metadata[bond_key]

        bond_data = self.cohp_data.get(bond_key, {})
        sites = bond_data.get("sites", ())

        if len(sites) >= 2:
            pair_label = f"site {sites[0] + 1} -> site {sites[1] + 1}"
        else:
            pair_label = f"Bond {bond_key}"

        return CohpBondMetadata(
            bond_key=bond_key,
            pair_label=pair_label,
            length=bond_data.get("length"),
        )


class CohpcarPlotWindow(QtWidgets.QMainWindow):
    """Window for plotting COHPCAR total and orbital-resolved interactions."""

    PLOT_LINEWIDTH = 2.2
    SPIN_DOWN_ALPHA = 115
    PLOT_BACKGROUND = "#11161c"
    AXIS_COLOR = "#dce5ee"
    GRID_COLOR = "#405064"

    def __init__(
        self,
        dataset=None,
        default_dir=None,
        parent=None,
        selected_bond_key=None,
        selected_interactions=None,
    ):
        super().__init__(parent)
        self.dataset = dataset
        self.default_dir = Path(default_dir or Path.cwd())
        self.selected_bond_key = selected_bond_key
        self.selected_interactions = list(selected_interactions or [])
        self.interaction_boxes = []
        self.updating_checkboxes = False
        self.plot_entries: list[CohpPlotEntry] = []
        self.region = None
        self.spin_up_legend = None
        self.spin_down_legend = None
        self.current_region = (-5.0, 5.0)
        self.updating_region = False

        self._setup_window()
        self._setup_controls()
        self._setup_plot()
        self._connect_signals()

        if self.dataset is not None:
            self._populate_bonds()

    def _setup_window(self):
        self.setObjectName("cohpcarViewer")
        self.setWindowTitle("COHPCAR Viewer")
        self.resize(1300, 850)
        self.setStyleSheet(COHPCAR_VIEWER_STYLESHEET)

        central_widget = QtWidgets.QWidget()
        central_widget.setObjectName("cohpcarCentral")
        self.setCentralWidget(central_widget)
        self.main_layout = QtWidgets.QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)

    def _setup_controls(self):
        top_controls = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(top_controls)

        self.open_file_button = QtWidgets.QPushButton("Open COHPCAR")
        top_controls.addWidget(self.open_file_button)

        top_controls.addWidget(QtWidgets.QLabel("Bond"))
        self.bond_combo = QtWidgets.QComboBox()
        self.bond_combo.setMinimumWidth(280)
        top_controls.addWidget(self.bond_combo)

        top_controls.addWidget(QtWidgets.QLabel("Colors"))
        self.color_combo = QtWidgets.QComboBox()
        self._populate_color_combo()
        top_controls.addWidget(self.color_combo)

        self.plot_button = QtWidgets.QPushButton("Add plot")
        top_controls.addWidget(self.plot_button)

        self.clear_selection_button = QtWidgets.QPushButton("Clear selection")
        top_controls.addWidget(self.clear_selection_button)

        self.clear_button = QtWidgets.QPushButton("Clear plots")
        top_controls.addWidget(self.clear_button)

        top_controls.addStretch()

        self.info_label = QtWidgets.QLabel("No COHPCAR data loaded")
        self.info_label.setWordWrap(True)
        self.main_layout.addWidget(self.info_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.main_layout.addWidget(splitter, 1)

        self.interaction_widget = QtWidgets.QWidget()
        self.interaction_widget.setObjectName("cohpcarInteractionList")
        self.interaction_layout = QtWidgets.QVBoxLayout(self.interaction_widget)
        self.interaction_layout.setAlignment(QtCore.Qt.AlignTop)

        interaction_scroll = QtWidgets.QScrollArea()
        interaction_scroll.setWidgetResizable(True)
        interaction_scroll.setWidget(self.interaction_widget)

        left_panel = QtWidgets.QWidget()
        left_panel.setObjectName("cohpcarSidePanel")
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.addWidget(QtWidgets.QLabel("Interactions"))
        left_layout.addWidget(interaction_scroll)
        splitter.addWidget(left_panel)

        self.plot_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.full_range_plot = pg.PlotWidget(background=self.PLOT_BACKGROUND)
        self.bounded_plot = pg.PlotWidget(background=self.PLOT_BACKGROUND)
        self.plot_splitter.addWidget(self.full_range_plot)
        self.plot_splitter.addWidget(self.bounded_plot)
        self.plot_splitter.setStretchFactor(0, 2)
        self.plot_splitter.setStretchFactor(1, 3)

        splitter.addWidget(self.plot_splitter)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

    def _populate_color_combo(self):
        self.color_combo.addItem("Classic DOS colors", CLASSIC_DOS_COLORS_ID)

        preferred_colormaps = [
            "turbo",
            "viridis",
            "plasma",
            "inferno",
            "magma",
            "cividis",
            "CET-L17",
            "CET-L4",
            "CET-D1A",
        ]

        try:
            available = set(pg.colormap.listMaps())
        except Exception:
            available = set()

        added = set()
        for name in preferred_colormaps:
            if not available or name in available:
                self.color_combo.addItem(name, name)
                added.add(name)

        for name in sorted(available):
            if name in added:
                continue
            self.color_combo.addItem(name, name)

    def _setup_plot(self):
        for title, plot_widget in (
            ("Full COHP range", self.full_range_plot),
            ("Bounded COHP range", self.bounded_plot),
        ):
            plot_widget.setBackground(self.PLOT_BACKGROUND)
            plot_item = plot_widget.getPlotItem()
            plot_item.setTitle(title, color=self.AXIS_COLOR)
            plot_item.setLabel("bottom", "COHP")
            plot_item.setLabel("left", "Energy", units="eV")
            plot_item.showGrid(x=True, y=True, alpha=0.25)

            for axis_name in ("bottom", "left"):
                axis = plot_item.getAxis(axis_name)
                axis.setPen(pg.mkPen(self.AXIS_COLOR))
                axis.setTextPen(pg.mkPen(self.AXIS_COLOR))

        self.bounded_plot.sigRangeChanged.connect(self.update_region_from_bounded_plot)
        self._reset_plot_overlays()

    def _connect_signals(self):
        self.open_file_button.clicked.connect(self.open_file)
        self.bond_combo.currentIndexChanged.connect(self._bond_changed)
        self.color_combo.currentIndexChanged.connect(self.redraw_active_plots)
        self.plot_button.clicked.connect(self.add_selected_to_plots)
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.clear_button.clicked.connect(self.clear_plots)

    def open_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open COHPCAR file",
            str(self.default_dir),
            "COHPCAR files (COHPCAR.lobster *.lobster);;All files (*)",
        )

        if filename:
            self.load_file(filename)

    def load_file(self, filename, selected_bond_key=None, selected_interactions=None):
        try:
            self.dataset = CohpcarDataset(filename)
        except Exception as error:
            self.dataset = None
            self.info_label.setText(f"Could not load {filename}: {error}")
            self._populate_bonds()
            QtWidgets.QMessageBox.warning(self, "Load failed", self.info_label.text())
            return

        self.default_dir = Path(filename).resolve().parent
        self.selected_bond_key = selected_bond_key
        self.selected_interactions = list(selected_interactions or [])
        self.plot_entries = []
        self._populate_bonds()

        if selected_bond_key is not None and selected_interactions:
            self.add_selected_to_plots()
        else:
            self.redraw_active_plots()

    def _populate_bonds(self):
        self.bond_combo.blockSignals(True)
        self.bond_combo.clear()

        if self.dataset is None:
            self.bond_combo.blockSignals(False)
            self._clear_interaction_boxes()
            self.clear_plots()
            return

        for bond_key in self.dataset.bond_keys:
            self.bond_combo.addItem(
                self.dataset.bond_display_label(bond_key),
                bond_key,
            )

        selected_index = self._bond_index(self.selected_bond_key)
        self.bond_combo.setCurrentIndex(selected_index)
        self.bond_combo.blockSignals(False)
        self._populate_interactions()

    def _bond_index(self, bond_key):
        if self.dataset is None or bond_key is None:
            return 0

        for index, key in enumerate(self.dataset.bond_keys):
            if str(key) == str(bond_key):
                return index

        return 0

    def _bond_changed(self):
        self.selected_interactions = []
        self._populate_interactions()

    def _populate_interactions(self):
        self._clear_interaction_boxes()

        if self.dataset is None:
            self.info_label.setText("No COHPCAR data loaded")
            return

        bond_key = self.current_bond_key()
        if bond_key is None:
            return

        selected_keys = self._resolved_selected_interactions(bond_key)
        self.updating_checkboxes = True

        for interaction_key in self.dataset.interaction_keys(bond_key):
            box = QtWidgets.QCheckBox(
                self.dataset.interaction_label(bond_key, interaction_key)
            )
            box.setProperty("interaction_key", interaction_key)
            box.setChecked(interaction_key in selected_keys)
            box.stateChanged.connect(self.plot_selected)
            self.interaction_layout.addWidget(box)
            self.interaction_boxes.append(box)

        if not selected_keys and self.interaction_boxes:
            self.interaction_boxes[0].setChecked(True)

        self.updating_checkboxes = False
        self._update_selection_info()

    def _resolved_selected_interactions(self, bond_key):
        resolved = []
        for interaction_key in self.selected_interactions:
            resolved_key = self.dataset.resolve_interaction_key(
                bond_key,
                interaction_key,
            )
            if resolved_key is not None and resolved_key not in resolved:
                resolved.append(resolved_key)
        return resolved

    def _clear_interaction_boxes(self):
        while self.interaction_boxes:
            box = self.interaction_boxes.pop()
            self.interaction_layout.removeWidget(box)
            box.deleteLater()

    def current_bond_key(self):
        index = self.bond_combo.currentIndex()
        if index < 0:
            return None

        return self.bond_combo.itemData(index)

    def selected_interaction_keys(self):
        return [
            box.property("interaction_key")
            for box in self.interaction_boxes
            if box.isChecked()
        ]

    def plot_selected(self, *args):
        if self.updating_checkboxes:
            return

        self.selected_interactions = self.selected_interaction_keys()
        self._update_selection_info()

    def clear_selection(self):
        self.updating_checkboxes = True
        for box in self.interaction_boxes:
            box.setChecked(False)
        self.updating_checkboxes = False
        self.selected_interactions = []
        self._update_selection_info()

    def add_selected_to_plots(self):
        if self.updating_checkboxes:
            return

        if self.dataset is None:
            self.info_label.setText("No COHPCAR data loaded")
            return

        bond_key = self.current_bond_key()
        selected_keys = self.selected_interaction_keys()

        if bond_key is None or not selected_keys:
            self.info_label.setText("No interactions selected")
            return

        added_count = 0
        for interaction_key in selected_keys:
            resolved_key = self.dataset.resolve_interaction_key(
                bond_key,
                interaction_key,
            )
            if resolved_key is None:
                continue
            entry = CohpPlotEntry(str(bond_key), resolved_key)
            if entry in self.plot_entries:
                continue
            self.plot_entries.append(entry)
            added_count += 1

        self.info_label.setText(
            f"Added {added_count} interaction(s). Active plots: {len(self.plot_entries)}"
        )
        self.redraw_active_plots()

    def clear_plots(self):
        self.plot_entries = []
        self.redraw_active_plots()
        self._update_selection_info()

    def redraw_active_plots(self):
        self._reset_plot_overlays()

        if self.dataset is None:
            self.info_label.setText("No COHPCAR data loaded")
            return

        if not self.plot_entries:
            return

        valid_entries = []
        for entry in self.plot_entries:
            if self.dataset.resolve_interaction_key(
                entry.bond_key,
                entry.interaction_key,
            ) is not None:
                valid_entries.append(entry)

        self.plot_entries = valid_entries
        colors = self._colors_for_count(len(valid_entries))

        for index, entry in enumerate(valid_entries):
            self._plot_entry(entry, colors[index])

        self.update_bounded_plot_y_range()

    def _plot_entry(self, entry, color):
        curves = self.dataset.interaction_curves(
            entry.bond_key,
            entry.interaction_key,
        )
        label = self._plot_entry_label(entry)
        self._plot_interaction(curves, label, color)

    def _plot_interaction(self, curves, label, color):
        up_color = QtGui.QColor(color)
        down_color = QtGui.QColor(color)
        down_color.setAlpha(self.SPIN_DOWN_ALPHA)

        spin_specs = [
            (Spin.up, up_color, self.spin_up_legend),
            (Spin.down, down_color, self.spin_down_legend),
        ]

        for spin, spin_color, legend in spin_specs:
            if spin not in curves:
                continue

            pen = pg.mkPen(spin_color, width=self.PLOT_LINEWIDTH)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)

            self.full_range_plot.plot(
                np.asarray(curves[spin]),
                self.dataset.energies,
                pen=pen,
            )
            bounded_item = self.bounded_plot.plot(
                np.asarray(curves[spin]),
                self.dataset.energies,
                pen=pen,
            )
            if legend is not None:
                legend.addItem(bounded_item, label)

    def _plot_entry_label(self, entry):
        bond_label = self.dataset.bond_display_label(entry.bond_key)
        interaction_label = self.dataset.interaction_label(
            entry.bond_key,
            entry.interaction_key,
        )
        return f"{bond_label} | {interaction_label}"

    def _reset_plot_overlays(self):
        self._clear_plot_widget(self.full_range_plot)
        self._clear_plot_widget(self.bounded_plot)
        self._create_region()
        self._add_reference_lines()
        self._create_legends()

    def _clear_plot_widget(self, plot_widget):
        plot_widget.getPlotItem().clear()

    def _create_region(self):
        self.region = pg.LinearRegionItem(
            values=self.current_region,
            orientation=pg.LinearRegionItem.Horizontal,
            pen=pg.mkPen("#8bd3ec", width=1.3),
            brush=pg.mkBrush(95, 179, 214, 45),
        )
        self.region.setHoverBrush(pg.mkBrush(95, 179, 214, 80))
        self.full_range_plot.addItem(self.region)
        self.region.sigRegionChanged.connect(self.update_bounded_plot_y_range)

    def _create_legends(self):
        self.spin_up_legend = self._make_legend((10, 10), "Spin up")
        self.spin_down_legend = self._make_legend((270, 10), "Spin down")

    def _make_legend(self, offset, title):
        legend = pg.LegendItem(offset=offset)
        legend.setParentItem(self.bounded_plot.getPlotItem())
        legend.setBrush(pg.mkBrush(17, 22, 28, 230))
        legend.setPen(pg.mkPen("#405064"))
        dummy = pg.PlotDataItem([], [], pen=pg.mkPen((0, 0, 0, 0)))
        legend.addItem(dummy, title)
        return legend

    def update_bounded_plot_y_range(self):
        if self.region is None or self.updating_region:
            return

        self.updating_region = True
        min_y, max_y = sorted(self.region.getRegion())
        self.current_region = (float(min_y), float(max_y))
        self.bounded_plot.setYRange(min_y, max_y, padding=0)
        self.updating_region = False

    def update_region_from_bounded_plot(self, *args):
        if self.region is None or self.updating_region:
            return

        self.updating_region = True
        y_range = self.bounded_plot.viewRange()[1]
        self.current_region = (float(y_range[0]), float(y_range[1]))
        self.region.setRegion(y_range)
        self.updating_region = False

    def _update_selection_info(self):
        if self.dataset is None:
            self.info_label.setText("No COHPCAR data loaded")
            return

        bond_key = self.current_bond_key()
        selected_count = len(self.selected_interaction_keys())
        active_count = len(self.plot_entries)
        if bond_key is None:
            self.info_label.setText(f"Active plots: {active_count}")
            return

        self.info_label.setText(
            f"{self.dataset.bond_display_label(bond_key)}    "
            f"Selected: {selected_count}    Active plots: {active_count}"
        )

    def _colors_for_count(self, count):
        if count <= 0:
            return []

        positions = np.array([0.0]) if count == 1 else np.linspace(0.0, 1.0, count)
        color_source = self.color_combo.currentData()

        if color_source == CLASSIC_DOS_COLORS_ID:
            return self._classic_colors(positions)

        try:
            color_map = pg.colormap.get(color_source)
            return color_map.map(positions, mode="qcolor")
        except Exception:
            return self._classic_colors(positions)

    @staticmethod
    def _classic_colors(positions):
        colors = []
        last_index = len(CLASSIC_DOS_COLORS) - 1

        for position in positions:
            color_index = int(round(float(position) * last_index))
            colors.append(QtGui.QColor(CLASSIC_DOS_COLORS[color_index]))

        return colors

    def _add_reference_lines(self):
        fermi_pen = pg.mkPen("#5fb3d6", width=1.2, style=QtCore.Qt.DashLine)
        zero_pen = pg.mkPen("#405064", width=1.0, style=QtCore.Qt.DotLine)

        for plot_widget in (self.full_range_plot, self.bounded_plot):
            plot_widget.addItem(
                pg.InfiniteLine(
                    pos=0.0,
                    angle=0,
                    pen=fermi_pen,
                    movable=False,
                )
            )
            plot_widget.addItem(
                pg.InfiniteLine(
                    pos=0.0,
                    angle=90,
                    pen=zero_pen,
                    movable=False,
                )
            )


COHPCAR_VIEWER_STYLESHEET = """
QMainWindow#cohpcarViewer, QWidget#cohpcarCentral {
    background-color: #11161c;
    color: #dce5ee;
}

QWidget#cohpcarSidePanel, QWidget#cohpcarInteractionList {
    background-color: #151a21;
}

QLabel {
    color: #dce5ee;
    background: transparent;
}

QPushButton {
    color: #edf4fa;
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2f3b4a, stop:1 #202833);
    border: 1px solid #405064;
    border-radius: 6px;
    padding: 4px 9px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #2b3948;
    border-color: #5fb3d6;
}

QPushButton:pressed {
    background-color: #11161c;
    border-color: #d4a84f;
}

QComboBox {
    color: #edf4fa;
    background-color: #0f141a;
    border: 1px solid #334050;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #2f7fa5;
}

QComboBox:focus {
    border-color: #5fb3d6;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QScrollArea {
    background-color: #151a21;
    border: 1px solid #27313d;
    border-radius: 6px;
}

QCheckBox {
    spacing: 7px;
    color: #dce5ee;
    background: transparent;
    padding: 3px 2px;
}

QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #536272;
    background-color: #10161d;
    border-radius: 4px;
}

QCheckBox::indicator:checked {
    background-color: #5fb3d6;
    border-color: #8bd3ec;
}

QSplitter::handle {
    background-color: #27313d;
}

QSplitter::handle:hover {
    background-color: #5fb3d6;
}
"""


def get_initial_cohpcar_filename(default_dir=None):
    directory = Path(default_dir or Path.cwd())
    filename = directory / LOCAL_COHPCAR_FILENAME
    if filename.is_file():
        return str(filename)
    return None


def open_cohpcar_window(
    default_dir=None,
    parent=None,
    selected_bond_key=None,
    selected_interactions=None,
):
    window = CohpcarPlotWindow(
        default_dir=default_dir,
        parent=parent,
        selected_bond_key=selected_bond_key,
        selected_interactions=selected_interactions,
    )
    filename = get_initial_cohpcar_filename(default_dir)

    if filename is not None:
        window.load_file(
            filename,
            selected_bond_key=selected_bond_key,
            selected_interactions=selected_interactions,
        )

    return window


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = open_cohpcar_window(default_dir=os.getcwd())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
