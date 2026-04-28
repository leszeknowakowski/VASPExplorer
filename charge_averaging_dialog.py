import numpy as np
import pyqtgraph as pg

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton
)


# =========================================================
# PHYSICAL AVERAGING FUNCTIONS
# =========================================================

def axis_average_real(data, lattice_vectors, axis):
    """
    Axis averaging with real spatial coordinate.

    axis:
        0 = along a
        1 = along b
        2 = along c
    """

    # average over the other two axes
    avg = np.mean(data, axis=tuple(i for i in range(3) if i != axis))

    # length of lattice vector
    vec = lattice_vectors[axis]
    length = np.linalg.norm(vec)

    npts = data.shape[axis]

    coords = np.linspace(0, length, npts)

    return coords, avg


def plane_average_real(data, lattice_vectors, axis):
    """
    Plane averaging with correct physical scaling.

    axis = axis perpendicular to plane
    """

    plane = np.mean(data, axis=axis)

    axes = [0, 1, 2]
    axes.remove(axis)

    vec1 = lattice_vectors[axes[0]]
    vec2 = lattice_vectors[axes[1]]

    L1 = np.linalg.norm(vec1)
    L2 = np.linalg.norm(vec2)

    return plane, (L1, L2)


# =========================================================
# DIALOG
# =========================================================

class ChargeAveragingDialog(QDialog):

    def __init__(self, parent):
        super().__init__(parent)

        self.parent_widget = parent

        self.setWindowTitle("Charge Density Averaging")
        self.resize(900, 650)
        self.current_colormap_name = 'viridis'
        main_layout = QVBoxLayout()

        # ================= CONTROLS =================

        controls = QHBoxLayout()

        # CHGCAR selector
        self.data_combo = QComboBox()
        self.data_combo.addItems(parent.chgcar_data.keys())

        # Channel selector
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["total", "spin", "alfa", "beta"])

        # Mode selector
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Axis average", "Plane average"])

        # Axis selector
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["X", "Y", "Z"])

        self.plot_btn = QPushButton("Plot")

        controls.addWidget(QLabel("Data:"))
        controls.addWidget(self.data_combo)

        controls.addWidget(QLabel("Channel:"))
        controls.addWidget(self.channel_combo)

        controls.addWidget(QLabel("Mode:"))
        controls.addWidget(self.mode_combo)

        controls.addWidget(QLabel("Axis:"))
        controls.addWidget(self.axis_combo)

        controls.addWidget(self.plot_btn)

        main_layout.addLayout(controls)

        # ================= PLOT AREA =================

        self.plot_widget = pg.GraphicsLayoutWidget()
        main_layout.addWidget(self.plot_widget)

        self.setLayout(main_layout)

        self.plot_btn.clicked.connect(self.make_plot)

    # =====================================================
    # GET DATA FROM YOUR EXISTING STRUCTURE
    # =====================================================

    def get_volumetric_data(self, path, channel):
        data_obj = self.parent_widget.chgcar_data[path]

        if channel == "total":
            return data_obj.chop(data_obj.all_numbers[0], 1)

        elif channel == "spin":
            return data_obj.chop(data_obj.all_numbers[1], 1)

        elif channel == "alfa":
            if data_obj.alfa is None:
                data_obj.calc_alfa_beta()
            return data_obj.alfa

        elif channel == "beta":
            if data_obj.beta is None:
                data_obj.calc_alfa_beta()
            return data_obj.beta

        return None

    # =====================================================
    # MAIN PLOTTING FUNCTION
    # =====================================================

    def make_plot(self):

        self.plot_widget.clear()

        path = self.data_combo.currentText()
        channel = self.channel_combo.currentText()
        mode = self.mode_combo.currentText()
        axis = self.axis_combo.currentIndex()

        data_obj = self.parent_widget.chgcar_data[path]

        data = self.get_volumetric_data(path, channel)
        lattice = data_obj._unit_cell_vectors

        if data is None:
            return

        # ================= AXIS AVERAGE =================

        if mode == "Axis average":

            coords, avg = axis_average_real(data, lattice, axis)

            plot = self.plot_widget.addPlot()
            plot.plot(coords, avg, pen='y')

            plot.setLabel('bottom', "Distance (Å)")
            plot.setLabel('left', "Average charge density")

            plot.showGrid(x=True, y=True)

        # ================= PLANE AVERAGE =================

        else:

            # plane, Lx, Ly from plane_average_real(...)
            plane, (Lx, Ly) = plane_average_real(data, lattice, axis)

            # Clear previous plot
            self.plot_widget.clear()

            # Create a ViewBox for the image
            view = self.plot_widget.addViewBox()
            view.setAspectLocked(True)

            # Image item
            img = pg.ImageItem(plane.T, axisOrder='row-major')
            img.setRect(0, 0, Lx, Ly)
            view.addItem(img)

            # Create color bar
            colormap = pg.colormap.get(self.current_colormap_name)
            colormapmenu = pg.ColorMapMenu(showColorMapSubMenus=True, showGradientSubMenu=True)
            bar = pg.ColorBarItem(colorMap=colormap, colorMapMenu=colormapmenu)
            bar.setImageItem(img)

            # Add colorbar to the right of the plot
            self.plot_widget.addItem(bar)

            def on_colormap_changed():
                # get current colormap from colorbar
                cmap = bar.colorMap()
                # gradient.colorMap().name gives the string name if available
                if hasattr(cmap, "name") and cmap.name:
                    self.current_colormap_name = cmap.name

            bar.colorMapMenu.sigColorMapTriggered.connect(on_colormap_changed)
