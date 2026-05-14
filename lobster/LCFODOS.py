import os
import sys
import numpy as np
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QLabel, QScrollArea, QMessageBox
)

import pyqtgraph as pg

from lobster.lobster_outputs import Doscar as DOSCAR
from pymatgen.electronic_structure.core import Spin
from dos_plot_widget import PDFExporter


class DosWindow(QMainWindow):

    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent
        if self.parent is not None:
            os.chdir(self.parent.dir)
        self.setWindowTitle("LOBSTER DOS Viewer")

        self.doscar = None
        self.entity_boxes = []
        self.orbital_boxes = []

        self.plot_widget = pg.PlotWidget(background='white')
        self.plot_widget.addLegend()

        load_button = QPushButton("Load DOSCAR.LCFO.lobster")
        load_button.clicked.connect(lambda: self.load_file(filename=None))

        plot_button = QPushButton("Plot")
        plot_button.clicked.connect(self.plot_selected)

        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(self.export_csv)

        export_pdf = QPushButton("Export PDF")
        export_pdf.clicked.connect(lambda: self.export_pdf(plot_widget=self.plot_widget))

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
        left_layout.addWidget(export_csv)
        left_layout.addWidget(export_pdf)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        main_layout = QHBoxLayout()
        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(self.plot_widget, 3)

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
            box = QCheckBox(f"{self.doscar.entities[i]}")
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

    def plot_selected(self):

        if self.doscar is None:
            return

        self.plot_widget.clear()

        energies = self.doscar.energies
        entities = self.doscar.entities
        selected_entities = self.get_selected_entities()
        selected_orbitals = self.get_selected_orbitals()
        cmap = pg.colormap.get("turbo")
        colors = cmap.getColors(1)
        n = len(selected_orbitals)
        picked = [colors[round(i * (len(colors) - 1) / (n - 1))] for i in range(n)] if n > 1 else [colors[0]]
        WIDTH = 2
        sum_up = np.zeros_like(energies)
        sum_down = np.zeros_like(energies)

        for ent_num,ent in enumerate(selected_entities):

            for orb_num, orb in enumerate(selected_orbitals):

                data = self.doscar.pdos[ent][orb]

                if Spin.up in data:

                    up = data[Spin.up]
                    sum_up += up

                    self.plot_widget.plot(
                        up, energies,
                        pen=pg.mkPen(picked[orb_num], width=WIDTH),
                        name=f"{entities[ent_num]}_{orb}"
                    )

                if Spin.down in data:

                    down = -data[Spin.down]
                    sum_down += down

                    self.plot_widget.plot(
                        down, energies,
                        pen=pg.mkPen(picked[orb_num], width=WIDTH)
                    )

        # plot summed DOS
        self.plot_widget.plot(
            sum_up, energies,
            pen=pg.mkPen(width=0.8),
            name="SUM"
        )

        if self.doscar.is_spin_polarized:
            self.plot_widget.plot(
                sum_down, energies,
                pen=pg.mkPen(width=0.8),
            )

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
            for orb in selected_orbitals:

                d = self.doscar.pdos[ent][orb]

                if Spin.up in d:
                    header.append(f"E{ent}_{orb}_up")
                    data_columns.append(d[Spin.up])

                if Spin.down in d:
                    header.append(f"E{ent}_{orb}_down")
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

    def export_pdf(self, plot_widget):
        filename, _ = QFileDialog.getSaveFileName(
            plot_widget,
            "Save plot data",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not filename:
            return  # user cancelled
        exporter = PDFExporter(plot_widget)
        exporter.export(filename=filename)



if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = DosWindow()
    file = "DOSCAR.LCFO.lobster"
    if file in [file.name for file in Path.cwd().iterdir()]:
        w.load_file(file)
    w.resize(1200, 800)
    w.show()

    sys.exit(app.exec_())