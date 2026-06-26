import os
import re
import sys
import numpy as np
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QScrollArea, QMessageBox, QGridLayout, QSplitter
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
    ENTITY_LABEL_PATTERN = re.compile(r"^\s*([A-Z][a-z]?)(?:\d+)?\s*$")
    ORBITAL_FAMILIES = ("s", "p", "d", "f")

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
        self.show_dos_threshold_regions = True

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

        self.dos_threshold_toggle = QPushButton("Highlights: On")
        self.dos_threshold_toggle.setCheckable(True)
        self.dos_threshold_toggle.setChecked(True)
        self.dos_threshold_toggle.clicked.connect(self.toggle_dos_threshold_regions)

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

        self.entity_button_widget = QWidget()
        self.entity_button_layout = QVBoxLayout()
        self.entity_button_widget.setLayout(self.entity_button_layout)
        self.entity_button_layout.setAlignment(QtCore.Qt.AlignTop)

        self.orbital_button_widget = QWidget()
        self.orbital_button_layout = QVBoxLayout()
        self.orbital_button_widget.setLayout(self.orbital_button_layout)
        self.orbital_button_layout.setAlignment(QtCore.Qt.AlignTop)

        entity_button_scroll = QScrollArea()
        entity_button_scroll.setWidgetResizable(True)
        entity_button_scroll.setWidget(self.entity_button_widget)

        orbital_button_scroll = QScrollArea()
        orbital_button_scroll.setWidgetResizable(True)
        orbital_button_scroll.setWidget(self.orbital_button_widget)

        selector_layout = QGridLayout()
        selector_layout.addWidget(QLabel("Entities"), 0, 0)
        selector_layout.addWidget(QLabel("Entity buttons"), 0, 1)
        selector_layout.addWidget(entity_scroll, 1, 0)
        selector_layout.addWidget(entity_button_scroll, 1, 1)
        selector_layout.addWidget(QLabel("Orbitals"), 2, 0)
        selector_layout.addWidget(QLabel("Orbital buttons"), 2, 1)
        selector_layout.addWidget(orbital_scroll, 3, 0)
        selector_layout.addWidget(orbital_button_scroll, 3, 1)
        selector_layout.setColumnStretch(0, 2)
        selector_layout.setColumnStretch(1, 1)
        selector_layout.setRowStretch(1, 1)
        selector_layout.setRowStretch(3, 1)

        left_layout = QVBoxLayout()
        left_layout.addLayout(selector_layout)
        left_layout.addWidget(plot_button)
        left_layout.addWidget(self.weighted_mean_label)

        overlay_controls_layout = QHBoxLayout()
        overlay_controls_layout.addWidget(self.weighted_mean_toggle)
        overlay_controls_layout.addWidget(self.dos_threshold_toggle)
        left_layout.addLayout(overlay_controls_layout)

        left_layout.addWidget(export_csv)
        left_layout.addWidget(export_pdf)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        main_splitter = QSplitter(QtCore.Qt.Horizontal)
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(self.dos_plot)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes([360, 840])

        top_layout = QVBoxLayout()
        top_layout.addWidget(load_button)
        top_layout.addWidget(main_splitter)

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

        checked_entities = self.get_selected_entities()
        checked_orbitals = set(self.get_selected_orbitals())

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
        self.populate_checkboxes(checked_entities, checked_orbitals)

    def populate_checkboxes(self, checked_entities=None, checked_orbitals=None):
        checked_entities = set(checked_entities or [])
        checked_orbitals = set(checked_orbitals or [])

        # clear previous
        self.clear_layout(self.entity_layout)
        self.clear_layout(self.orbital_layout)

        self.entity_boxes = []
        self.orbital_boxes = []

        pdos = self.doscar.pdos

        # entities
        for i in range(len(pdos)):
            box = QCheckBox(self.get_entity_name(i))
            box.setChecked(i in checked_entities)
            self.entity_layout.addWidget(box)
            self.entity_boxes.append(box)

        # Preserve the orbital order from the file while removing duplicates.
        orbitals = list(dict.fromkeys(orbital for entity_pdos in pdos for orbital in entity_pdos))

        for orb in orbitals:
            box = QCheckBox(orb)
            box.setChecked(orb in checked_orbitals)
            self.orbital_layout.addWidget(box)
            self.orbital_boxes.append(box)

        self.populate_selection_buttons(orbitals)

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
    def entity_symbol_from_label(cls, label):
        match = cls.ENTITY_LABEL_PATTERN.match(str(label))
        if match:
            return match.group(1)
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

    def get_entity_symbol(self, index):
        if self.doscar is not None and index < len(self.doscar.entities):
            symbol = self.normalize_entity_base(self.doscar.entities[index])
            if symbol is not None:
                return symbol
        return self.entity_symbol_from_label(self.get_entity_name(index))

    @classmethod
    def orbital_family(cls, orbital):
        text = str(orbital).strip().lower()
        match = re.search(r"(?:^|[_\-\s])\d*([spdf])(?:$|[_^()]|[xyz])", text)
        if match:
            return match.group(1)

        return None

    @classmethod
    def group_orbitals_by_family(cls, orbitals):
        grouped = {family: [] for family in cls.ORBITAL_FAMILIES}
        for orbital in orbitals:
            family = cls.orbital_family(orbital)
            if family in grouped:
                grouped[family].append(orbital)
        return {family: values for family, values in grouped.items() if values}

    def group_entities_by_symbol(self):
        grouped = {}
        for index, _box in enumerate(self.entity_boxes):
            symbol = self.get_entity_symbol(index)
            if symbol is None:
                continue
            grouped.setdefault(symbol, []).append(index)
        return grouped

    def populate_selection_buttons(self, orbitals):
        self.clear_layout(self.entity_button_layout)
        self.clear_layout(self.orbital_button_layout)

        if self.entity_boxes:
            self.add_toggle_button(self.entity_button_layout, "All entities", self.toggle_all_entities)

        for symbol, indexes in self.group_entities_by_symbol().items():
            self.add_toggle_button(
                self.entity_button_layout,
                symbol,
                lambda checked=False, group_indexes=indexes: self.toggle_entity_group(group_indexes),
            )

        if self.orbital_boxes:
            self.add_toggle_button(self.orbital_button_layout, "All orbitals", self.toggle_all_orbitals)

        for family in self.group_orbitals_by_family(orbitals):
            self.add_toggle_button(
                self.orbital_button_layout,
                family,
                lambda checked=False, orbital_family=family: self.toggle_orbital_group(orbital_family),
            )

    def add_toggle_button(self, layout, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)

    def toggle_all_entities(self):
        self.toggle_boxes(self.entity_boxes)

    def toggle_entity_group(self, indexes):
        boxes = [self.entity_boxes[index] for index in indexes if index < len(self.entity_boxes)]
        self.toggle_boxes(boxes)

    def toggle_all_orbitals(self):
        self.toggle_boxes(self.orbital_boxes)

    def toggle_orbital_group(self, family):
        boxes = [box for box in self.orbital_boxes if self.orbital_family(box.text()) == family]
        self.toggle_boxes(boxes)

    @staticmethod
    def toggle_boxes(boxes):
        if not boxes:
            return

        checked = not all(box.isChecked() for box in boxes)
        for box in boxes:
            box.setChecked(checked)

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            child_layout = child.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                DosWindow.clear_layout(child_layout)

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

    def toggle_dos_threshold_regions(self, checked=None):
        self.show_dos_threshold_regions = self.dos_threshold_toggle.isChecked()
        state = "On" if self.show_dos_threshold_regions else "Off"
        self.dos_threshold_toggle.setText(f"Highlights: {state}")
        self.clear_dos_threshold_regions()
        if self.show_dos_threshold_regions and self.current_dos_threshold_intervals:
            self.add_dos_threshold_regions(self.current_dos_threshold_intervals)

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
            for plot in [self.dos_plot.bounded_plot]:
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

        if self.show_dos_threshold_regions and self.current_dos_threshold_intervals:
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

        if self.show_dos_threshold_regions:
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
                for plot in [self.dos_plot.bounded_plot]:
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
