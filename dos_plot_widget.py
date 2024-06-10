import time

if True:
    tic = time.perf_counter()
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter, QHBoxLayout
    toc = time.perf_counter()
    print(f'import PyQt5.QtWidgets in DOSplot: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from PyQt5 import QtCore
    toc = time.perf_counter()
    print(f'import PyQt5.QtCore in DOSplot: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import pyqtgraph as pg
    from pyqtgraph.graphicsItems.PlotDataItem import PlotDataItem
    toc = time.perf_counter()
    print(f'import pyqtgraph in DOSplot: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import re
    toc = time.perf_counter()
    print(f'import re in DOSplot: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import numpy as np
    toc = time.perf_counter()
    print(f'import numpy in DOSplot: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import sys
    toc = time.perf_counter()
    print(f'import sys in DOSplot: {toc - tic:0.4f}')


class DosPlotWidget(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.initUI()
        self.legend = []

    def initUI(self):
        self.layout = QVBoxLayout(self)

        plot_splitter = QSplitter(QtCore.Qt.Horizontal)
        self.full_range_plot = pg.PlotWidget()
        self.full_range_plot.setBackground('w')
        self.bounded_plot = pg.PlotWidget()
        self.bounded_plot.setBackground('w')

        plot_splitter.addWidget(self.full_range_plot)
        plot_splitter.addWidget(self.bounded_plot)
        plot_splitter.setStretchFactor(0, 2)
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
        items = [item for item in plot_widget.listDataItems() if isinstance(item, pg.PlotDataItem) and not isinstance(item, MergedPlotDataItem)]
        for item in items:
            plot_widget.removeItem(item)

    def clear_merged_plot(self):
        for plot in [self.full_range_plot, self.bounded_plot]:
            for item in [item for item in plot.listDataItems() if isinstance(item, MergedPlotDataItem)]:
                plot.removeItem(item)
        self.legend.clear()


    def update_plot(self, data, selected_atoms, selected_orbitals, ):
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

    def create_label(self, orbital_up, orbital_down, atom_no_up, atom_no_down):
        def number_range(lst):
            '''returns a string representing a range of numbers, eg. 1-4,5,10-11'''
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
        dataset_up = np.array(self.data.data_up)
        dataset_down = np.array(self.data.data_down)
        dataset_up =  dataset_up[np.ix_(selected_atoms,selected_orbitals,range(self.data.nedos))]
        dataset_down =  dataset_down[np.ix_(selected_atoms,selected_orbitals,range(self.data.nedos))]
        merged_data_up = np.sum(dataset_up, axis=(1,0))
        merged_data_down = np.sum(dataset_down, axis=(1,0))
        return merged_data_up, merged_data_down

    def plot_merged(self, selected_atoms, selected_orbitals, nrg, label, color):
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
        #self.legend.clear()
        #for index, item in enumerate(self.bounded_plot.listDataItems()):
        #    if index % 2 == 0:
        #       self.legend.addItem(item, label)
        self.legend.addItem(self.bounded_plot.listDataItems()[-1], label)

    def show_all_saved_plots(self, saved_plots, nrg):
        self.saved_plots_window = MergedPlotWindow(saved_plots, nrg)
        self.saved_plots_window.show()


class MergedPlotWindow(QWidget):
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

