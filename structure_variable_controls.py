import time
tic = time.perf_counter()
from PyQt5.QtGui import QCloseEvent,QDropEvent
from structure_plot import StructureViewer
from structure_controls import StructureControlsWidget
import sys, platform, os
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, \
    QPushButton, QHBoxLayout, QFrame, QHeaderView, QFileDialog, QAbstractItemView, QLabel, QLineEdit, QCheckBox, \
    QDialog, QDialogButtonBox
from PyQt5.QtCore import pyqtSlot, Qt, pyqtSignal, QItemSelection, QItemSelectionModel
from collections import OrderedDict
import numpy as np
from periodic_table import PeriodicTable
from itertools import groupby, combinations
import numpy as np
from ase.io import read
from ase.neighborlist import NeighborList, natural_cutoffs
from ase.constraints import FixAtoms, FixBondLength, FixLinearTriatomic
toc = time.perf_counter()
print(f'importing in structure variable controls: {toc - tic:0.4f}')

def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()  # Record the start time
        result = func(*args, **kwargs)  # Call the original function
        end_time = time.time()  # Record the end time
        execution_time = end_time - start_time
        print(f"Function '{func.__name__}' executed in {execution_time:.4f} seconds.")
        return result  # Return the original function's result
    return wrapper

class TableWidgetDragRows(QTableWidget):
    def __init__(self, structureControlWidget):
        super().__init__(structureControlWidget)

        self.structure_control_widget = structureControlWidget
        self.control = self.structure_control_widget.structure_control_widget
        self.plot = self.control.structure_plot_widget

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        
    def dropEvent(self, event: QDropEvent):
        self.blockSignals(True)
        if not event.isAccepted() and event.source() == self:
            drop_row = self.drop_on(event)

            rows = sorted(set(item.row() for item in self.selectedItems()))
            rows_to_move = [[QTableWidgetItem(self.item(row_index, column_index)) for column_index in range(self.columnCount())]
                            for row_index in rows]
            for row_index in reversed(rows):
                self.removeRow(row_index)
                if row_index < drop_row:
                    drop_row -= 1

            for row_index, data in enumerate(rows_to_move):
                row_index += drop_row
                self.insertRow(row_index)
                for column_index, column_data in enumerate(data):
                    self.setItem(row_index, column_index, column_data)
            event.accept()
            for row_index in range(len(rows_to_move)):
                self.item(drop_row + row_index, 0).setSelected(True)
                self.item(drop_row + row_index, 1).setSelected(True)
        super().dropEvent(event)

        self.update_all_data()

        self.blockSignals(False)
        self.structure_control_widget.change_table_when_atom_added()

    def update_all_data(self):
        for column in range(self.columnCount()):
            text = self.horizontalHeaderItem(column).text()
            for row in range(self.rowCount()):
                if text == "MagMom":
                    self.plot.data.magmoms[row] = self.item(row, column).text()
                if text == "Tag":
                    self.plot.data.suffixes[row] = self.item(row, column).text()
                if text == 'Atom':
                    self.plot.data.symbols[row] = self.item(row, column).text()
                if text in ['X', 'Y', 'Z']:
                    new_value = float(self.item(row, column).text())
                    self.plot.data.outcar_coordinates[self.control.geometry_slider.value()][row][column - 3] = new_value
                elif text in ["Move X", "Move Y", "Move Z"]: # Move X, Move Y, Move Z columns (T or F)
                    new_value = self.item(row, column).text()
                    self.plot.data.all_constrains[row][
                            column - 6] = new_value.upper()

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()

        return index.row() + 1 if self.is_below(event.pos(), index) else index.row()

    def is_below(self, pos, index):
        rect = self.visualRect(index)
        margin = 2
        if pos.y() - rect.top() < margin:
            return False
        elif rect.bottom() - pos.y() < margin:
            return True
        # noinspection PyTypeChecker
        return rect.contains(pos, True) and not (int(self.model().flags(index)) & Qt.ItemIsDropEnabled) and pos.y() >= rect.center().y()

    def keyPressEvent(self, event):
        #super().keyPressEvent(event)
        if event.key() == Qt.Key_C: # and (event.modifiers() & Qt.ControlModifier):
            self.copy_table()

    def copy_table(self):
        copied_cells = sorted(self.selectedIndexes())

        copy_text = ''
        try:
            max_column = copied_cells[-1].column()
            for c in copied_cells:
                copy_text += self.item(c.row(), c.column()).text()
                if c.column() == max_column:
                    copy_text += '\n'
                else:
                    copy_text += '\t'
            QApplication.clipboard().setText(copy_text)
            print("copied")
        except IndexError:
            print("No selected rows!")


class StructureVariableControls(QWidget):

    def __init__(self, structure_control_widget):
        super().__init__(structure_control_widget)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        # Store the data manager
        self.structure_control_widget = structure_control_widget

        # Initialize table and populate
        self.createTable()
        # add first row buttons layout
        self.btns_layout = QHBoxLayout()

        # create and connect buttons
        self.save_poscar_btn = QPushButton("Save Poscar")
        self.save_poscar_btn.clicked.connect(self.save_poscar)

        self.delete_atoms_btn = QPushButton("Delete")
        self.delete_atoms_btn.clicked.connect(self.delete_atoms)

        self.x_t_btn = QPushButton("T")
        self.x_t_btn.clicked.connect(lambda: self.change_constrain(6, "T"))
        self.x_f_btn = QPushButton("F")
        self.x_f_btn.clicked.connect(lambda: self.change_constrain(6, "F"))
        self.y_t_btn = QPushButton("T")
        self.y_t_btn.clicked.connect(lambda: self.change_constrain(7, "T"))
        self.y_f_btn = QPushButton("F")
        self.y_f_btn.clicked.connect(lambda: self.change_constrain(7, "F"))
        self.z_t_btn = QPushButton("T")
        self.z_t_btn.clicked.connect(lambda: self.change_constrain(8, "T"))
        self.z_f_btn = QPushButton("F")
        self.z_f_btn.clicked.connect(lambda: self.change_constrain(8, "F"))

        # add buttons to layout
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

        # row of selection
        self.selected_atoms_btn_layout = QHBoxLayout()
        self.print_selected_atoms_btn = QPushButton("print")
        self.add_selection_input_field = QLineEdit()
        self.add_selection_input_field.setMaximumWidth(800)
        self.select_added_atoms = QPushButton("add")

        # add and connect buttons
        self.selected_atoms_btn_layout.addWidget(self.print_selected_atoms_btn)
        self.print_selected_atoms_btn.clicked.connect(self.print_selected_atoms)
        self.selected_atoms_btn_layout.addWidget(self.add_selection_input_field)
        self.selected_atoms_btn_layout.addWidget(self.select_added_atoms)
        self.select_added_atoms.clicked.connect(self.add_input_to_selection)

        self.layout.addLayout(self.selected_atoms_btn_layout)

        # row of magmoms
        self.another_btn_layout = QHBoxLayout()
        self.print_magmom_btn = QPushButton("print magmoms")
        self.set_magmom_input_field = QLineEdit()
        self.set_magmom_input_field.setMaximumWidth(800)
        self.set_magmom_btn = QPushButton("set magmom")

        self.print_magmom_btn.clicked.connect(self.print_magmoms)
        self.set_magmom_btn.clicked.connect(self.set_magmoms)

        self.another_btn_layout.addWidget(self.print_magmom_btn)
        self.another_btn_layout.addWidget(self.set_magmom_input_field)
        self.another_btn_layout.addWidget(self.set_magmom_btn)
        self.layout.addLayout(self.another_btn_layout)

        # row of tags
        self.tags_btn_layout = QHBoxLayout()
        self.sort_by_tags_btn = QPushButton("sort")
        self.set_tags_btn = QPushButton("set tags")
        self.rattle_btn = QPushButton("rattle")
        self.set_tags_input_field = QLineEdit()

        self.set_tags_btn.clicked.connect(self.set_tags)
        self.sort_by_tags_btn.clicked.connect(self.sort_by_tags)
        self.rattle_btn.clicked.connect(self.rattle)

        self.tags_btn_layout.addWidget(self.sort_by_tags_btn)
        self.tags_btn_layout.addWidget(self.rattle_btn)
        self.tags_btn_layout.addWidget(self.set_tags_input_field)
        self.tags_btn_layout.addWidget(self.set_tags_btn)
        self.layout.addLayout(self.tags_btn_layout)


        self.layout.addWidget(self.tableWidget)

        self.structure_control_widget.selected_actors_changed.connect(self.rectangle_rows_selection)



    def createTable(self):
        self.tableWidget = TableWidgetDragRows(self)
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.MultiSelection)

        self.tableWidget.setSortingEnabled(True)
        self.tableWidget.horizontalHeader().sortIndicatorChanged.connect(self.sort_by_column)

        # Get data from the data manager
        atom_num_and_symb, coordinates, constraints, magmoms, suffixes = self.structure_control_widget.get_table_data()

        # Set row count based on the data
        num_atoms = len(atom_num_and_symb)
        self.tableWidget.setRowCount(num_atoms)
        self.tableWidget.setColumnCount(10)  # Extra columns for constraints and delete button

        # Set table headers
        headers = ["Atom", "Number", "Tag", "X", "Y", "Z", "Move X", "Move Y", "Move Z", "MagMom"]
        self.tableWidget.setHorizontalHeaderLabels(headers)
        #header = self.tableWidget.horizontalHeader()
        #header.setSectionResizeMode(QHeaderView.ResizeToContents)
        #header.setSectionResizeMode(0, QHeaderView.Stretch)

        for i in range(self.tableWidget.columnCount()):
            self.tableWidget.horizontalHeader().setSectionResizeMode(i,QHeaderView.Stretch)
        #resizeSection(logicalIndex, size)
        # Add data to the table
        for row in range(num_atoms):
            atom = atom_num_and_symb[row]
            x, y, z = coordinates[row]
            move_x, move_y, move_z = constraints[row]
            magmom =magmoms[row]
            suffix = suffixes[row]

            self.tableWidget.setItem(row, 0, QTableWidgetItem(atom))
            self.tableWidget.setItem(row, 1, QTableWidgetItem(str(row+1)))
            self.tableWidget.setItem(row, 2, QTableWidgetItem(suffix))
            self.tableWidget.setItem(row, 3, QTableWidgetItem(str(f'{x:.2f}')))
            self.tableWidget.setItem(row, 4, QTableWidgetItem(str(f'{y:.2f}')))
            self.tableWidget.setItem(row, 5, QTableWidgetItem(str(f'{z:.2f}')))
            self.tableWidget.setItem(row, 6, QTableWidgetItem(move_x))
            self.tableWidget.setItem(row, 7, QTableWidgetItem(move_y))
            self.tableWidget.setItem(row, 8, QTableWidgetItem(move_z))
            self.tableWidget.setItem(row, 9, QTableWidgetItem(str(magmom)))

        # Connect the cellChanged signal to the updateData method
        self.tableWidget.cellChanged.connect(self.updateData)
        self.tableWidget.itemSelectionChanged.connect(self.on_selection_changed)
        self.tableWidget.horizontalHeader().setResizeContentsPrecision(-1)
        self.structure_control_widget.structure_plot_widget.plotter.add_key_event('Delete', self.delete_atoms)

    def find_headers(self, row, column):
        header = self.tableWidget.horizontalHeaderItem(column).text()  # Get the header of the changed column
        new_value = self.tableWidget.item(row, column).text()  # Get the new value from the cell
        labels = []
        for num in range(self.tableWidget.columnCount()):
            item = self.tableWidget.horizontalHeaderItem(num).text()
            labels.append(item)

        # Assuming each row in self.data corresponds to a list and headers are keys
        # Update the correct field in your data list
        header_to_index = {header: idx for idx, header in enumerate(labels)}
        return header_to_index

    @pyqtSlot(int, int)
    def updateData(self, row, column):
        """Update the data list based on the table cell change."""
        header = self.tableWidget.horizontalHeaderItem(column).text()
        header_to_index = self.find_headers(row, column)

        if header in header_to_index:
            # number of column which were updated
            if header in ["X", "Y", "Z"]:
                self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][row][column - 3] = float(new_value)
            if header in ["Move X", "Move Y", "Move Z"]:
                new_value = self.tableWidget.item(row, column).text()
                if new_value.upper() in ['T', 'F', 'N/A']:
                    self.structure_control_widget.structure_plot_widget.data.all_constrains[row][
                        column - 6] = new_value.upper()
                else:
                    raise ValueError("Movement constraint must be 'T' , 'F' or 'N/A'. Resetting to latter")
                    self.structure_control_widget.structure_plot_widget.data.all_constrains[row][
                        column - 6] = 'N/A'
            if header in ["MagMom"]:
                pass
            if header in ["Atom"]:
                pass
            if header in ["Tag"]:
                pass

            '''
            self.data[row][field_index] = new_value  # Update the data list with the new value
            print(f"Updated data[{row}]['{header}'] to {new_value}")
            
            
            
            
        if column in [1, 2, 3, 4, 5, 6]:  # Only update if X, Y, Z, Move X, Move Y, or Move Z columns are edited
            try:
                if column in [1, 2, 3]:  # X, Y, Z columns (float)
                    new_value = float(self.tableWidget.item(row, column).text())
                    self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][row][column - 1] = new_value

                elif column in  [4,5,6]:  # Move X, Move Y, Move Z columns (T or F)
                    new_value = self.tableWidget.item(row, column).text()
                    if new_value.upper() in ['T', 'F', 'N/A']:
                        self.structure_control_widget.structure_plot_widget.data.all_constrains[row][column - 4] = new_value.upper()
                    else:
                        raise ValueError("Movement constraint must be 'T' or 'F'.")
                self.structure_control_widget.add_sphere()
                self.structure_control_widget.add_bonds()
            except ValueError:
                print("Invalid input.")
                # Revert to the old value
                if column in [1, 2, 3]:
                    old_value = self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][row][column - 1]
                else:
                    old_value = self.structure_control_widget.structure_plot_widget.data.constrains[row][column - 4]
                self.tableWidget.blockSignals(True)
                self.tableWidget.setItem(row, column, QTableWidgetItem(str(old_value)))
                self.tableWidget.blockSignals(False)
            '''

    def after_update_data(self):
        self.structure_control_widget.add_sphere()
        self.structure_control_widget.add_bonds()

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
        if self.structure_control_widget.selected_actors == []:
            self.tableWidget.clearSelection()
        rows = self.get_selected_rows()
        self.tableWidget.blockSignals(True)
        #for row in rows:
        #    self.tableWidget.selectRow(row)
        selection = QItemSelection()
        for row in rows:
            top_left = self.tableWidget.model().index(row, 0)
            bottom_right = self.tableWidget.model().index(row, self.tableWidget.columnCount()-1)
            selection.select(top_left, bottom_right)
        selection_model = self.tableWidget.selectionModel()
        selection_model.select(selection, QItemSelectionModel.Select)
        self.tableWidget.blockSignals(False)

    def get_selected_rows(self):
        rows = []
        for actor in self.structure_control_widget.selected_actors:
            if actor in self.structure_control_widget.structure_plot_widget.sphere_actors:
                rows.append(self.structure_control_widget.structure_plot_widget.sphere_actors.index(actor))
        return rows

    def save_poscar(self):
        # Open a file dialog to save the text file
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save POSCAR", "", "All Files (*)", options=options)

        x = self.structure_control_widget.structure_plot_widget.data.x
        y = self.structure_control_widget.structure_plot_widget.data.y
        z = self.structure_control_widget.structure_plot_widget.data.z
        atoms_list = self.structure_control_widget.structure_plot_widget.data.symbols
        tags_list = self.structure_control_widget.structure_plot_widget.data.suffixes
        atoms_list = [a + b for a, b in zip(atoms_list, tags_list)]
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

        coordinates = self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()]
        constrains = self.structure_control_widget.structure_plot_widget.data.all_constrains
        if file_name:
            # Remove file extension if it exists
            if '.' in file_name:
                file_name = file_name.rsplit('.', 1)[0]
            with open(file_name, 'w') as file:
                file.write("created by Leszek Nowakowski with DOSwizard \n")
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
        name,  x,  y,  z,  x_constr,  y_constr,  z_constr,  magmom , suffix = self.atom_choose_window.get_atom_and_coords()
        names = self.structure_control_widget.structure_plot_widget.data.symbols
        if  name in names:
            pos = next(i for i in reversed(range(len(names))) if names[i] ==  name)
        else:
            pos = len(self.structure_control_widget.structure_plot_widget.data.symbols)
        self.structure_control_widget.structure_plot_widget.data.symbols.insert(pos + 1,  name)
        if  name in names:
            self.structure_control_widget.structure_plot_widget.data.atoms_symb_and_num.insert(pos + 1,
                                                                                               "".join([ name,
                                                                                                       str(pos+2)]))
        else:
            self.structure_control_widget.structure_plot_widget.data.atoms_symb_and_num.insert(pos + 1,
                                                                                               "".join([ name,
                                                                                                       str(pos+1)]))
        for interation in self.structure_control_widget.structure_plot_widget.data.outcar_coordinates:
            interation.insert(pos + 1, [float( x), float( y), float( z)])
        self.structure_control_widget.structure_plot_widget.data.all_constrains.insert(pos + 1, [ x_constr,  y_constr,  z_constr])
        self.structure_control_widget.structure_plot_widget.data.constrains.insert(pos + 1,  x_constr)
        self.structure_control_widget.structure_plot_widget.data.magmoms.insert(pos + 1, magmom)
        self.structure_control_widget.structure_plot_widget.data.suffixes.insert(pos + 1, suffix)

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
        self.structure_control_widget.structure_plot_widget.assign_missing_colors()
        self.structure_control_widget.add_sphere()
        self.structure_control_widget.add_bonds()

    def change_constrain(self, column, constrain):
        indexes = self.tableWidget.selectionModel().selectedRows()
        for index in sorted(indexes):
            self.tableWidget.setItem(index.row(), column, QTableWidgetItem(constrain))
            self.updateData(index.row(), column)
            self.structure_control_widget.structure_plot_widget.data.constrains[index.row()] = constrain

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
                self.structure_control_widget.geometry_slider.value()]

        selected_rows = self.get_selected_rows()

        for actor, row in zip(self.structure_control_widget.selected_actors, selected_rows):

            actor.mapper.dataset.points += translation_vector
            coordinates[row][0] = actor.center[0]
            coordinates[row][1] = actor.center[1]
            coordinates[row][2] = actor.center[2]
            """
            coordinates[row][0] += translation_vector[0]
            coordinates[row][1] += translation_vector[1]
            coordinates[row][2] += translation_vector[2]
            """
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
        #self.structure_control_widget.add_sphere()
        self.structure_control_widget.add_bonds()

        # Update the plotter
        #self.plotter.update()

    def print_selected_atoms(self):
        selected_rows = self.get_selected_rows()
        selected_atoms = [x + 1 for x in selected_rows]
        print("Selected atoms numbers:")
        print(selected_atoms)
        return selected_atoms

    def add_input_to_selection(self):
        def strip_if_not_number(s):
            if len(s) > 1:
                # Check if the first character is not a digit
                if not s[0].isdigit():
                    s = s[1:]
                # Check if the last character is not a digit
                if not s[-1].isdigit():
                    s = s[:-1]
            return s
        text = strip_if_not_number(self.add_selection_input_field.text())
        atoms = [int(x) for x in text.split(',')]
        for number in atoms:
            self.tableWidget.selectRow(number)

    def print_magmoms(self): #TODO fix wrong column print
        mags = []
        for row in range(self.tableWidget.rowCount()):
            mags.append(self.tableWidget.item(row, 7).text())
        # Create the compressed string
        compressed_string = " ".join(
            f"{count}*{key}" if count > 1 else key
            for key, group in groupby(mags)
            for count in [len(list(group))]  # Calculate length only once and store in count
        )

        print('MAGMOM = ' + compressed_string)

    def set_magmoms(self):
        indexes = self.tableWidget.selectionModel().selectedRows()
        for index in sorted(indexes):
            self.tableWidget.setItem(index.row(), 9, QTableWidgetItem(self.set_magmom_input_field.text()))
            self.updateData(index.row(), 9)
        self.after_update_data()

    def set_tags(self):
        tic = time.perf_counter()
        indexes = self.tableWidget.selectionModel().selectedRows()
        self.tableWidget.blockSignals(True)
        for index in sorted(indexes):
            self.tableWidget.setItem(index.row(), 2, QTableWidgetItem(self.set_tags_input_field.text()))
        self.tableWidget.update_all_data()
        self.tableWidget.blockSignals(False)
        toc = time.perf_counter()
        print(f"setting tags: {toc-tic:0.4f} seconds")

    def sort_by_tags(self):
        self.tableWidget.blockSignals(True)
        self.tableWidget.sortByColumn(2, Qt.AscendingOrder)
        self.tableWidget.sortByColumn(0, Qt.AscendingOrder)
        self.tableWidget.update_all_data()
        self.tableWidget.blockSignals(False)
        self.structure_control_widget.structure_plot_widget.assign_missing_colors()
        self.structure_control_widget.add_bonds()
        self.structure_control_widget.add_sphere()

    def sort_by_column(self):
        self.tableWidget.blockSignals(True)
        self.tableWidget.update_all_data()
        self.tableWidget.blockSignals(False)
        self.structure_control_widget.structure_plot_widget.assign_missing_colors()
        self.structure_control_widget.add_bonds()
        self.structure_control_widget.add_sphere()

    def rattle(self):
        coords = self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()]
        selected_rows = []
        new_coords = []
        indexes = self.tableWidget.selectionModel().selectedRows()
        for index in sorted(indexes):
            selected_rows.append(index.row())
        rng = np.random.RandomState()
        displacement = rng.normal(scale=0.05, size=np.array(coords).shape)
        for i in range(len(coords)):
            if i in selected_rows:
                new_coords.append(np.array(coords[i]) + displacement[i])
            else:
                new_coords.append(np.array(coords[i]))

        #new_coords = np.array(selected_coords + displacement).tolist()
        self.tableWidget.blockSignals(True)
        for column in range(3,6):
            for row in range(self.tableWidget.rowCount()):
                self.tableWidget.setItem(row, column, QTableWidgetItem(str(f"{new_coords[row][column-3]:.2f}")))
        self.tableWidget.update_all_data()
        self.tableWidget.blockSignals(False)
        self.structure_control_widget.structure_plot_widget.assign_missing_colors()
        self.structure_control_widget.add_bonds()
        self.structure_control_widget.add_sphere()

    def modify_constraints(self):
        self.atom_choose_window = ConstraintsWindow(self)
        self.atom_choose_window.show()

class AtomChooseWindow(QWidget):
    sig = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()

        self.atom_coords_layout = QHBoxLayout()

        self.coords_table = QTableWidget()
        self.coords_table.setRowCount(4)
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

        self.coords_table.setItem(3, 0, QTableWidgetItem("magmom"))
        self.coords_table.setItem(3, 1, QTableWidgetItem("0"))

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
        magmom = self.coords_table.item(3, 1).text()
        suffix = ""

        return name, x, y, z, x_constr, y_constr, z_constr, magmom, suffix

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

class ConstraintsWindow(QWidget):
    sig = pyqtSignal()
    def __init__(self, parent):
        super().__init__()
        self.parent_class = parent
        self.dir = self.set_working_dir()
        self.poscar =  self.set_structure_file(self.dir)
        self.constraints_list = []
        self.process_structure_file()
        #self.atoms = read(self.poscar)
        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout()
        self.checkboxes_layout = QHBoxLayout()

        self.bonds_cb = QCheckBox()
        self.angles_cb = QCheckBox()

        self.bonds_cb.setChecked(False)
        self.bonds_cb.setText("Bond length constrain")
        self.bonds_cb.stateChanged.connect(self.bonds_constraints_changed)

        self.angles_cb.setChecked(False)
        self.angles_cb.setText("Angle constrain")
        self.angles_cb.stateChanged.connect(self.angles_constraints_changed)

        self.checkboxes_layout.addWidget(self.bonds_cb)
        self.checkboxes_layout.addWidget(self.angles_cb)

        self.layout.addLayout(self.checkboxes_layout)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout.addWidget(self.buttonBox)

        self.setLayout(self.layout)

    def set_working_dir(self):
        """ gets the current working dir. Useful for building"""
        if platform.system() == 'Linux':
            dir = './'
        elif platform.system() == 'Windows':
            path = "F:\\syncme\\modelowanie DFT\\lobster_tests\\Mn"
            if os.path.isdir(path):
                dir = path
            else:
                dir = ("D:\\test_fir_doswizard\\4.strange_atom_definition")
                #dir = ("F:\\syncme-from-c120\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt")
                #dir = "D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\Adsorption\\CeO2_100_CeO4-t\\CO\\O1_site"
                #dir = "D:\\syncme-from-c120\\modelowanie DFT\\lobster_tests\\Mn"
                #dir = "C:\\Users\\lesze\\OneDrive\\Dokumenty"
            #print("can't resolve operating system")
        return dir

    def set_structure_file(self, dir):
        if not os.path.exists(os.path.join(dir, 'CONTCAR')) and not os.path.exists(os.path.join(dir, 'POSCAR')):
            for file in os.listdir(dir):
                # Check if the file has a .cell extension
                if file.endswith(".cell"):
                    # Read the .cell file
                    structure = read(os.path.join(dir, file))
                    write(os.path.join(dir, "POSCAR"), structure, format="vasp")
                    poscar_file = os.path.join(dir, "POSCAR")

        if not os.path.exists(os.path.join(dir, 'CONTCAR')):
            if not os.path.exists(os.path.join(dir, 'POSCAR')):
                p = input("eneter file name: ")
                if not os.path.exists(p):
                    raise FileNotFoundError('No important files found! Missing POSCAR')
                else:
                    poscar_file = os.path.join(dir, p)

            else:
                poscar_file = os.path.join(dir, "POSCAR")
        else:
            if os.path.getsize(os.path.join(dir, 'CONTCAR')) > 0:
                poscar_file = os.path.join(dir, "CONTCAR")
            else:
                if not os.path.exists(os.path.join(dir, 'POSCAR')):
                    raise EmptyFile('CONTCAR is found but appears to be empty! POSCAR missing! Check your files')
                else:
                    poscar_file = os.path.join(dir, "POSCAR")
        return poscar_file

    def process_structure_file(self):
        try:
            self.atoms = read(self.poscar)
        except:
            print("atoms in POSCAR have different symbols then standard atomic symbols.")
            print(f'symbols in poscar: {self.parent_class.structure_control_widget.structure_plot_widget.data.atomic_symbols}')

    def get_selected_atoms(self):
        self.selected_atoms = self.parent_class.print_selected_atoms()
        self.selected_atoms = np.array(self.selected_atoms) - 1
        return self.selected_atoms

    def create_neighbor_list(self):
        cutoffs = natural_cutoffs(self.atoms, Ce=1.5)
        self.neighbor_list = NeighborList(cutoffs, self_interaction=False, bothways=True)
        self.neighbor_list.update(self.atoms)

    def set_distance_constraints(self, atom1, atom2):
        const = FixBondLength(atom1, atom2)
        return const

    def set_angle_constraints(self,atom1, atom2, atom3):
        const = FixLinearTriatomic(triples=[(atom1, atom2, atom3)])
        return const

    def find_selected_neighbours(self,atom):
        self.create_neighbor_list()
        indices, offets = self.neighbor_list.get_neighbors(atom)
        indices_in_selected = list(set(indices) & set(self.selected_atoms))
        return indices_in_selected

    def find_constrained_bonds(self,atom):
        neighours = self.find_selected_neighbours(atom)
        bonds = [(atom, neighbour) for neighbour in neighours]
        return bonds

    def find_constrained_triples(self, atom):
        neighours = self.find_selected_neighbours(atom)
        triples = [(a, atom, b) for a, b, in combinations(neighours, 2)]
        return triples

    def constrain_bonds(self, atom):
        bonds = self.find_constrained_bonds(atom)
        for bond in bonds:
            const = self.set_distance_constraints(bond[0], bond[1])
            self.constraints_list.append(const)

    def constrain_triples(self, atom):
        triples = self.find_constrained_triples(atom)
        for triple in triples:
            const = self.set_angle_constraints(triple[0], triple[1], triple[2])
            self.constraints_list.append(const)

    def apply_constraints(self):
        self.atoms.set_constraint(self.constraints_list)

    def constraint_to_ICONST(self, const):
        const = const.todict()
        if const["name"] == "FixBondLengths":
            flag = "R"
            atoms = const['kwargs']['pairs'][0]
            line = [flag, atoms[0]+1, atoms[1]+1, 0]
        if const["name"] == "FixLinearTriatomic":
            flag = "A"
            atoms = const['kwargs']['triples'][0]
            line = [flag, atoms[0]+1, atoms[1]+1, atoms[2]+1, 0]
        return line

    def write_ICONST(self):
        file_name = "ICONST"
        with open(file_name, 'w') as file:
            for const in self.constraints_list:
                line = self.constraint_to_ICONST(const)
                line = " ".join(map(str, line))
                file.write(line)
                file.write('\n')

    def bonds_constraints_changed(self):
        self.get_selected_atoms()
        for atom in self.selected_atoms:
            self.constrain_bonds(atom)

    def angles_constraints_changed(self):
        self.get_selected_atoms()
        for atom in self.selected_atoms:
            self.constrain_triples(atom)

    def accept(self):
        self.write_ICONST()
        self.close()
        print("constrains modified")

    def reject(self):
        self.atoms.set_constraint()
        self.close()
        print("constrains deleted")