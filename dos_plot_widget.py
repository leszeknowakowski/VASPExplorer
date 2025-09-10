import time

if True:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter, QHBoxLayout
    from PyQt5 import QtCore
    import pyqtgraph as pg
    from pyqtgraph.graphicsItems.PlotDataItem import PlotDataItem
    import re
    import numpy as np
    import sys
    from itertools import cycle

from pymatgen.electronic_structure.core import Spin

class DosPlotWidget(QWidget):
    """
    A widget for plotting Density of States (DOS) data using PyQt and pyqtgraph.

    Attributes:
        data:
            The dataset containing DOS information for plotting.
        legend:
            A list to hold legend items for the plot.
    """
    PLOT_LINEWIDTH=2.5
    def __init__(self, data):
        """
        Initializes the DosPlotWidget with the provided DOS data.

        Args:
            data: A data object containing DOS information and Fermi energy.
        """
        super().__init__()
        self.data = data
        self.initUI()
        self.legend = []

    def initUI(self):
        """
        Sets up the user interface for the DOS plot widget, including
        layout, plots, region selection, and Fermi level lines.
        """
        self.layout = QVBoxLayout(self)

        # splitter for two parts of plot (original and zoomed  (bounded))
        plot_splitter = QSplitter(QtCore.Qt.Horizontal)
        self.full_range_plot = pg.PlotWidget()
        self.bounded_plot = pg.PlotWidget()
        plot_splitter.addWidget(self.full_range_plot)
        plot_splitter.addWidget(self.bounded_plot)
        plot_splitter.setStretchFactor(0, 2)
        plot_splitter.setStretchFactor(1, 3)

        self.layout.addWidget(plot_splitter)

        # Add LinearRegionItem to the full range plot
        self.region = pg.LinearRegionItem(orientation=pg.LinearRegionItem.Horizontal, pen=pg.mkPen('w'))
        self.full_range_plot.addItem(self.region)
        self.region.sigRegionChanged.connect(self.update_bounded_plot_y_range)
        self.bounded_plot.sigRangeChanged.connect(self.update_region_from_bounded_plot)
        self.region.setRegion([-5, 5])

        # fermi enerfy lines
        self.inf_line_full = pg.InfiniteLine(pos=float(self.data.e_fermi),
                                             angle=0,
                                             pen=pg.mkPen(color='#6ab4dc', width=4),
                                             movable=False, label='E_Fermi={value:0.2f}',
                                             labelOpts={'position': 0.1,
                                                        'color': '#cbcdd2',
                                                        'fill': (0, 0, 255, 100),
                                                        'movable': True}
                                             )
        self.inf_line_bounded = pg.InfiniteLine(pos=float(self.data.e_fermi),
                                                angle=0,
                                                pen=pg.mkPen(color='#6ab4dc', width=4),
                                                movable=False,
                                                label='E_Fermi={value:0.2f}',
                                                labelOpts={'position': 0.1,
                                                           'color': '#cbcdd2',
                                                           'fill': (0, 0, 255, 100),
                                                           'movable': True}
                                                )

        self.full_range_plot.addItem(self.inf_line_full)
        self.bounded_plot.addItem(self.inf_line_bounded)

    def update_data(self, data):
        self.data = data

    def update_bounded_plot_y_range(self):
        """
         Updates the y-axis range of the bounded plot based on the selected region
         in the full range plot.
        """
        min_y, max_y = self.region.getRegion()
        self.bounded_plot.setYRange(min_y, max_y, padding=0)

    def update_region_from_bounded_plot(self):
        """
          Updates the selection region in the full range plot based on the
          y-axis range of the bounded plot.
        """
        view_range = self.bounded_plot.viewRange()[1]
        self.region.setRegion(view_range)

    def clear_plot_data(self, plot_widget):
        """
        Removes plot data items from the specified plot widget.

        Args:
            plot_widget: The plot widget from which to remove data items (full_range_plot or bounded_plot)
        """
        items = [item for item in plot_widget.listDataItems() if isinstance(item, pg.PlotDataItem) and not isinstance(item, MergedPlotDataItem)]
        for item in items:
            plot_widget.removeItem(item)

    def clear_merged_plot(self):
        """
        Clears merged plot data from both the full and bounded plots.
        """
        for plot in [self.full_range_plot, self.bounded_plot]:
            for item in [item for item in plot.listDataItems() if isinstance(item, MergedPlotDataItem) or isinstance(item, pg.graphicsItems.PlotDataItem.PlotDataItem)]:
                plot.removeItem(item)
        self.legend.clear()

    def plot_separate(self, nrg, data, selected_atoms, selected_orbitals):
        """
        Updates the DOS plots with data for specified atoms and orbitals.
        Clears both plots first, then adds selected atoms and orbitals.
        """

        colors = [
            "#FF6B6B", "#FFD93D", "#6BCB77", "#4D96FF", "#F38BA0",
            "#6A4C93", "#FFA41B", "#00CFC1", "#E4572E", "#9D4EDD"
        ]
        spin_configs = [
            (Spin.up, 1, True),  # normal, add label to legend
            (Spin.down, -1, False)  # inverted, no label (avoid duplicates)
        ]

        self.full_range_plot.addLegend()
        color_gen = cycle(colors)

        for atom_index in selected_atoms:
            atom_name = self.data.atoms_symb_and_num[atom_index]
            atom_data = data[atom_index]  # dict: orbital_name -> {Spin.up: arr, Spin.down: arr}

            for orbital_name in selected_orbitals:
                orbital_data = atom_data[orbital_name]

                # Assign a single color per atom/orbital (shared for up/down)
                plot_color = next(color_gen)
                pen = pg.mkPen(plot_color, width=self.PLOT_LINEWIDTH)
                pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)

                for spin, sign, add_label in spin_configs:
                    if not orbital_data:
                        pass
                    else:
                        spin_data = orbital_data[spin]
                        if spin_data[0] == 'empty':
                            pass
                        else:
                            spin_data = spin_data * sign
                            label = f'{atom_name}_{orbital_name}' if add_label else None
                            for plot in (self.full_range_plot, self.bounded_plot):
                                plot.plot(spin_data, nrg, pen=pen, name=label)

        self.update_bounded_plot_y_range()

    def update_total_dos_plot(self, datasetup, datasetdown, nrg):
        """
        Updates plot to display total DOS data for spin-up and spin-down datasets.
        Used only in DosControlWidget class

        Args:
            datasetup:
                DOS data for spin-up states.
            datasetdown:
                DOS data for spin-down states.
            nrg:
                Array of energy values for the DOS.
        """
        self.clear_plot_data(self.full_range_plot)
        self.clear_plot_data(self.bounded_plot)
        self.full_range_plot.plot(datasetup, nrg, pen=pg.mkPen('b'))
        self.bounded_plot.plot(datasetup, nrg, pen=pg.mkPen('b'))

        self.full_range_plot.plot([-x for x in datasetdown], nrg, pen=pg.mkPen('b'))
        self.bounded_plot.plot([-x for x in datasetdown], nrg, pen=pg.mkPen('b'))

    def create_label(self, orbital_up, orbital_down, atom_no_up, atom_no_down):
        """
        Creates a formatted label describing the selected orbitals and atoms.

        Args:
            orbital_up:
                List of selected orbitals for spin-up.
            orbital_down:
                List of selected orbitals for spin-down.
            atom_no_up:
                List of selected atom numbers for spin-up.
            atom_no_down:
                List of selected atom numbers for spin-down.

        Returns:
            str: A formatted label string summarizing the selection.
        """
        def number_range(lst):
            """returns a string representing a range of numbers, eg. 1-4,5,10-11"""
            result = []
            i = 0
            while i < len(lst):
                start = lst[i]
                end = start
                while i + 1 < len(lst) and lst[i + 1] - lst[i] == 1:
                    end = lst[i + 1]
                    i += 1
                if start == end:
                    result.append(str(start))
                else:
                    result.append(f"{start}-{end}")
                i += 1
            string_result = ",".join(result) + ","
            return " many atoms!," if len(string_result) > 20 else string_result

        # join list of up and down spin
        orblst = sorted(set(orbital_down + orbital_up))
        atomlst = sorted(set(atom_no_down + atom_no_up), key=lambda x: (
        re.match(r'\D+', x).group(), int(re.match(r'\d+', x[len(re.match(r'\D+', x).group()):]).group())))
        lst = [orblst, atomlst]

        flattened_lst = [item for sublist in lst for item in sublist]

        count_orb_in_label = [sum(1 for item in flattened_lst if item.startswith(prefix)) for prefix in ["s", "p", "d", "f"]]


        orblbl = []
        if count_orb_in_label[0] == 1:
            orblbl.append('s')
        if count_orb_in_label[1] == 3:
            orblbl.append('p')
        else:
            orblbl.extend([orb for orb in lst[0] if orb.startswith('p')])

        if count_orb_in_label[2] == 5:
            orblbl.append('d')
        elif count_orb_in_label[2] > 2:
            orblbl.append('many d')
        else:
            orblbl.extend([orb for orb in lst[0] if orb.startswith('d')])

        if count_orb_in_label[3] == 7:
            orblbl.append('f')
        elif count_orb_in_label[3] > 3:
            orblbl.append('many f')
        else:
            orblbl.extend([orb for orb in lst[0] if orb.startswith('f')])

        atomlst_group = {}
        for atom in lst[1]:
            key = re.match(r'\D+', atom).group()
            if key in atomlst_group:
                atomlst_group[key].append(int(re.match(r'\d+', atom[len(key):]).group()))
            else:
                atomlst_group[key] = [int(re.match(r'\d+', atom[len(key):]).group())]

        atomlbl = [f"{key}{number_range(sorted(values))}" for key, values in atomlst_group.items()]

        merged_label = atomlbl + orblbl
        joined_label = " ".join(merged_label)
        print(joined_label)
        return joined_label

    def sum_data_to_merge(self, selected_atoms, selected_orbitals):
        """
        Sums DOS data for selected atoms and orbitals, preparing for merged plot display.

        Args:
            selected_atoms:
                List of Indices of selected atoms.
            selected_orbitals:
                List of Indices of selected orbitals.

        Returns:
            tuple: Merged DOS data for spin-up and spin-down.
        """
        dataset_up = np.array(self.data.data_up)
        dataset_down = np.array(self.data.data_down)
        dataset_up =  dataset_up[np.ix_(selected_atoms,selected_orbitals,range(self.data.nedos))]
        dataset_down =  dataset_down[np.ix_(selected_atoms,selected_orbitals,range(self.data.nedos))]
        merged_data_up = np.sum(dataset_up, axis=(1,0))
        merged_data_down = np.sum(dataset_down, axis=(1,0))
        return merged_data_up, merged_data_down

    def plot_merged(self, selected_atoms, selected_orbitals, nrg, label, color):
        """
        Plots merged DOS data for selected atoms and orbitals in specified color.

        Args:
            selected_atoms:
                List of atom indices for merging.
            selected_orbitals:
                List of orbital indices for merging.
            nrg:
                Array of energy values for DOS.
            label:
                Label for the legend.
            color:
                Color for the merged plot line.
        """
        merged_data_up, merged_data_down = self.sum_data_to_merge(selected_atoms,
                                                                              selected_orbitals)

        self.clear_plot_data(self.full_range_plot)
        self.clear_plot_data(self.bounded_plot)

        merged_item_up_full = MergedPlotDataItem(merged_data_up, nrg,pen=pg.mkPen(color))
        merged_item_up_bound = MergedPlotDataItem(merged_data_up, nrg,pen=pg.mkPen(color))

        self.full_range_plot.addItem(merged_item_up_full)
        self.bounded_plot.addItem(merged_item_up_bound)

        merged_item_down_full = MergedPlotDataItem([-x for x in merged_data_down], nrg, pen=pg.mkPen(color))
        merged_item_down_bound = MergedPlotDataItem([-x for x in merged_data_down], nrg, pen=pg.mkPen(color))
        self.full_range_plot.addItem(merged_item_down_full)
        self.bounded_plot.addItem(merged_item_down_bound)

        if self.legend == []:
            self.legend = pg.LegendItem((80,60), offset=(-20,-50))
            self.legend.setParentItem(self.bounded_plot.getPlotItem())
        self.legend.addItem(self.bounded_plot.listDataItems()[-1], label)

    def show_all_saved_plots(self, saved_plots, nrg):
        """
        Displays all saved DOS plots in a separate window.

        Args:
            saved_plots:
                List of saved plots to display.
            nrg:
                Array of energy values for DOS.
        """
        self.saved_plots_window = MergedPlotWindow(saved_plots, nrg)
        self.saved_plots_window.show()


class MergedPlotWindow(QWidget):
    """
    A window to display saved DOS plots in separate widgets.

    Attributes:
        saved_plots:
            List of saved plots to be displayed.
        nrg:
            Energy values associated with DOS data.
    """
    def __init__(self, saved_plots, nrg):
        super().__init__()

        self.setWindowTitle("Plot Window")
        self.setGeometry(200, 200, 800, 600)

        layout = QHBoxLayout()
        self.setLayout(layout)


        for data in saved_plots:
            picked_plot = pg.PlotWidget()
            picked_plot.setBackground('w')
            up = picked_plot.plot(data[0], nrg, pen=pg.mkPen(data[3]), name=data[2])
            picked_plot.plot(data[1], nrg,pen=pg.mkPen(data[3]), name=data[2])
            legend = pg.LegendItem((80, 60), offset=(70, 20))
            legend.setParentItem(picked_plot.getPlotItem())
            legend.addItem(up, name=data[2])

            layout.addWidget(picked_plot)

class MergedPlotDataItem(PlotDataItem):
    """
    A Class for plots which data is merged.
    Used to check instances and clear only merged plots
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

