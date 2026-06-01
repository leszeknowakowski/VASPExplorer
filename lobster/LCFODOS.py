import os
import re
import sys
import numpy as np
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QScrollArea, QMessageBox
)
from PyQt5 import QtCore

import pyqtgraph as pg

from lobster.lobster_outputs import Doscar as DOSCAR
from pymatgen.core.periodic_table import Element
from pymatgen.electronic_structure.core import Spin
from dos_plot_widget import DosPlotWidget


class _DosDataShim:
    """Minimal stand-in so DosPlotWidget can be built before a DOSCAR is loaded.
    Lobster DOSCAR energies are already shifted so Efermi sits at 0."""
    def __init__(self, e_fermi=0.0):
        self.e_fermi = e_fermi


class DosWindow(QMainWindow):
    Z_ENTITY_PATTERN = re.compile(r"^\s*Z\s*=\s*(\d+)\s*$")

    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent
        if self.parent is not None:
            os.chdir(self.parent.dir)
        self.setWindowTitle("LOBSTER DOS Viewer")

        self.doscar = None
        self.entity_names = []
        self.entity_boxes = []
        self.orbital_boxes = []
        self.weighted_mean_lines = []
        self.dos_threshold_regions = []
        self.current_dos_threshold_intervals = {}
        self.current_weighted_means = {}
        self.updating_overlay_spans = False
        self.show_weighted_mean_on_plot = True

        self.dos_plot = DosPlotWidget(_DosDataShim(e_fermi=0.0))
        self.dos_plot.full_range_plot.addLegend()
        self.dos_plot.bounded_plot.addLegend()
        self.dos_plot.region.sigRegionChanged.connect(self.refresh_weighted_mean)
        self.dos_plot.full_range_plot.getViewBox().sigXRangeChanged.connect(self.update_overlay_spans)
        self.dos_plot.bounded_plot.getViewBox().sigXRangeChanged.connect(self.update_overlay_spans)

        load_button = QPushButton("Load DOSCAR.LCFO.lobster")
        load_button.clicked.connect(lambda: self.load_file(filename=None))

        plot_button = QPushButton("Plot")
        plot_button.clicked.connect(self.plot_selected)

        self.weighted_mean_toggle = QPushButton("Mean values on plot: On")
        self.weighted_mean_toggle.setCheckable(True)
        self.weighted_mean_toggle.setChecked(True)
        self.weighted_mean_toggle.clicked.connect(self.toggle_weighted_mean_on_plot)

        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(self.export_csv)

        export_pdf = QPushButton("Export PDF")
        export_pdf.clicked.connect(lambda: self.dos_plot.export_to_pdf(self.dos_plot.bounded_plot))

        self.weighted_mean_label = QLabel("Weighted mean: select one entity and at least one orbital")
        self.weighted_mean_label.setWordWrap(True)

        # Scroll areas
        self.entity_widget = QWidget()
        self.entity_layout = QVBoxLayout(self.entity_widget)

        self.orbital_widget = QWidget()
        self.orbital_layout = QVBoxLayout(self.orbital_widget)

        entity_scroll = QScrollArea()
        entity_scroll.setWidgetResizable(True)
        entity_scroll.setWidget(self.entity_widget)

        orbital_scroll = QScrollArea()
        orbital_scroll.setWidgetResizable(True)
        orbital_scroll.setWidget(self.orbital_widget)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Entities"))
        left_layout.addWidget(entity_scroll)
        left_layout.addWidget(QLabel("Orbitals"))
        left_layout.addWidget(orbital_scroll)
        left_layout.addWidget(plot_button)
        left_layout.addWidget(self.weighted_mean_label)
        left_layout.addWidget(self.weighted_mean_toggle)
        left_layout.addWidget(export_csv)
        left_layout.addWidget(export_pdf)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        main_layout = QHBoxLayout()
        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(self.dos_plot, 3)

        container = QWidget()
        container.setLayout(main_layout)

        top_layout = QVBoxLayout()
        top_layout.addWidget(load_button)
        top_layout.addWidget(container)

        top_widget = QWidget()
        top_widget.setLayout(top_layout)

        self.setCentralWidget(top_widget)

    def load_file(self, filename=None):
        default_path = os.getcwd() if self.parent is None else self.parent.dir
        if filename is None:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Open DOSCAR", default_path, "LCFO.DOSCAR (*.lobster);;All Files (*)"
            )

        if not filename:
            return

        if os.path.exists("CONTCAR"):
            struct_file = "CONTCAR"
        elif os.path.exists("POSCAR"):
            struct_file = "POSCAR"
        else:
            QMessageBox.critical(self, "Error", "No structure file found")
            return
        struct_file = "CONTCAR" if os.path.exists("CONTCAR") else "POSCAR"
        self.doscar = DOSCAR(filename, False, struct_file)
        self.entity_names = self.build_entity_names(self.doscar.entities, len(self.doscar.pdos))
        self.clear_weighted_mean_lines()
        self.clear_dos_threshold_regions()
        self.current_weighted_means = {}
        self.current_dos_threshold_intervals = {}
        self.populate_checkboxes()

    def populate_checkboxes(self):

        # clear previous
        for box in self.entity_boxes:
            box.deleteLater()
        for box in self.orbital_boxes:
            box.deleteLater()

        self.entity_boxes = []
        self.orbital_boxes = []

        pdos = self.doscar.pdos

        # entities
        for i in range(len(pdos)):
            box = QCheckBox(self.get_entity_name(i))
            self.entity_layout.addWidget(box)
            self.entity_boxes.append(box)

        # orbitals from first entity

        unique_orbitals = list(map(list, dict.fromkeys(map(tuple, pdos))))
        flattened_unique_orbitals = [item for sublist in unique_orbitals for item in sublist]
        orbitals = flattened_unique_orbitals

        for orb in orbitals:
            box = QCheckBox(orb)
            self.orbital_layout.addWidget(box)
            self.orbital_boxes.append(box)

    def get_selected_entities(self):
        return [i for i, b in enumerate(self.entity_boxes) if b.isChecked()]

    def get_selected_orbitals(self):
        return [b.text() for b in self.orbital_boxes if b.isChecked()]

    @classmethod
    def normalize_entity_base(cls, entity):
        entity_name = str(entity)
        match = cls.Z_ENTITY_PATTERN.match(entity_name)
        if not match:
            return None

        try:
            return Element.from_Z(int(match.group(1))).symbol
        except ValueError:
            return None

    @classmethod
    def build_entity_names(cls, entities, count):
        names = []
        for index in range(count):
            entity = entities[index] if index < len(entities) else "Entity"
            base_name = cls.normalize_entity_base(entity)
            if base_name is None:
                names.append(str(entity))
            else:
                names.append(f"{base_name}{index + 1}")
        return names

    def get_entity_name(self, index):
        if 0 <= index < len(self.entity_names):
            return self.entity_names[index]
        return f"Entity{index + 1}"

    def plot_selected(self):

        if self.doscar is None:
            return

        full_plot = self.dos_plot.full_range_plot
        bounded_plot = self.dos_plot.bounded_plot
        self.dos_plot.clear_plot_data(full_plot)
        self.dos_plot.clear_plot_data(bounded_plot)
        self.clear_weighted_mean_lines()
        self.clear_dos_threshold_regions()

        energies = self.doscar.energies
        selected_entities = self.get_selected_entities()
        selected_orbitals = self.get_selected_orbitals()
        cmap = pg.colormap.get("turbo")
        colors = cmap.getColors(1)
        n = len(selected_orbitals)
        picked = [colors[round(i * (len(colors) - 1) / (n - 1))] for i in range(n)] if n > 1 else [colors[0]]
        WIDTH = 2
        sum_up = np.zeros_like(energies)
        sum_down = np.zeros_like(energies)

        for ent in selected_entities:

            for orb_num, orb in enumerate(selected_orbitals):

                data = self.doscar.pdos[ent][orb]

                if Spin.up in data:

                    up = data[Spin.up]
                    sum_up += up

                    pen = pg.mkPen(picked[orb_num], width=WIDTH)
                    name = f"{self.get_entity_name(ent)}_{orb}"
                    full_plot.plot(up, energies, pen=pen, name=name)
                    bounded_plot.plot(up, energies, pen=pen, name=name)

                if Spin.down in data:

                    down = -data[Spin.down]
                    sum_down += down

                    pen = pg.mkPen(picked[orb_num], width=WIDTH)
                    full_plot.plot(down, energies, pen=pen)
                    bounded_plot.plot(down, energies, pen=pen)

        # plot summed DOS
        sum_pen = pg.mkPen(width=0.8)
        full_plot.plot(sum_up, energies, pen=sum_pen, name="SUM")
        bounded_plot.plot(sum_up, energies, pen=sum_pen, name="SUM")

        if self.doscar.is_spin_polarized:
            full_plot.plot(sum_down, energies, pen=sum_pen)
            bounded_plot.plot(sum_down, energies, pen=sum_pen)

        self.refresh_weighted_mean()
        self.update_dos_threshold_regions(selected_entities, selected_orbitals)
        self.dos_plot.update_bounded_plot_y_range()

    def toggle_weighted_mean_on_plot(self, checked=None):
        self.show_weighted_mean_on_plot = self.weighted_mean_toggle.isChecked()
        state = "On" if self.show_weighted_mean_on_plot else "Off"
        self.weighted_mean_toggle.setText(f"Mean values on plot: {state}")
        self.refresh_weighted_mean()

    def refresh_weighted_mean(self):
        self.clear_weighted_mean_lines()
        if self.doscar is None:
            self.current_weighted_means = {}
            return

        self.update_weighted_mean(self.get_selected_entities(), self.get_selected_orbitals())

    def clear_weighted_mean_lines(self):
        for line, plot in self.weighted_mean_lines:
            plot.removeItem(line)
        self.weighted_mean_lines = []

    def clear_dos_threshold_regions(self):
        for region, plot in self.dos_threshold_regions:
            plot.removeItem(region)
        self.dos_threshold_regions = []

    def update_weighted_mean(self, selected_entities, selected_orbitals):
        if len(selected_entities) != 1 or not selected_orbitals:
            self.current_weighted_means = {}
            self.weighted_mean_label.setText("Weighted mean: select one entity and at least one orbital")
            return

        ent = selected_entities[0]
        energies = self.doscar.energies
        min_energy, max_energy = sorted(self.dos_plot.region.getRegion())
        region_energies = self.get_region_energies(energies, min_energy, max_energy)
        if region_energies is None:
            self.current_weighted_means = {}
            self.weighted_mean_label.setText("Weighted mean: selected region is too narrow")
            return

        spin_weights = {}

        for orb in selected_orbitals:
            data = self.doscar.pdos[ent][orb]
            for spin in [Spin.up, Spin.down]:
                if spin not in data:
                    continue
                if spin not in spin_weights:
                    spin_weights[spin] = np.zeros_like(energies, dtype=float)
                spin_weights[spin] += data[spin]

        integrate = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
        orbital_label = "+".join(selected_orbitals)
        means = {}

        for spin, weights in spin_weights.items():
            region_energies, region_weights = self.slice_to_region(energies, weights, min_energy, max_energy)
            denominator = integrate(region_weights, region_energies)
            if np.isclose(denominator, 0.0):
                continue
            means[spin] = integrate(region_energies * region_weights, region_energies) / denominator

        if not means:
            self.current_weighted_means = {}
            self.weighted_mean_label.setText(
                f"Weighted mean for {self.get_entity_name(ent)}_{orbital_label}: no DOS weight in selected region"
            )
            return

        self.current_weighted_means = means

        label_parts = []
        for spin, spin_label in [(Spin.up, "up"), (Spin.down, "down")]:
            if spin in means:
                label_parts.append(f"{spin_label} {means[spin]:.4f} eV")

        self.weighted_mean_label.setText(
            f"Weighted mean for {self.get_entity_name(ent)}_{orbital_label} "
            f"({min_energy:.2f} to {max_energy:.2f} eV): " + ", ".join(label_parts)
        )

        if self.show_weighted_mean_on_plot:
            self.add_weighted_mean_lines(means)

    @staticmethod
    def get_region_energies(energies, min_energy, max_energy):
        low = max(min_energy, np.min(energies))
        high = min(max_energy, np.max(energies))
        if not low < high:
            return None
        return np.array([low, high], dtype=float)

    @staticmethod
    def slice_to_region(energies, weights, min_energy, max_energy):
        sort_order = np.argsort(energies)
        sorted_energies = energies[sort_order]
        sorted_weights = weights[sort_order]
        low = max(min_energy, sorted_energies[0])
        high = min(max_energy, sorted_energies[-1])

        inside = (sorted_energies > low) & (sorted_energies < high)
        region_energies = np.concatenate(([low], sorted_energies[inside], [high]))
        region_weights = np.interp(region_energies, sorted_energies, sorted_weights)
        return region_energies, region_weights

    def add_weighted_mean_lines(self, means):
        line_specs = {
            Spin.up: ("#d62728", "up mean={value:0.2f} eV", 0.85),
            Spin.down: ("#1f77b4", "down mean={value:0.2f} eV", 0.70),
        }

        self.updating_overlay_spans = True
        for spin, weighted_mean in means.items():

            color, label, position = line_specs[spin]
            pen = pg.mkPen(color=color, width=1.5, style=QtCore.Qt.DashLine)
            for plot in [self.dos_plot.full_range_plot, self.dos_plot.bounded_plot]:
                span = self.spin_side_span(plot, spin)
                if span is None:
                    continue
                line = pg.InfiniteLine(
                    pos=float(weighted_mean),
                    angle=0,
                    pen=pen,
                    movable=False,
                    label=label,
                    labelOpts={"position": position, "color": color, "movable": True},
                    span=span,
                )
                plot.addItem(line)
                self.weighted_mean_lines.append((line, plot))
        self.updating_overlay_spans = False

    def update_overlay_spans(self, *args):
        if self.updating_overlay_spans:
            return

        if self.show_weighted_mean_on_plot and self.current_weighted_means:
            self.clear_weighted_mean_lines()
            self.add_weighted_mean_lines(self.current_weighted_means)

        if self.current_dos_threshold_intervals:
            self.clear_dos_threshold_regions()
            self.add_dos_threshold_regions(self.current_dos_threshold_intervals)

    @staticmethod
    def spin_side_span(plot, spin):
        x_min, x_max = plot.viewRange()[0]
        width = x_max - x_min
        if width <= 0:
            return None

        zero_position = (0.0 - x_min) / width
        zero_position = min(max(zero_position, 0.0), 1.0)

        if spin == Spin.up:
            if x_max <= 0:
                return None
            return zero_position, 1.0

        if x_min >= 0:
            return None
        return 0.0, zero_position

    def update_dos_threshold_regions(self, selected_entities, selected_orbitals):
        self.clear_dos_threshold_regions()
        if len(selected_entities) != 1 or not selected_orbitals:
            self.current_dos_threshold_intervals = {}
            return

        ent = selected_entities[0]
        energies = self.doscar.energies
        spin_intensities = {}

        for orb in selected_orbitals:
            data = self.doscar.pdos[ent][orb]
            for spin in [Spin.up, Spin.down]:
                if spin not in data:
                    continue
                if spin not in spin_intensities:
                    spin_intensities[spin] = np.zeros_like(energies, dtype=float)
                spin_intensities[spin] += data[spin]

        intervals_by_spin = {}
        for spin, intensity in spin_intensities.items():
            max_intensity = np.max(intensity)
            if np.isclose(max_intensity, 0.0):
                continue
            intervals_by_spin[spin] = self.threshold_intervals(energies, intensity, 0.1 * max_intensity)

        self.current_dos_threshold_intervals = intervals_by_spin
        if not intervals_by_spin:
            return

        self.add_dos_threshold_regions(intervals_by_spin)

    @staticmethod
    def threshold_intervals(energies, intensity, threshold):
        sort_order = np.argsort(energies)
        energies = energies[sort_order]
        intensity = intensity[sort_order]
        above = intensity > threshold
        intervals = []

        start = None
        for idx, is_above in enumerate(above):
            if is_above and start is None:
                if idx == 0:
                    start = energies[idx]
                else:
                    start = DosWindow.crossing_energy(
                        energies[idx - 1], intensity[idx - 1], energies[idx], intensity[idx], threshold
                    )
            elif not is_above and start is not None:
                end = DosWindow.crossing_energy(
                    energies[idx - 1], intensity[idx - 1], energies[idx], intensity[idx], threshold
                )
                intervals.append((start, end))
                start = None

        if start is not None:
            intervals.append((start, energies[-1]))

        return intervals

    @staticmethod
    def crossing_energy(energy_a, intensity_a, energy_b, intensity_b, threshold):
        if np.isclose(intensity_a, intensity_b):
            return energy_a
        fraction = (threshold - intensity_a) / (intensity_b - intensity_a)
        fraction = min(max(fraction, 0.0), 1.0)
        return energy_a + fraction * (energy_b - energy_a)

    def add_dos_threshold_regions(self, intervals_by_spin):
        region_specs = {
            Spin.up: (pg.mkBrush(214, 39, 40, 45), pg.mkPen(214, 39, 40, 90)),
            Spin.down: (pg.mkBrush(31, 119, 180, 45), pg.mkPen(31, 119, 180, 90)),
        }

        self.updating_overlay_spans = True
        for spin, intervals in intervals_by_spin.items():
            brush, pen = region_specs[spin]
            for start, end in intervals:
                for plot in [self.dos_plot.full_range_plot, self.dos_plot.bounded_plot]:
                    span = self.spin_side_span(plot, spin)
                    if span is None:
                        continue
                    region = pg.LinearRegionItem(
                        values=(float(start), float(end)),
                        orientation=pg.LinearRegionItem.Horizontal,
                        brush=brush,
                        pen=pen,
                        movable=False,
                        span=span,
                    )
                    region.setZValue(-10)
                    plot.addItem(region)
                    self.dos_threshold_regions.append((region, plot))
        self.updating_overlay_spans = False

    def export_csv(self):

        if self.doscar is None:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "", "CSV (*.csv)"
        )

        if not filename:
            return

        energies = self.doscar.energies

        selected_entities = self.get_selected_entities()
        selected_orbitals = self.get_selected_orbitals()

        rows = []

        header = ["Energy"]

        data_columns = []

        for ent in selected_entities:
            entity_name = self.get_entity_name(ent)
            for orb in selected_orbitals:

                d = self.doscar.pdos[ent][orb]

                if Spin.up in d:
                    header.append(f"{entity_name}_{orb}_up")
                    data_columns.append(d[Spin.up])

                if Spin.down in d:
                    header.append(f"{entity_name}_{orb}_down")
                    data_columns.append(d[Spin.down])

        rows.append(header)

        for i in range(len(energies)):

            row = [energies[i]]

            for col in data_columns:
                row.append(col[i])

            rows.append(row)

        with open(filename, "w") as f:
            for r in rows:
                f.write(",".join(map(str, r)) + "\n")

if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = DosWindow()
    file = "DOSCAR.LCFO.lobster"
    if file in [file.name for file in Path.cwd().iterdir()]:
        w.load_file(file)
    w.resize(1200, 800)
    w.show()

    sys.exit(app.exec_())
