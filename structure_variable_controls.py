from PyQt5.QtGui import QCloseEvent
from structure_plot import StructureViewer
from structure_controls import StructureControlsWidget
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, \
    QPushButton, QHBoxLayout, QFrame
from PyQt5.QtCore import pyqtSlot, Qt


class StructureVariableControls(QWidget):
    def __init__(self, structure_control_widget):
        super().__init__(structure_control_widget)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        self.frame = QFrame(self)

        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.frame.setStyleSheet("background-color: rgb(200, 200, 200);")
        self.frame.setLineWidth(10)

        self.frame_layout = QVBoxLayout(self.frame)
        self.layout.addWidget(self.frame)

        # Store the data manager
        self.structure_control_widget = structure_control_widget

        # Initialize table and populate
        self.createTable()

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
        self.frame_layout.addWidget(self.tableWidget)

    @pyqtSlot(int, int)
    def updateData(self, row, column):
        if column in [1, 2, 3, 4, 5, 6]:  # Only update if X, Y, Z, Move X, Move Y, or Move Z columns are edited
            try:
                if column in [1, 2, 3]:  # X, Y, Z columns (float)
                    new_value = float(self.tableWidget.item(row, column).text())
                    self.structure_control_widget.coordinates[row][column - 1] = new_value
                else:  # Move X, Move Y, Move Z columns (T or F)
                    new_value = self.tableWidget.item(row, column).text()
                    if new_value.upper() in ['T', 'F']:
                        self.structure_control_widget.constraints[row][column - 4] = new_value.upper()
                    else:
                        raise ValueError("Movement constraint must be 'T' or 'F'.")

                print(
                    f"Updated data: {self.structure_control_widget.atom_num_and_symb}, {self.structure_control_widget.coordinates}, {self.structure_control_widget.constraints}")
            except ValueError:
                print("Invalid input.")
                # Revert to the old value
                if column in [1, 2, 3]:
                    old_value = self.structure_control_widget.coordinates[row][column - 1]
                else:
                    old_value = self.structure_control_widget.constraints[row][column - 4]
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

    def is_row_selected(self, row):
        column_count = self.tableWidget.columnCount()
        for column in range(column_count-2):
            if not self.tableWidget.item(row, column).isSelected():
                return False
        return True


 
        


