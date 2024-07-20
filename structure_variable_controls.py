from PyQt5.QtGui import QCloseEvent
from structure_plot import StructureViewer
from structure_controls import StructureControlsWidget
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, \
    QPushButton, QHBoxLayout, QFrame, QHeaderView, QFileDialog
from PyQt5.QtCore import pyqtSlot, Qt
from collections import OrderedDict

class StructureVariableControls(QWidget):
    def __init__(self, structure_control_widget):
        super().__init__(structure_control_widget)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        # Store the data manager
        self.structure_control_widget = structure_control_widget

        # Initialize table and populate
        self.createTable()

        self.save_poscar_btn = QPushButton("Save Poscar")
        self.save_poscar_btn.clicked.connect(self.save_poscar)

        self.layout.addWidget(self.tableWidget)
        self.layout.addWidget(self.save_poscar_btn)

    def createTable(self):
        self.tableWidget = QTableWidget()
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectRows)

        # Get data from the data manager
        atom_num_and_symb, coordinates, constraints = self.structure_control_widget.get_table_data()

        # Set row count based on the data
        num_atoms = len(atom_num_and_symb)
        self.tableWidget.setRowCount(num_atoms)
        self.tableWidget.setColumnCount(8)  # Extra columns for constraints and delete button

        # Set table headers
        headers = ["Atom", "X", "Y", "Z", "Move X", "Move Y", "Move Z", "Actions"]
        self.tableWidget.setHorizontalHeaderLabels(headers)
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        # Add data to the table
        for row in range(num_atoms):
            atom = atom_num_and_symb[row]
            x, y, z = coordinates[row]
            move_x, move_y, move_z = constraints[row]

            self.tableWidget.setItem(row, 0, QTableWidgetItem(atom))
            self.tableWidget.setItem(row, 1, QTableWidgetItem(str(x)))
            self.tableWidget.setItem(row, 2, QTableWidgetItem(str(y)))
            self.tableWidget.setItem(row, 3, QTableWidgetItem(str(z)))
            self.tableWidget.setItem(row, 4, QTableWidgetItem(move_x))
            self.tableWidget.setItem(row, 5, QTableWidgetItem(move_y))
            self.tableWidget.setItem(row, 6, QTableWidgetItem(move_z))

            # Add a delete button in the last column
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, r=row: self.deleteRow(r))
            self.tableWidget.setCellWidget(row, 7, delete_button)

        # Connect the cellChanged signal to the updateData method
        self.tableWidget.cellChanged.connect(self.updateData)
        self.tableWidget.itemSelectionChanged.connect(self.on_selection_changed)





    @pyqtSlot(int, int)
    def updateData(self, row, column):
        if column in [1, 2, 3, 4, 5, 6]:  # Only update if X, Y, Z, Move X, Move Y, or Move Z columns are edited
            try:
                if column in [1, 2, 3]:  # X, Y, Z columns (float)
                    new_value = float(self.tableWidget.item(row, column).text())
                    self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][0][row][column - 1] = new_value
                else:  # Move X, Move Y, Move Z columns (T or F)
                    new_value = self.tableWidget.item(row, column).text()
                    if new_value.upper() in ['T', 'F']:
                        self.structure_control_widget.structure_plot_widget.data.all_constrains[row][column - 4] = new_value.upper()
                    else:
                        raise ValueError("Movement constraint must be 'T' or 'F'.")

                print("Updated data")
                self.structure_control_widget.add_sphere()
                self.structure_control_widget.add_bonds()
            except ValueError:
                print("Invalid input.")
                # Revert to the old value
                if column in [1, 2, 3]:
                    old_value = self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][0][row][column - 1]
                else:
                    old_value = self.structure_control_widget.structure_plot_widget.data.constrains[row][column - 4]
                self.tableWidget.blockSignals(True)
                self.tableWidget.setItem(row, column, QTableWidgetItem(str(old_value)))
                self.tableWidget.blockSignals(False)



    def deleteRow(self, row):
        # Call delete_row method from data manager
        self.structure_control_widget.delete_row(row)

        # Clear the table and remove it from layout
        self.tableWidget.blockSignals(True)
        self.tableWidget.clearContents()
        self.layout.removeWidget(self.tableWidget)
        self.tableWidget.blockSignals(False)

        # Rebuild the table with the updated data
        self.createTable()

        # Add the new table to the layout
        self.layout.addWidget(self.tableWidget)

        self.structure_control_widget.add_sphere()
        self.structure_control_widget.add_bonds()

    def on_selection_changed(self):
        selected_items = self.tableWidget.selectedItems()
        if not selected_items:
            return

        selected_rows = set()
        for item in selected_items:
            selected_rows.add(item.row())

        for row in selected_rows:
            if self.is_row_selected(row):
                print(f"Whole row {row} is selected")

        actor = self.structure_control_widget.structure_plot_widget.sphere_actors[row]
        actor.GetProperty().SetColor(255, 255, 0)
        actor.GetMapper().GetInputConnection(0, 0).GetProducer().SetRadius(self.structure_control_widget.sphere_radius * 2)
        self.structure_control_widget.plotter.render()  # Re-render the scene

    def is_row_selected(self, row):
        column_count = self.tableWidget.columnCount()
        for column in range(column_count-2):
            if not self.tableWidget.item(row, column).isSelected():
                return False
        return True

    def save_poscar(self):
        # Open a file dialog to save the text file
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Spheres Data", "", "All Files (*)", options=options)

        x = self.structure_control_widget.structure_plot_widget.data.x
        y = self.structure_control_widget.structure_plot_widget.data.y
        z = self.structure_control_widget.structure_plot_widget.data.z
        atoms_list = self.structure_control_widget.structure_plot_widget.data.symbols
        count_dict = OrderedDict()
        for element in atoms_list:
            if element in count_dict:
                count_dict[element] += 1
            else:
                count_dict[element] = 1
        atoms = list(count_dict.keys())
        numbers = list(count_dict.values())
        atoms_line = ' '.join(map(str, atoms))
        numbers_line = ' '.join(map(str, numbers))

        coordinates = self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][0]
        constrains = self.structure_control_widget.structure_plot_widget.data.all_constrains
        if file_name:
            # Remove file extension if it exists
            if '.' in file_name:
                file_name = file_name.rsplit('.', 1)[0]
            with open(file_name, 'w') as file:
                file.write("created by Leszek Nowakowski with VASPexplorer/DOSwizard \n")
                file.write("1.0000000000000\n")
                file.write(f" {x:.6f}\t0.000000 0.000000\n")
                file.write(f" 0.0000000 {y:.6f} 0.000000\n")
                file.write(f" 0.0000000 0.0000000 {z:.6f}\n")
                file.write(atoms_line+"\n")
                file.write(numbers_line + "\n")
                file.write("Selective dynamics\n")
                file.write("Cartesian\n")
                for index, (coord, const) in enumerate(zip(coordinates, constrains)):
                    coord_str = ' '.join(f"{x:.6f}" for x in coord)
                    const_str = ' '.join(const)
                    file.write(f" {coord_str}\t{const_str}\n")

 
        


