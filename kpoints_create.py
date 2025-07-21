import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, \
    QFileDialog, QPushButton, QHBoxLayout, QSlider, QMainWindow, QComboBox
from PyQt5 import QtCore
import sys
import os
import re

class Kpoints_tab(QWidget):
    def __init__(self, structure_plot_widget):
        super().__init__()
        self.structure_plot_widget = structure_plot_widget
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(QtCore.Qt.AlignTop)

        choose_label = QLabel("Choose the spacing for k-point grid: ")
        main_layout.addWidget(choose_label)

        combo_layout = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setMaximumWidth(150)
        self.combo.setEditable(True)
        self.combo.addItems(["Very coarse: 0.4", "Coarse: 0.3", "Medium: 0.15", "Fine: 0.1", "Very fine: 0.05"])
        self.combo.currentIndexChanged.connect(self.on_text_changed)

        unit_label = QLabel("1/A   ")
        spacing_prefix_label = QLabel("Current kpoints spacing: ")
        self.spacing_label = QLabel("0.4")
        spacing_suffix_label = QLabel(" 1/A")

        combo_layout.addWidget(self.combo)
        combo_layout.addWidget(unit_label)
        combo_layout.addWidget(spacing_prefix_label)
        combo_layout.addWidget(self.spacing_label)
        combo_layout.addWidget(spacing_suffix_label)

        kpoint_grid_label_prefix = QLabel("Kpoints grid: ")
        self.kpoint_grid_label = QLabel("")

        kpts_layout = QHBoxLayout()
        kpts_layout.addWidget(kpoint_grid_label_prefix)
        kpts_layout.addWidget(self.kpoint_grid_label)

        main_layout.addLayout(combo_layout)
        main_layout.addLayout(kpts_layout)
        self.setLayout(main_layout)

    def calculate_kpoint_grid(self, real_lattice, kpoint_spacing):
        """
        Calculate the optimal k-point grid for any unit cell shape.

        Parameters:
        - real_lattice: 3x3 numpy array of real-space lattice vectors as rows.
        - kpoint_spacing: Desired spacing in Å^-1.

        Returns:
        - kpoint_grid: Number of divisions along each reciprocal lattice direction.
        """
        # Calculate the reciprocal lattice vectors
        volume = np.dot(real_lattice[0], np.cross(real_lattice[1], real_lattice[2]))
        reciprocal_lattice = 2 * np.pi * np.linalg.inv(real_lattice).T  # Rows are reciprocal lattice vectors

        # Compute the norms of the reciprocal lattice vectors
        reciprocal_magnitudes = np.linalg.norm(reciprocal_lattice, axis=1)

        # Calculate the number of k-points along each reciprocal direction
        num_kpoints = np.ceil(reciprocal_magnitudes / kpoint_spacing).astype(int)

        return num_kpoints

    def get_kpoint_grid(self, kpoint_grid):
        return "x".join([str(x) for x in list(kpoint_grid)])

    def get_kpoint_spacing(self):
        text = self.combo.currentText()
        number = self.extract_one_number(text)
        return number

    def calculate_kpoints(self):
        spacing = self.get_kpoint_spacing()
        vectors = np.array(self.structure_plot_widget.data.unit_cell_vectors)
        kpts_grid = self.calculate_kpoint_grid(vectors, spacing)
        kpts_string = self.get_kpoint_grid(kpts_grid)
        return kpts_string

    def on_text_changed(self):
        kpts_string = self.calculate_kpoints()
        self.kpoint_grid_label.setText(kpts_string)
        self.spacing_label.setText(str(self.get_kpoint_spacing()))

        pass
    def extract_one_number(self, s):
        # Match only if there's exactly one valid number (integer or float)
        matches = re.findall(r'\d+(?:\.\d+)?', s)

        if len(matches) != 1:
            raise ValueError(f"Expected exactly one number, found {len(matches)}: {matches}")

        return float(matches[0])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    kpt = Kpoints_tab()


    # Example: Real lattice vectors for an arbitrary unit cell
    real_lattice = np.array([
        [16.229, 0.0, 0.0],  # a vector
        [0, 16.229, 0.0],  # b vector
        [0,0,18.11]  # c vector
    ])

    # Desired k-point spacing in Å^-1
    kpoint_spacing = 0.2

    # Calculate the k-point grid
    kpoint_grid = kpt.calculate_general_kpoint_grid(real_lattice, kpoint_spacing)

    print(f"Optimal k-point grid: {kpoint_grid}")
