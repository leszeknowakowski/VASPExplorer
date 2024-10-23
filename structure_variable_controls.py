from PyQt5.QtGui import QCloseEvent
from structure_plot import StructureViewer
from structure_controls import StructureControlsWidget
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, \
    QPushButton, QHBoxLayout, QFrame, QHeaderView, QFileDialog, QAbstractItemView, QLabel
from PyQt5.QtCore import pyqtSlot, Qt, pyqtSignal
from collections import OrderedDict
import numpy as np
from periodic_table import PeriodicTable

class StructureVariableControls(QWidget):

    def __init__(self, structure_control_widget):
        super().__init__(structure_control_widget)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        # Store the data manager
        self.structure_control_widget = structure_control_widget

        # Initialize table and populate
        self.createTable()
        self.btns_layout = QHBoxLayout()

        self.save_poscar_btn = QPushButton("Save Poscar")
        self.save_poscar_btn.clicked.connect(self.save_poscar)

        self.delete_atoms_btn = QPushButton("Delete")
        self.delete_atoms_btn.clicked.connect(self.delete_atoms)

        self.x_t_btn = QPushButton("T")
        self.x_t_btn.clicked.connect(lambda: self.change_constrain(4, "T"))
        self.x_f_btn = QPushButton("F")
        self.x_f_btn.clicked.connect(lambda: self.change_constrain(4, "F"))
        self.y_t_btn = QPushButton("T")
        self.y_t_btn.clicked.connect(lambda: self.change_constrain(5, "T"))
        self.y_f_btn = QPushButton("F")
        self.y_f_btn.clicked.connect(lambda: self.change_constrain(5, "F"))
        self.z_t_btn = QPushButton("T")
        self.z_t_btn.clicked.connect(lambda: self.change_constrain(6, "T"))
        self.z_f_btn = QPushButton("F")
        self.z_f_btn.clicked.connect(lambda: self.change_constrain(6, "F"))

        btns = [self.x_t_btn, self.x_f_btn, self.y_t_btn, self.y_f_btn, self.z_t_btn, self.z_f_btn]
        self.btns_layout.addWidget(self.save_poscar_btn)
        self.btns_layout.addWidget(self.delete_atoms_btn)
        self.btns_layout.addWidget(QLabel("X"))
        self.btns_layout.addWidget(btns[0])

        self.btns_layout.addWidget(btns[1])
        self.btns_layout.addWidget(QLabel("Y"))
        self.btns_layout.addWidget(btns[2])
        self.btns_layout.addWidget(btns[3])
        self.btns_layout.addWidget(QLabel("Z"))
        self.btns_layout.addWidget(btns[4])
        self.btns_layout.addWidget(btns[5])



        self.layout.addLayout(self.btns_layout)
        self.layout.addWidget(self.tableWidget)

        self.structure_control_widget.selected_actors_changed.connect(self.rectangle_rows_selection)



    def createTable(self):
        self.tableWidget = QTableWidget()
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.MultiSelection)

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
            self.tableWidget.setItem(row, 1, QTableWidgetItem(str(f'{x:.2f}')))
            self.tableWidget.setItem(row, 2, QTableWidgetItem(str(f'{y:.2f}')))
            self.tableWidget.setItem(row, 3, QTableWidgetItem(str(f'{z:.2f}')))
            self.tableWidget.setItem(row, 4, QTableWidgetItem(move_x))
            self.tableWidget.setItem(row, 5, QTableWidgetItem(move_y))
            self.tableWidget.setItem(row, 6, QTableWidgetItem(move_z))

            # Add a delete button in the last column
            #delete_button = QPushButton("Delete")
            #delete_button.clicked.connect(lambda _, r=row: self.deleteRow(r))
            #self.tableWidget.setCellWidget(row, 7, delete_button)

        # Connect the cellChanged signal to the updateData method
        self.tableWidget.cellChanged.connect(self.updateData)
        self.tableWidget.itemSelectionChanged.connect(self.on_selection_changed)

        self.structure_control_widget.structure_plot_widget.plotter.add_key_event('Delete', self.delete_atoms)

    @pyqtSlot(int, int)
    def updateData(self, row, column):

        if column in [1, 2, 3, 4, 5, 6]:  # Only update if X, Y, Z, Move X, Move Y, or Move Z columns are edited
            try:
                if column in [1, 2, 3]:  # X, Y, Z columns (float)
                    new_value = float(self.tableWidget.item(row, column).text())
                    self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][0][row][column - 1] = new_value
                    self.structure_control_widget.add_sphere()
                    self.structure_control_widget.add_bonds()
                else:  # Move X, Move Y, Move Z columns (T or F)
                    new_value = self.tableWidget.item(row, column).text()
                    if new_value.upper() in ['T', 'F']:
                        self.structure_control_widget.structure_plot_widget.data.all_constrains[row][column - 4] = new_value.upper()
                    else:
                        raise ValueError("Movement constraint must be 'T' or 'F'.")

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

    def on_selection_changed(self):
        actors = self.structure_control_widget.structure_plot_widget.sphere_actors
        self.structure_control_widget.selected_actors = []
        for index, actor in enumerate(actors):
            actor.prop.color = self.structure_control_widget.structure_plot_widget.atom_colors[index]

        selected_items = self.tableWidget.selectedItems()
        if not selected_items:
            return

        selected_rows = set()
        for item in selected_items:
            selected_rows.add(item.row())
        for row in selected_rows:
            if 0 <= row < len(actors):
                actors[row].prop.color = 'yellow'
                self.structure_control_widget.selected_actors.append(actors[row])

    def is_row_selected(self, row):
        column_count = self.tableWidget.columnCount()
        for column in range(column_count-2):
            if not self.tableWidget.item(row, column).isSelected():
                return False
        return True

    def rectangle_rows_selection(self):
        self.tableWidget.clearSelection()
        rows = self.get_selected_rows()
        for row in rows:
            self.tableWidget.selectRow(row)

    def get_selected_rows(self):
        rows = []
        for actor in self.structure_control_widget.selected_actors:
            if actor in self.structure_control_widget.structure_plot_widget.sphere_actors:
                rows.append(self.structure_control_widget.structure_plot_widget.sphere_actors.index(actor))
        return rows

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

    def delete_atoms(self):
        selected_rows = sorted(set(item.row() for item in self.tableWidget.selectedItems()), reverse=True)
        for index in selected_rows:
            self.deleteRow(index)
        self.structure_control_widget.add_sphere()
        self.structure_control_widget.add_bonds()

    def add_atom(self):
        self.atom_choose_window = AtomChooseWindow()
        self.atom_choose_window.show()
        self.atom_choose_window.sig.connect(self.change_data_when_atom_added)

    def change_data_when_atom_added(self):
        self.name, self.x, self.y, self.z, self.x_constr, self.y_constr, self.z_constr = self.atom_choose_window.get_atom_and_coords()
        names = self.structure_control_widget.structure_plot_widget.data.symbols
        if self.name in names:
            pos = next(i for i in reversed(range(len(names))) if names[i] == self.name)
        else:
            pos = len(self.structure_control_widget.structure_plot_widget.data.symbols)
        self.structure_control_widget.structure_plot_widget.data.symbols.insert(pos + 1, self.name)
        if self.name in names:
            self.structure_control_widget.structure_plot_widget.data.atoms_symb_and_num.insert(pos + 1,
                                                                                               "".join([self.name,
                                                                                                        str(pos + 2)]))
        else:
            self.structure_control_widget.structure_plot_widget.data.atoms_symb_and_num.insert(pos + 1,
                                                                                               "".join([self.name,
                                                                                                        str(pos + 1)]))
        for interation in self.structure_control_widget.structure_plot_widget.data.outcar_coordinates:
            interation[0].insert(pos + 1, [float(self.x), float(self.y), float(self.z)])
        self.structure_control_widget.structure_plot_widget.data.all_constrains.insert(pos + 1, [self.x_constr, self.y_constr, self.z_constr])
        self.structure_control_widget.structure_plot_widget.data.constrains.insert(pos + 1, self.x_constr)

        self.change_table_when_atom_added()
        print("added")

    def change_table_when_atom_added(self):
        self.tableWidget.blockSignals(True)
        self.tableWidget.clearContents()
        self.layout.removeWidget(self.tableWidget)
        self.tableWidget.blockSignals(False)

        # Rebuild the table with the updated data
        self.createTable()

        # Add the new table to the layout
        self.layout.addWidget(self.tableWidget)
        self.structure_control_widget.structure_plot_widget.update_atom_colors()
        self.structure_control_widget.add_sphere()
        self.structure_control_widget.add_bonds()

    def change_constrain(self, column, constrain):
        indexes = self.tableWidget.selectionModel().selectedRows()
        for index in sorted(indexes):
            self.tableWidget.setItem(index.row(), column, QTableWidgetItem(constrain))
            self.updateData(index.row(), column)

    def translate_object(self, direction):
        camera = self.structure_control_widget.plotter.camera

        # Get camera position and focal point
        camera_position = np.array(camera.GetPosition())
        focal_point = np.array(camera.GetFocalPoint())

        # Calculate the viewing direction (normal to the camera)
        view_direction = focal_point - camera_position
        view_direction /= np.linalg.norm(view_direction)  # Normalize the vector

        # Get the view up direction
        view_up = np.array(camera.GetViewUp())

        # Calculate the right direction (left-to-right on the screen)
        right_direction = np.cross(view_direction, view_up)
        right_direction /= np.linalg.norm(right_direction)  # Normalize the vector

        # Calculate the distance to move (1% of the interactor width)
        interactor_size = self.structure_control_widget.plotter.interactor.GetSize()
        move_distance = 0.001 * interactor_size[0]  # 1% of the interactor width

        # Determine translation vector based on the direction
        if direction == 'right':
            translation_vector = move_distance * right_direction
        elif direction == 'left':
            translation_vector = -move_distance * right_direction
        elif direction == 'up':
            translation_vector = move_distance * view_up
        elif direction == 'down':
            translation_vector = -move_distance * view_up
        elif direction == 'in':
            translation_vector = -move_distance * view_direction
        elif direction == 'out':
            translation_vector = move_distance * view_direction

        coordinates = self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[
                self.structure_control_widget.geometry_slider.value()][0]

        selected_rows = self.get_selected_rows()

        for actor, row in zip(self.structure_control_widget.selected_actors, selected_rows):
            actor.mapper.dataset.points += translation_vector
            coordinates[row][0] = actor.center[0]
            coordinates[row][1] = actor.center[1]
            coordinates[row][2] = actor.center[2]

        self.tableWidget.blockSignals(True)
        self.tableWidget.clearContents()
        self.layout.removeWidget(self.tableWidget)
        self.tableWidget.blockSignals(False)

        # Rebuild the table with the updated data
        self.createTable()

        # Add the new table to the layout
        self.layout.addWidget(self.tableWidget)

        self.tableWidget.clearSelection()
        for row in selected_rows:
            self.tableWidget.selectRow(row)

        self.structure_control_widget.add_bonds()

        # Update the plotter
        #self.plotter.update()


class AtomChooseWindow(QWidget):
    sig = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()

        self.atom_coords_layout = QHBoxLayout()

        self.coords_table = QTableWidget()
        self.coords_table.setRowCount(3)
        self.coords_table.setColumnCount(4)

        self.coords_table.setItem(0,0,QTableWidgetItem("atom: "))
        self.atom_name = QTableWidgetItem("")
        self.coords_table.setItem(0,4, self.atom_name)

        self.resize(640, 300)

        self.periodic_table = PeriodicTable()
        self.periodic_table.element_selected.connect(self.update_label)
        self.periodic_table.show()

        self.x_coord = QTableWidgetItem("0")
        self.y_coord = QTableWidgetItem("0")
        self.z_coord = QTableWidgetItem("0")

        self.coords_table.setItem(1, 0, QTableWidgetItem("coordinates:"))
        self.coords_table.setItem(1, 1, self.x_coord)
        self.coords_table.setItem(1, 2, self.y_coord)
        self.coords_table.setItem(1, 3, self.z_coord)

        self.coords_table.setItem(2, 0, QTableWidgetItem("constraints:"))
        self.coords_table.setItem(2, 1, QTableWidgetItem("F"))
        self.coords_table.setItem(2, 2, QTableWidgetItem("F"))
        self.coords_table.setItem(2, 3, QTableWidgetItem("F"))

        self.atom_coords_layout.addWidget(self.coords_table)

        self.layout.addLayout(self.atom_coords_layout)
        self.setLayout(self.layout)

        self.buttons_layout = QHBoxLayout()
        self.add_button = QPushButton("add")
        self.buttons_layout.addWidget(self.add_button)
        self.add_button.clicked.connect(self.add_atom)

        self.discard_button = QPushButton("discard")
        self.buttons_layout.addWidget(self.discard_button)
        self.discard_button.clicked.connect(self.discard)
        self.layout.addLayout(self.buttons_layout)

        self.coords_table.horizontalHeader().hide()
        self.coords_table.verticalHeader().hide()

    def update_label(self, element):
        self.atom_name = QTableWidgetItem(element)
        self.coords_table.setItem(0,3, self.atom_name)

    def get_atom_and_coords(self):
        name = self.atom_name.text()
        x = self.coords_table.item(1,1).text()
        y = self.coords_table.item(1,2).text()
        z = self.coords_table.item(1, 3).text()
        x_constr = self.coords_table.item(2, 1).text()
        y_constr = self.coords_table.item(2, 2).text()
        z_constr = self.coords_table.item(2, 3).text()

        return name, x, y, z, x_constr, y_constr, z_constr

    def add_atom(self):
        try:
            if self.atom_name.text() != '':
                self.sig.emit()
                self.close()
        except:
            print("no atom added")

    def discard(self):
        self.close()
        self.periodic_table.close()

class MovementRangeWindow(QWidget):
    movement_range = pyqtSignal()
    def __init__(self):
        super().__init__()
