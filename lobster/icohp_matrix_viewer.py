import sys
import re
import os
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from vtk import vtkActor, vtkLineSource, vtkPolyDataMapper, vtkSphereSource
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pymatgen.electronic_structure.core import Spin
from pymatgen.io.lobster.outputs import Icohplist

try:
    from lobster.custom_color_bar import EditableColorBarItem
except ImportError:
    # Keep direct script execution working: python lobster/icohp_matrix_viewer.py
    from custom_color_bar import EditableColorBarItem


ICOHPLIST_FILENAME = (
    r"D:\syncme\modelowanie DFT\co3o4_new_new\9.deep_o2_reduction\GOOD"
    r"\1.spin_up\HSE\1.gas_to_metaloxo\5.o2_2minus\ICOHPLIST.lobster"
)
ICOHP_COLORMAP_NAME = "ICOHP Mathematica"
DEFAULT_COLORMAP = ICOHP_COLORMAP_NAME
LOCAL_ICOHPLIST_FILENAME = "ICOHPLIST.lobster"

# Mathematica RGBColor stops scaled to pyqtgraph's expected 8-bit RGBA values.
ICOHP_COLORMAP_STOPS = (
    (0.0, (75, 108, 174, 255)),
    (0.48, (105, 189, 170, 255)),
    (0.49, (223, 243, 160, 255)),
    (0.5, (255, 255, 255, 255)),
    (0.51, (253, 200, 120, 255)),
    (0.52, (230, 89, 73, 255)),
    (1.0, (81, 3, 34, 255)),
)


def make_icohp_colormap():
    positions = np.array(
        [position for position, _ in ICOHP_COLORMAP_STOPS],
        dtype=float,
    )
    colors = np.array(
        [color for _, color in ICOHP_COLORMAP_STOPS],
        dtype=np.ubyte,
    )
    return pg.ColorMap(positions, colors, name=ICOHP_COLORMAP_NAME)


class MatrixImageItem(pg.ImageItem):
    """Image item that shows the matrix value under the cursor as a tooltip."""

    def __init__(self, matrix, orbitals_1, orbitals_2, spin_label):
        super().__init__(matrix)
        self.matrix = matrix
        self.orbitals_1 = orbitals_1
        self.orbitals_2 = orbitals_2
        self.spin_label = spin_label
        self.double_click_callback = None
        self.setAcceptHoverEvents(True)

    def hoverEvent(self, event):
        if event.isExit():
            QtWidgets.QToolTip.hideText()
            return

        position = event.pos()
        x_index = int(position.x())
        y_index = int(position.y())

        if not self._has_value_at(x_index, y_index):
            QtWidgets.QToolTip.hideText()
            return

        tooltip = (
            f"{self.spin_label}\n"
            f"{self.orbitals_1[x_index]} - {self.orbitals_2[y_index]}\n"
            f"ICOHP: {self.matrix[x_index, y_index]:.4f}"
        )
        QtWidgets.QToolTip.showText(event.screenPos().toPoint(), tooltip)

    def mouseDoubleClickEvent(self, event):
        position = event.pos()
        x_index = int(position.x())
        y_index = int(position.y())

        if self._has_value_at(x_index, y_index):
            if self.double_click_callback is not None:
                self.double_click_callback(x_index, y_index)
            event.accept()
            return

        super().mouseDoubleClickEvent(event)

    def set_double_click_callback(self, callback):
        self.double_click_callback = callback

    def _has_value_at(self, x_index, y_index):
        return (
            0 <= x_index < self.matrix.shape[0]
            and 0 <= y_index < self.matrix.shape[1]
        )


class IcohpDataset:
    """Loads and exposes ICOHPLIST bond data."""

    def __init__(self, filename):
        self.filename = filename
        self.icohp_obj = self._load_icohplist()
        self.icohplist = self.icohp_obj.icohplist
        self.bond_keys = list(self.icohplist.keys())
        self.bond_metadata = self._load_bond_metadata()
        self.color_levels = self._calculate_color_levels()

        if not self.bond_keys:
            raise ValueError(f"No bonds found in ICOHPLIST file: {filename}")

    def _load_icohplist(self):
        return Icohplist(
            filename=self.filename,
            are_coops=False,
        )

    def _load_bond_metadata(self):
        collection = getattr(self.icohp_obj, "icohpcollection", None)
        if collection is None:
            return [
                {
                    "atom_pair": str(bond_key),
                    "atom1": None,
                    "atom2": None,
                    "translation": (0, 0, 0),
                    "total_icohp": {},
                }
                for bond_key in self.bond_keys
            ]

        atom1_list = getattr(collection, "_list_atom1", [])
        atom2_list = getattr(collection, "_list_atom2", [])
        translation_list = getattr(collection, "_list_translation", [])
        total_icohp_list = getattr(collection, "_list_icohp", [])

        metadata = []

        for index, bond_key in enumerate(self.bond_keys):
            atom1 = self._get_list_value(atom1_list, index, str(bond_key))
            atom2 = self._get_list_value(atom2_list, index, "")
            translation = self._get_list_value(translation_list, index, (0, 0, 0))
            total_icohp = self._get_list_value(total_icohp_list, index, {})

            metadata.append(
                {
                    "atom_pair": self._format_atom_pair(atom1, atom2),
                    "atom1": atom1,
                    "atom2": atom2,
                    "translation": translation,
                    "total_icohp": total_icohp,
                }
            )

        return metadata

    @staticmethod
    def _get_list_value(values, index, fallback):
        if index >= len(values):
            return fallback

        return values[index]

    @staticmethod
    def _format_atom_pair(atom1, atom2):
        if atom2:
            return f"{atom1} - {atom2}"

        return str(atom1)

    def bond_count(self):
        return len(self.bond_keys)

    def get_bond(self, index):
        bond_key = self.bond_keys[index]
        return bond_key, self.icohplist[bond_key], self.bond_metadata[index]

    def _calculate_color_levels(self):
        values = []

        for bond_data in self.icohplist.values():
            for orbital_data in (bond_data.get("orbitals") or {}).values():
                icohp_by_spin = orbital_data.get("icohp", {})
                values.extend(float(value) for value in icohp_by_spin.values())

        if not values:
            return -1.0, 1.0

        minimum = min(values)
        maximum = max(values)
        biggest = max(abs(minimum), abs(maximum))
        minimum = - biggest
        maximum = biggest
        if minimum == maximum:
            return minimum - 1.0, maximum + 1.0

        return minimum, maximum


class OrbitalMatrixBuilder:
    """Builds orbital-resolved ICOHP matrices for a single bond."""

    @staticmethod
    def build(bond_data, spin):
        orbitals_dict = bond_data["orbitals"]

        orbitals_1 = []
        orbitals_2 = []
        orbital_1_indexes = {}
        orbital_2_indexes = {}

        for orbital_key in orbitals_dict:
            orbital_1, orbital_2 = OrbitalMatrixBuilder._split_orbital_key(
                orbital_key
            )
            OrbitalMatrixBuilder._add_orbital(
                orbital_1,
                orbitals_1,
                orbital_1_indexes,
            )
            OrbitalMatrixBuilder._add_orbital(
                orbital_2,
                orbitals_2,
                orbital_2_indexes,
            )

        matrix = np.zeros((len(orbitals_1), len(orbitals_2)))

        for orbital_key, orbital_data in orbitals_dict.items():
            orbital_1, orbital_2 = OrbitalMatrixBuilder._split_orbital_key(
                orbital_key
            )
            row = orbital_1_indexes[orbital_1]
            column = orbital_2_indexes[orbital_2]
            matrix[row, column] = orbital_data["icohp"].get(spin, 0.0)

        return matrix, orbitals_1, orbitals_2

    @staticmethod
    def _split_orbital_key(orbital_key):
        return orbital_key.split("-", maxsplit=1)

    @staticmethod
    def _add_orbital(orbital, orbitals, indexes):
        if orbital in indexes:
            return

        indexes[orbital] = len(orbitals)
        orbitals.append(orbital)


class SpinMatrixPlots:
    """Owns the pyqtgraph plots for spin-up and spin-down matrices."""

    def __init__(self, graphics):
        self.graphics = graphics
        self.show_values = False
        self.interaction_double_click_callback = None

        self.plot_up = self.graphics.addPlot(title="Spin Up", row=0, col=0)
        self.plot_down = self.graphics.addPlot(title="Spin Down", row=0, col=1)

        self.colorbar = EditableColorBarItem(
            colorMap=self._default_colormap(),
            width=30,
            orientation="vertical",
            interactive=True,
            label="Intensity",
            colorMapMenu=self._colormap_menu(),
        )

        self.graphics.addItem(self.colorbar, row=0, col=2)

    def set_interaction_double_click_callback(self, callback):
        self.interaction_double_click_callback = callback

    def update(self, matrix_up, matrix_down, orbitals_1, orbitals_2, levels=None):
        self.plot_up.clear()
        self.plot_down.clear()

        if levels is None:
            levels = self._symmetric_levels(matrix_up, matrix_down)
        colormap = self._current_colormap()

        image_up = self._add_matrix_image(
            self.plot_up,
            matrix_up,
            orbitals_1,
            orbitals_2,
            "Spin Up",
            colormap,
            levels,
        )
        image_down = self._add_matrix_image(
            self.plot_down,
            matrix_down,
            orbitals_1,
            orbitals_2,
            "Spin Down",
            colormap,
            levels,
        )

        self._connect_double_click(image_up, orbitals_1, orbitals_2)
        self._connect_double_click(image_down, orbitals_1, orbitals_2)

        self.colorbar.setImageItem([image_up, image_down])
        self.colorbar.setLevels(levels)

        self._configure_axes(orbitals_1, orbitals_2)

        if self.show_values:
            self._add_value_labels(self.plot_up, matrix_up, levels)
            self._add_value_labels(self.plot_down, matrix_down, levels)

        self.view_all()

    def set_show_values(self, show_values):
        self.show_values = show_values

    def show_empty(self, message="No ICOHPLIST data loaded"):
        self.plot_up.clear()
        self.plot_down.clear()

        for plot in (self.plot_up, self.plot_down):
            plot.getAxis("bottom").setTicks([])
            plot.getAxis("left").setTicks([])
            plot.setAspectLocked(False)

        self._add_empty_text(self.plot_up, message)
        self._add_empty_text(self.plot_down, message)
        self.colorbar.setImageItem([])
        self.colorbar.setLevels((-1.0, 1.0))

    def view_all(self):
        for plot in (self.plot_up, self.plot_down):
            plot.getViewBox().autoRange()

    @staticmethod
    def _add_empty_text(plot, message):
        text = pg.TextItem(message, anchor=(0.5, 0.5))
        plot.addItem(text)
        text.setPos(0.0, 0.0)
        plot.setRange(xRange=(-1.0, 1.0), yRange=(-1.0, 1.0), padding=0.0)

    @staticmethod
    def _add_matrix_image(
        plot,
        matrix,
        orbitals_1,
        orbitals_2,
        spin_label,
        colormap,
        levels,
    ):
        image = MatrixImageItem(matrix, orbitals_1, orbitals_2, spin_label)
        image.setColorMap(colormap)
        image.setLevels(levels)
        plot.addItem(image)
        return image

    def _connect_double_click(self, image, orbitals_1, orbitals_2):
        image.set_double_click_callback(
            lambda x_index, y_index: self._interaction_double_clicked(
                orbitals_1[x_index],
                orbitals_2[y_index],
            )
        )

    def _interaction_double_clicked(self, orbital_1, orbital_2):
        if self.interaction_double_click_callback is None:
            return

        self.interaction_double_click_callback(f"{orbital_1}-{orbital_2}")

    def _configure_axes(self, orbitals_1, orbitals_2):
        bottom_ticks = [(index + 0.5, orbital) for index, orbital in enumerate(orbitals_1)]
        left_ticks = [(index + 0.5, orbital) for index, orbital in enumerate(orbitals_2)]

        for plot in (self.plot_up, self.plot_down):
            plot.getAxis("bottom").setTicks([bottom_ticks])
            plot.getAxis("left").setTicks([left_ticks])
            plot.setAspectLocked(True)

    def _add_value_labels(self, plot, matrix, levels):
        max_abs_level = max(abs(levels[0]), abs(levels[1]), 1.0)

        for x_index in range(matrix.shape[0]):
            for y_index in range(matrix.shape[1]):
                value = float(matrix[x_index, y_index])
                text = pg.TextItem(
                    text=f"{value:.2f}",
                    color=self._label_color(value, max_abs_level),
                    anchor=(0.5, 0.5),
                )
                text.setFont(self._label_font())
                text.setZValue(10)
                plot.addItem(text)
                text.setPos(x_index + 0.5, y_index + 0.5)

    @staticmethod
    def _label_color(value, max_abs_level):
        if abs(value) / max_abs_level > 0.55:
            return "w"

        return "k"

    @staticmethod
    def _label_font():
        font = QtGui.QFont()
        font.setPointSize(8)
        return font

    @staticmethod
    def _symmetric_levels(matrix_up, matrix_down):
        vmax = max(
            SpinMatrixPlots._abs_max(matrix_up),
            SpinMatrixPlots._abs_max(matrix_down),
        )

        if vmax == 0.0:
            vmax = 1.0

        return -vmax, vmax

    @staticmethod
    def _abs_max(matrix):
        if matrix.size == 0:
            return 0.0

        return float(np.abs(matrix).max())

    @staticmethod
    def _default_colormap():
        if DEFAULT_COLORMAP == ICOHP_COLORMAP_NAME:
            return make_icohp_colormap()

        if DEFAULT_COLORMAP in pg.colormap.listMaps():
            return DEFAULT_COLORMAP

        return "viridis"

    @staticmethod
    def _colormap_menu():
        return pg.ColorMapMenu(
            userList=[make_icohp_colormap()],
            showColorMapSubMenus=True,
        )

    def _current_colormap(self):
        if self.colorbar._colorMap is None:
            default_colormap = self._default_colormap()
            if isinstance(default_colormap, pg.ColorMap):
                self.colorbar.setColorMap(default_colormap)
            else:
                self.colorbar.setColorMap(pg.colormap.get(default_colormap))

        return self.colorbar._colorMap


class IcohpMatrixViewer(QtWidgets.QWidget):
    """Main window for browsing orbital-resolved ICOHP matrices."""

    def __init__(
        self,
        dataset=None,
        load_error=None,
        parent=None,
        default_dir=None,
        levels=None,
        main_window=None,
        show_structure="auto",
    ):
        super().__init__(parent)
        owner = main_window or parent
        self.dataset = dataset
        self.load_error = load_error
        self.main_window = main_window or self._main_window_from_parent(parent)
        self.default_dir = Path(default_dir or getattr(owner, "dir", Path.cwd()))
        self.matrix_builder = OrbitalMatrixBuilder()
        self.current_bond_index = 0
        self.manual_color_levels = self._normalize_levels(levels)
        self.structure_highlight_actors = []
        self.show_structure = self._resolve_show_structure(show_structure)
        self.standalone_structure_viewer = None
        self.standalone_structure_control = None
        self.standalone_structure_container = None
        self.standalone_structure_layout = None
        self.plot_splitter = None
        self.plot_label_splitter = None
        self.shift_pressed = False

        self._setup_window()
        self._setup_controls()
        self._setup_graphics()
        self._connect_signals()
        self._connect_structure_signals()
        self.cohpcar_plot_windows = []
        self._sync_level_inputs()
        self.update_plot()

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.matrix_plots.view_all)

    def _setup_window(self):
        self.resize(1800, 900)
        self.setWindowTitle("Orbital-resolved ICOHP matrices")
        self.main_layout = QtWidgets.QVBoxLayout(self)

    def _setup_controls(self):
        controls_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(controls_layout)

        self.open_file_button = QtWidgets.QPushButton("Open file")
        controls_layout.addWidget(self.open_file_button)

        self.show_values_button = QtWidgets.QPushButton("Show numbers: Off")
        self.show_values_button.setCheckable(True)
        controls_layout.addWidget(self.show_values_button)

        controls_layout.addWidget(QtWidgets.QLabel("Min level"))
        self.min_level_input = self._create_level_input()
        controls_layout.addWidget(self.min_level_input)

        controls_layout.addWidget(QtWidgets.QLabel("Max level"))
        self.max_level_input = self._create_level_input()
        controls_layout.addWidget(self.max_level_input)

        self.apply_levels_button = QtWidgets.QPushButton("Apply levels")
        controls_layout.addWidget(self.apply_levels_button)

        self.auto_levels_button = QtWidgets.QPushButton("Auto levels")
        controls_layout.addWidget(self.auto_levels_button)

        controls_layout.addStretch()

        self.previous_button = QtWidgets.QPushButton("Previous")
        controls_layout.addWidget(self.previous_button)

        self.next_button = QtWidgets.QPushButton("Next")
        controls_layout.addWidget(self.next_button)

        self.info_label = QtWidgets.QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumHeight(28)
        if self.main_window is not None:
            self.main_layout.addWidget(self.info_label)

    def _setup_graphics(self):
        self.graphics = pg.GraphicsLayoutWidget()

        if self.main_window is None and self.show_structure:
            self.plot_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
            self.plot_splitter.addWidget(self.graphics)

            self.standalone_structure_container = QtWidgets.QWidget()
            self.standalone_structure_layout = QtWidgets.QVBoxLayout(
                self.standalone_structure_container
            )
            self.standalone_structure_layout.setContentsMargins(0, 0, 0, 0)
            self.standalone_structure_layout.setSpacing(0)
            self.plot_splitter.addWidget(self.standalone_structure_container)
            self.plot_splitter.setStretchFactor(0, 2)
            self.plot_splitter.setStretchFactor(1, 1)
            self.standalone_structure_container.hide()
            plot_area = self.plot_splitter
        else:
            plot_area = self.graphics

        if self.main_window is None:
            self.plot_label_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
            self.plot_label_splitter.addWidget(plot_area)
            self.plot_label_splitter.addWidget(self.info_label)
            self.plot_label_splitter.setStretchFactor(0, 1)
            self.plot_label_splitter.setStretchFactor(1, 0)
            self.plot_label_splitter.setSizes([820, 60])
            self.main_layout.insertWidget(1, self.plot_label_splitter)
        else:
            self.main_layout.insertWidget(1, plot_area)

        self.matrix_plots = SpinMatrixPlots(self.graphics)
        self._load_standalone_structure()

    def _connect_signals(self):
        self.open_file_button.clicked.connect(self.open_file)
        self.show_values_button.toggled.connect(self.toggle_value_labels)
        self.apply_levels_button.clicked.connect(self.apply_color_levels)
        self.auto_levels_button.clicked.connect(self.reset_color_levels)
        self.previous_button.clicked.connect(self.previous_bond)
        self.next_button.clicked.connect(self.next_bond)
        self.matrix_plots.set_interaction_double_click_callback(
            self.open_cohpcar_for_interaction
        )

    def _connect_structure_signals(self):
        if self.main_window is None:
            return

        slider = self._structure_geometry_slider()
        if slider is not None:
            slider.valueChanged.connect(lambda _value: self.refresh_structure_highlight())

    @staticmethod
    def _create_level_input():
        level_input = QtWidgets.QDoubleSpinBox()
        level_input.setRange(-1.0e9, 1.0e9)
        level_input.setDecimals(4)
        level_input.setSingleStep(0.1)
        level_input.setKeyboardTracking(False)
        return level_input

    def toggle_value_labels(self, checked):
        self.show_values_button.setText(
            "Show numbers: On" if checked else "Show numbers: Off"
        )
        self.matrix_plots.set_show_values(checked)
        self.update_plot()

    def open_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open ICOHPLIST file",
            str(self.default_dir),
            "ICOHPLIST files (ICOHPLIST.lobster *.lobster);;All files (*)",
        )

        if not filename:
            return

        self.load_file(filename)

    def load_file(self, filename):
        try:
            dataset = IcohpDataset(filename)
        except Exception as error:
            self.dataset = None
            self.load_error = f"Could not load {filename}: {error}"
            self.current_bond_index = 0
            if self.main_window is None:
                self._clear_standalone_structure()
            self.update_plot()
            QtWidgets.QMessageBox.warning(self, "Load failed", self.load_error)
            return

        self.dataset = dataset
        self.load_error = None
        self.current_bond_index = 0
        if self.main_window is None:
            self.default_dir = Path(filename).resolve().parent
            self._load_standalone_structure(self.default_dir)
        if self.manual_color_levels is None:
            self._sync_level_inputs()
        self.update_plot()

    def apply_color_levels(self):
        levels = (
            self.min_level_input.value(),
            self.max_level_input.value(),
        )

        try:
            self.manual_color_levels = self._normalize_levels(levels)
        except ValueError as error:
            QtWidgets.QMessageBox.warning(self, "Invalid levels", str(error))
            return

        self.update_plot()

    def reset_color_levels(self):
        self.manual_color_levels = None
        self._sync_level_inputs()
        self.update_plot()

    def set_color_levels(self, levels):
        self.manual_color_levels = self._normalize_levels(levels)
        self._sync_level_inputs()
        self.update_plot()

    def previous_bond(self):
        self._set_bond_index(self.current_bond_index - 1)

    def next_bond(self):
        self._set_bond_index(self.current_bond_index + 1)

    def _set_bond_index(self, index):
        if self.dataset is None:
            return

        self.current_bond_index = max(
            0,
            min(index, self.dataset.bond_count() - 1),
        )
        self.update_plot()

    def update_plot(self):
        if self.dataset is None:
            self.matrix_plots.show_empty()
            self._clear_structure_highlight()
            self._update_empty_info_label()
            self._update_navigation_buttons()
            return

        _, bond_data, bond_metadata = self.dataset.get_bond(
            self.current_bond_index
        )

        matrix_up, orbitals_1, orbitals_2 = self.matrix_builder.build(
            bond_data,
            Spin.up,
        )
        matrix_down, _, _ = self.matrix_builder.build(
            bond_data,
            Spin.down,
        )

        self.matrix_plots.update(
            matrix_up,
            matrix_down,
            orbitals_1,
            orbitals_2,
            levels=self._current_color_levels(),
        )
        self._update_info_label(bond_data, bond_metadata)
        self._update_navigation_buttons()
        self._update_structure_highlight(bond_metadata)
        QtCore.QTimer.singleShot(0, self.matrix_plots.view_all)

    def _current_color_levels(self):
        if self.manual_color_levels is not None:
            return self.manual_color_levels

        if self.dataset is not None:
            return self.dataset.color_levels

        return -1.0, 1.0

    def _sync_level_inputs(self):
        minimum, maximum = self._current_color_levels()
        self.min_level_input.setValue(minimum)
        self.max_level_input.setValue(maximum)

    @staticmethod
    def _normalize_levels(levels):
        if levels is None:
            return None

        if len(levels) != 2:
            raise ValueError("Color levels must contain exactly two values.")

        minimum, maximum = (float(levels[0]), float(levels[1]))
        if not minimum < maximum:
            raise ValueError("Minimum color level must be smaller than maximum color level.")

        return minimum, maximum

    def refresh_structure_highlight(self):
        if self.dataset is None:
            self._clear_structure_highlight()
            return

        _, _, bond_metadata = self.dataset.get_bond(self.current_bond_index)
        self._update_structure_highlight(bond_metadata)

    def _update_structure_highlight(self, bond_metadata):
        self._clear_structure_highlight(render=False)

        structure_viewer = self._structure_viewer()
        if structure_viewer is None:
            return

        coordinates = self._current_structure_coordinates(structure_viewer)
        atom_indexes = self._bond_atom_indexes(bond_metadata, structure_viewer.data)
        if coordinates is None or atom_indexes is None:
            self._render_structure_plot(structure_viewer.plotter)
            return

        atom1_index, atom2_index = atom_indexes
        if atom1_index >= len(coordinates) or atom2_index >= len(coordinates):
            self._render_structure_plot(structure_viewer.plotter)
            return

        point1 = np.asarray(coordinates[atom1_index], dtype=float)
        point2 = np.asarray(coordinates[atom2_index], dtype=float)
        point2 = point2 + self._translation_vector(bond_metadata, structure_viewer.data)

        radius = self._highlight_sphere_radius()
        actors = [
            self._create_highlight_sphere(point1, radius),
            self._create_highlight_sphere(point2, radius),
            self._create_highlight_bond(point1, point2),
        ]

        for actor in actors:
            structure_viewer.plotter.renderer.AddActor(actor)

        self.structure_highlight_actors = actors
        self._render_structure_plot(structure_viewer.plotter)

    def _clear_structure_highlight(self, render=True):
        structure_viewer = self._structure_viewer()
        plotter = getattr(structure_viewer, "plotter", None)
        renderer = getattr(plotter, "renderer", None)

        if renderer is not None:
            for actor in self.structure_highlight_actors:
                try:
                    renderer.RemoveActor(actor)
                except RuntimeError:
                    pass

        self.structure_highlight_actors = []

        if render and plotter is not None:
            self._render_structure_plot(plotter)

    def _structure_viewer(self):
        if self.main_window is not None:
            return getattr(self.main_window, "structure_plot_interactor_widget", None)

        return self.standalone_structure_viewer

    def _structure_geometry_slider(self):
        if self.main_window is not None:
            return getattr(
                getattr(self.main_window, "structure_plot_control_tab", None),
                "geometry_slider",
                None,
            )

        return getattr(self.standalone_structure_control, "geometry_slider", None)

    @staticmethod
    def _main_window_from_parent(parent):
        if hasattr(parent, "structure_plot_interactor_widget"):
            return parent

        return None

    @staticmethod
    def _resolve_show_structure(show_structure):
        if show_structure == "auto":
            return os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen"

        return bool(show_structure)

    def _load_standalone_structure(self, directory=None):
        if (
            self.main_window is not None
            or not self.show_structure
            or self.standalone_structure_container is None
        ):
            return

        structure_dir = Path(directory or self._standalone_structure_dir())
        if not self._has_structure_file(structure_dir):
            self._clear_standalone_structure()
            return

        self._clear_standalone_structure()

        try:
            from structure_controls import StructureControlsWidget
            from structure_plot import StructureViewer
            from vasp_data import VaspData

            data = VaspData(str(structure_dir), parse_doscar=False)
            structure_viewer = StructureViewer(data, parent=self)
            structure_control = StructureControlsWidget(structure_viewer, parent=self)
        except Exception as error:
            print(f"Could not load standalone structure view: {error}")
            return

        structure_control.hide()
        self.standalone_structure_viewer = structure_viewer
        self.standalone_structure_control = structure_control
        self.standalone_structure_layout.addWidget(structure_viewer)
        self.standalone_structure_container.show()
        self.plot_splitter.setSizes([1200, 600])

        slider = self._structure_geometry_slider()
        if slider is not None:
            slider.valueChanged.connect(lambda _value: self.refresh_structure_highlight())

    def _clear_standalone_structure(self):
        if self.standalone_structure_viewer is None:
            return

        self._clear_structure_highlight(render=False)

        self.standalone_structure_layout.removeWidget(self.standalone_structure_viewer)
        self.standalone_structure_viewer.setParent(None)
        self.standalone_structure_viewer.deleteLater()

        if self.standalone_structure_control is not None:
            self.standalone_structure_control.setParent(None)
            self.standalone_structure_control.deleteLater()

        self.standalone_structure_viewer = None
        self.standalone_structure_control = None

        if self.standalone_structure_container is not None:
            self.standalone_structure_container.hide()

    def _standalone_structure_dir(self):
        if self.dataset is not None and getattr(self.dataset, "filename", None):
            return Path(self.dataset.filename).resolve().parent

        return self.default_dir

    @staticmethod
    def _has_structure_file(directory):
        directory = Path(directory)
        return any((directory / filename).is_file() for filename in ("CONTCAR", "POSCAR"))

    def _current_structure_coordinates(self, structure_viewer):
        data = structure_viewer.data
        coordinates_by_step = getattr(data, "outcar_coordinates", None)

        if coordinates_by_step is not None and len(coordinates_by_step) > 0:
            slider = self._structure_geometry_slider()
            index = slider.value() if slider is not None else 0
            index = max(0, min(index, len(coordinates_by_step) - 1))
            return np.asarray(coordinates_by_step[index], dtype=float)

        for attribute in ("coordinates", "init_coordinates"):
            coordinates = getattr(data, attribute, None)
            if coordinates is not None:
                return np.asarray(coordinates, dtype=float)

        return None

    def _bond_atom_indexes(self, bond_metadata, data):
        atom_labels = getattr(data, "atoms_symb_and_num", [])
        atom1_index = self._atom_index_from_label(bond_metadata.get("atom1"), atom_labels)
        atom2_index = self._atom_index_from_label(bond_metadata.get("atom2"), atom_labels)

        if atom1_index is None or atom2_index is None:
            return None

        return atom1_index, atom2_index

    @staticmethod
    def _atom_index_from_label(atom_label, atom_labels):
        if atom_label is None:
            return None

        if isinstance(atom_label, (int, np.integer)):
            if 1 <= atom_label <= len(atom_labels):
                return atom_label - 1
            if 0 <= atom_label < len(atom_labels):
                return atom_label
            return None

        label = str(atom_label).strip().replace(" ", "")
        if not label:
            return None

        normalized_labels = {
            str(atom).strip().replace(" ", ""): index
            for index, atom in enumerate(atom_labels)
        }
        if label in normalized_labels:
            return normalized_labels[label]

        lower_labels = {atom.lower(): index for atom, index in normalized_labels.items()}
        if label.lower() in lower_labels:
            return lower_labels[label.lower()]

        match = re.search(r"(\d+)$", label)
        if match is None:
            return None

        atom_index = int(match.group(1)) - 1
        if 0 <= atom_index < len(atom_labels):
            return atom_index

        return None

    @staticmethod
    def _translation_vector(bond_metadata, data):
        translation = bond_metadata.get("translation", (0, 0, 0))
        try:
            translation = np.asarray(translation, dtype=float)
        except (TypeError, ValueError):
            return np.zeros(3, dtype=float)

        if translation.shape != (3,):
            return np.zeros(3, dtype=float)

        vectors = getattr(data, "unit_cell_vectors", None)
        if callable(vectors):
            vectors = vectors()
        if vectors is None and getattr(data, "poscar", None) is not None:
            vectors = data.poscar.unit_cell_vectors()

        if vectors is None:
            return np.zeros(3, dtype=float)

        try:
            return translation @ np.asarray(vectors, dtype=float)
        except ValueError:
            return np.zeros(3, dtype=float)

    def _highlight_sphere_radius(self):
        structure_control = getattr(self.main_window, "structure_plot_control_tab", None)
        radius = getattr(structure_control, "sphere_radius", None)
        if radius is None:
            structure_viewer = self._structure_viewer()
            radius = getattr(structure_viewer, "sphere_radius", 0.5)

        return max(float(radius) * 1.45, 0.2)

    @staticmethod
    def _create_highlight_sphere(point, radius):
        sphere_source = vtkSphereSource()
        sphere_source.SetRadius(radius)
        sphere_source.SetCenter(float(point[0]), float(point[1]), float(point[2]))
        sphere_source.SetThetaResolution(32)
        sphere_source.SetPhiResolution(32)
        sphere_source.Update()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(sphere_source.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(0.0, 0.9, 0.0)
        prop.SetSpecular(0.45)
        prop.SetSpecularPower(18)
        prop.SetAmbient(0.35)
        prop.SetDiffuse(0.7)
        prop.SetInterpolationToPhong()
        return actor

    @staticmethod
    def _create_highlight_bond(point1, point2):
        line_source = vtkLineSource()
        line_source.SetPoint1(float(point1[0]), float(point1[1]), float(point1[2]))
        line_source.SetPoint2(float(point2[0]), float(point2[1]), float(point2[2]))
        line_source.Update()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(line_source.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.0, 0.9, 0.0)
        actor.GetProperty().SetLineWidth(10)
        return actor

    @staticmethod
    def _render_structure_plot(plotter):
        if hasattr(plotter, "render"):
            plotter.render()
            return

        plotter.renderer.Render()

    def open_cohpcar_for_interaction(self, interaction_key):
        if self.dataset is None:
            return

        bond_key, _, _ = self.dataset.get_bond(self.current_bond_index)

        try:
            from lobster.cohpcar_viewer import open_cohpcar_window
        except ImportError:
            from cohpcar_viewer import open_cohpcar_window

        window = open_cohpcar_window(
            default_dir=self.default_dir,
            selected_bond_key=str(bond_key),
            selected_interactions=[interaction_key],
        )
        self.cohpcar_plot_windows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _update_info_label(self, bond_data, bond_metadata):
        total_icohp = bond_metadata["total_icohp"]
        self.info_label.setText(
            f"Bond {bond_metadata['atom_pair']}      "
            f"Length: {bond_data['length']:.4f} \u00c5      "
            f"Equivalent bonds: {bond_data['number_of_bonds']}      "
            f"Total ICOHP up: {self._format_spin_icohp(total_icohp, Spin.up)}      "
            f"Total ICOHP down: {self._format_spin_icohp(total_icohp, Spin.down)}"
        )

    def _update_empty_info_label(self):
        if self.load_error:
            self.info_label.setText(self.load_error)
            return

        self.info_label.setText("No ICOHPLIST data loaded")

    @staticmethod
    def _format_spin_icohp(total_icohp, spin):
        if not isinstance(total_icohp, dict) or spin not in total_icohp:
            return "n/a"

        return f"{total_icohp[spin]:.4f}"

    def _update_navigation_buttons(self):
        if self.dataset is None:
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        self.previous_button.setEnabled(self.current_bond_index > 0)
        self.next_button.setEnabled(
            self.current_bond_index < self.dataset.bond_count() - 1
        )

    def closeEvent(self, event):
        self._clear_structure_highlight()
        super().closeEvent(event)


def get_initial_icohplist_filename():
    local_filename = Path.cwd() / LOCAL_ICOHPLIST_FILENAME

    if local_filename.is_file():
        return str(local_filename)

    return ICOHPLIST_FILENAME


def load_initial_dataset():
    filename = get_initial_icohplist_filename()

    try:
        return IcohpDataset(filename), None
    except Exception as error:
        return None, f"Could not load {filename}: {error}"


def main():
    app = QtWidgets.QApplication(sys.argv)
    dataset, load_error = load_initial_dataset()
    window = IcohpMatrixViewer(dataset, load_error)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
