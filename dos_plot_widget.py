from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PyQt5 import QtCore
import pyqtgraph as pg

class DosPlotWidget(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)

        plot_splitter = QSplitter(QtCore.Qt.Horizontal)
        self.full_range_plot = pg.PlotWidget()
        self.full_range_plot.setBackground('w')
        self.bounded_plot = pg.PlotWidget()
        self.bounded_plot.setBackground('w')

        plot_splitter.addWidget(self.full_range_plot)
        plot_splitter.addWidget(self.bounded_plot)
        plot_splitter.setStretchFactor(0, 3)
        plot_splitter.setStretchFactor(1, 3)

        self.layout.addWidget(plot_splitter)

        # Add LinearRegionItem to the full range plot
        self.region = pg.LinearRegionItem(orientation=pg.LinearRegionItem.Horizontal, brush=pg.mkBrush(255, 235, 14, 100))
        self.full_range_plot.addItem(self.region)
        self.region.sigRegionChanged.connect(self.update_bounded_plot_y_range)

        self.bounded_plot.sigRangeChanged.connect(self.update_region_from_bounded_plot)

        self.region.setRegion([-5, 5])

        self.inf_line_full = pg.InfiniteLine(pos=float(self.data.e_fermi), angle=0, pen=pg.mkPen('b'), movable=False, label='E_Fermi={value:0.2f}', labelOpts={'position': 0.1, 'color': (0, 0, 255), 'fill': (0, 0, 255, 100), 'movable': True})
        self.inf_line_bounded = pg.InfiniteLine(pos=float(self.data.e_fermi), angle=0, pen=pg.mkPen('b'), movable=False, label='E_Fermi={value:0.2f}', labelOpts={'position': 0.1, 'color': (0, 0, 255), 'fill': (0, 0, 255, 100), 'movable': True})

        self.full_range_plot.addItem(self.inf_line_full)
        self.bounded_plot.addItem(self.inf_line_bounded)

    def update_bounded_plot_y_range(self):
        min_y, max_y = self.region.getRegion()
        self.bounded_plot.setYRange(min_y, max_y, padding=0)

    def update_region_from_bounded_plot(self):
        view_range = self.bounded_plot.viewRange()[1]
        self.region.setRegion(view_range)

    def clear_plot_data(self, plot_widget):
        items = [item for item in plot_widget.listDataItems() if isinstance(item, pg.PlotDataItem)]
        for item in items:
            plot_widget.removeItem(item)


    def update_plot(self, data, selected_atoms, selected_orbitals):
        self.clear_plot_data(self.full_range_plot)
        self.clear_plot_data(self.bounded_plot)
        colors = ['b', 'r', 'g', 'c', 'm', 'y', 'k', 'b', 'r', 'g', 'c', 'm', 'y', 'k', 'b', 'r', 'g', 'c', 'm', 'y',
                  'k']  # Add more colors if needed
        dataset_up = data.data_up
        dataset_down = data.data_down
        nrg = data.doscar.total_dos_energy
        for atom_index in selected_atoms:
            for orbital_index in selected_orbitals:
                plot_color = colors[orbital_index]  # Cycle through colors
                plot_data = dataset_up[atom_index][orbital_index]
                self.full_range_plot.plot(plot_data, nrg, pen=pg.mkPen(plot_color))
                self.bounded_plot.plot(plot_data, nrg, pen=pg.mkPen(plot_color))

        # plot dataset down
        for atom_index in selected_atoms:
            for orbital_index in selected_orbitals:
                plot_color = colors[orbital_index]  # Cycle through colors
                plot_data = dataset_down[atom_index][orbital_index]
                self.full_range_plot.plot([-x for x in plot_data], nrg,
                                          pen=pg.mkPen(plot_color))
                self.bounded_plot.plot([-x for x in plot_data], nrg,
                                       pen=pg.mkPen(plot_color))

        self.update_bounded_plot_y_range()

    def update_total_dos_plot(self, datasetup, datasetdown, nrg):
        self.clear_plot_data(self.full_range_plot)
        self.clear_plot_data(self.bounded_plot)
        self.full_range_plot.plot(datasetup, nrg, pen=pg.mkPen('b'))
        self.bounded_plot.plot(datasetup, nrg, pen=pg.mkPen('b'))

        self.full_range_plot.plot([-x for x in datasetdown], nrg, pen=pg.mkPen('b'))
        self.bounded_plot.plot([-x for x in datasetdown], nrg, pen=pg.mkPen('b'))
