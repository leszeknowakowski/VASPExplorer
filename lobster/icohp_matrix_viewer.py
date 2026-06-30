import sys
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets
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
    (0.3, (105, 189, 170, 255)),
    (0.4, (223, 243, 160, 255)),
    (0.5, (255, 255, 255, 255)),
    (0.6, (253, 200, 120, 255)),
    (0.7, (230, 89, 73, 255)),
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
                    "total_icohp": {},
                }
                for bond_key in self.bond_keys
            ]

        atom1_list = getattr(collection, "_list_atom1", [])
        atom2_list = getattr(collection, "_list_atom2", [])
        total_icohp_list = getattr(collection, "_list_icohp", [])

        metadata = []

        for index, bond_key in enumerate(self.bond_keys):
            atom1 = self._get_list_value(atom1_list, index, str(bond_key))
            atom2 = self._get_list_value(atom2_list, index, "")
            total_icohp = self._get_list_value(total_icohp_list, index, {})

            metadata.append(
                {
                    "atom_pair": self._format_atom_pair(atom1, atom2),
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
    ):
        super().__init__(parent)
        self.dataset = dataset
        self.load_error = load_error
        self.default_dir = Path(default_dir or getattr(parent, "dir", Path.cwd()))
        self.matrix_builder = OrbitalMatrixBuilder()
        self.current_bond_index = 0
        self.manual_color_levels = self._normalize_levels(levels)

        self._setup_window()
        self._setup_controls()
        self._setup_graphics()
        self._connect_signals()
        self.cohpcar_plot_windows = []
        self._sync_level_inputs()
        self.update_plot()

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
        self.main_layout.addWidget(self.info_label)

    def _setup_graphics(self):
        self.graphics = pg.GraphicsLayoutWidget()
        self.main_layout.insertWidget(1, self.graphics)
        self.matrix_plots = SpinMatrixPlots(self.graphics)

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
            self.update_plot()
            QtWidgets.QMessageBox.warning(self, "Load failed", self.load_error)
            return

        self.dataset = dataset
        self.load_error = None
        self.current_bond_index = 0
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
