import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,
    QFileDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QMessageBox
)
from PyQt5 import QtCore
from pathlib import Path
from collections import defaultdict
import sys
import os
import re

class Potcar_tab(QWidget):
    def __init__(self, structure_variable_control):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.structure_variable_control = structure_variable_control
        self.structure_plot_widget = self.structure_variable_control.structure_control_widget.structure_plot_widget
        self.data = self.structure_plot_widget.data

        self.label = QLabel("Click to create POTCAR")
        self.button = QPushButton("Choose POTCAR files directory")

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.button)
        self.button.clicked.connect(self.generate_potcar)

        self.setLayout(self.layout)

    def generate_potcar(self):
        self.symbols_as_in_poscar, self.counts = self.data.poscar.atom_lines_as_in_poscar(self.data.symbols)
        self.mendelev_symbols_as_in_poscar = self.data.poscar.mendelev_symbols(self.symbols_as_in_poscar)
        potcar_dir = QFileDialog.getExistingDirectory(self, "Select POTCAR Base Directory")
        if not potcar_dir:
            return
        dialog = PotcarSelectorDialog(self.mendelev_symbols_as_in_poscar, potcar_dir, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        selection = dialog.get_selection()
        try:
            contents = self.create_potcar(self.mendelev_symbols_as_in_poscar, selection, potcar_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save POTCAR", "POTCAR", "All Files (*)")
        if save_path:
            Path(save_path).write_text(contents)
            QMessageBox.information(self, "Success", f"POTCAR written to:\n{save_path}")

    def create_potcar(self, symbols, selection, potcar_dir):
        potcar_dir = Path(potcar_dir)
        potcar_contents = []
        for symbol in symbols:
            variant_dir = potcar_dir / selection[symbol]
            potcar_path = variant_dir / "POTCAR"
            if not potcar_path.is_file():
                raise FileNotFoundError(f"Expected POTCAR not found at: {potcar_path}")
            potcar_contents.append(potcar_path.read_text())
        return "".join(potcar_contents)

class PotcarSelectorDialog(QDialog):
    def __init__(self, symbols, potcar_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select POTCAR Variants")
        self.layout = QFormLayout(self)
        self.symbols = symbols
        self.potcar_dir = Path(potcar_dir)
        self.selection = {}
        self.combos = {}
        self.available = self.find_potcar_variants()

        if not self.available:
            QMessageBox.critical(self, "Error", f"No valid POTCAR variants found in:\n{self.potcar_dir}")
            self.close_button = QDialogButtonBox(QDialogButtonBox.Cancel)
            self.close_button.rejected.connect(self.reject)
            self.layout.addRow(self.close_button)
        else:
            for element, variants in self.available.items():
                combo = QComboBox()
                combo.addItems(variants)
                self.layout.addRow(QLabel(f"{element}:"), combo)
                self.combos[element] = combo

            self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)
            self.layout.addRow(self.buttons)

    def find_potcar_variants(self):
        dirs = sorted({d.name for d in self.potcar_dir.iterdir() if (d / "POTCAR").is_file()})
        element_to_choices = defaultdict(set)
        for dname in dirs:
            for symbol in set(self.symbols):
                if dname == symbol or dname.startswith(f"{symbol}_"):
                    element_to_choices[symbol].add(dname)
        return {el: sorted(choices) for el, choices in element_to_choices.items()}

    def get_selection(self):
        return {el: self.combos[el].currentText() for el in self.combos}