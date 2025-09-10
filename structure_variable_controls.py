import time
tic = time.perf_counter()
from PyQt5.QtGui import  QDropEvent, QIcon
from exceptions import EmptyFile
import  os
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, \
    QPushButton, QHBoxLayout, QHeaderView, QFileDialog, QAbstractItemView, QLabel, QLineEdit, QCheckBox, \
     QDialogButtonBox, QSlider, QGroupBox, QMessageBox, QAbstractScrollArea, QSizePolicy, QMenu, QAction
from PyQt5.QtCore import pyqtSlot, Qt, pyqtSignal, QItemSelectionModel, QItemSelection, QPoint
import traceback
from periodic_table import PeriodicTable
from itertools import groupby, combinations
import numpy as np
from ase.io import read
from ase.neighborlist import NeighborList, natural_cutoffs
from ase.constraints import FixBondLength, FixLinearTriatomic
from config import AppConfig
from vtk import vtkNamedColors,  vtkActor, vtkPoints, vtkCellArray, vtkLine, vtkPolyData, vtkPolyDataMapper

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

class DebugSelectionModel(QItemSelectionModel):
    def select(self, selection, flags):
        print("\n=== QItemSelectionModel.select() called ===")
        print("printing traceback")
        try:
            traceback.print_stack(limit=50)
        except:
            print("traceback not printed")
        print(f"Selection: {selection}, Flags: {flags}")
        super().select(selection, flags)


class TableWidgetDragRows(QTableWidget):
    def __init__(self, structure_control_widget):
        super().__init__(structure_control_widget)

        self.structure_control_widget = structure_control_widget
        self.control = self.structure_control_widget.structure_control_widget
        self.plot = self.control.structure_plot_widget

        self.disable_dragdrop()

    def enable_dragdrop(self):
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def disable_dragdrop(self):
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)

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


# noinspection PyUnresolvedReferences
class StructureVariableControls(QWidget):
    atom_deleted = pyqtSignal(int)
    all_atoms_deleted = pyqtSignal(str)
    def __init__(self, structure_control_widget, parent=None):
        super().__init__(structure_control_widget)

        self.bonds = []
        self.tableWidget = None
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)


        # Store the data manager
        self.structure_control_widget = structure_control_widget
        self.parent = parent

        # Initialize table and populate
        self.create_table()

        # add first row buttons layout
        self.btns_layout = QHBoxLayout()

        # create and connect buttons
        self.save_poscar_btn = QPushButton("Save Poscar")
        self.save_poscar_btn.clicked.connect(lambda : self.save_poscar(target="default"))

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
        for btn in btns:
            btn.setMinimumWidth(5)
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
        self.tableWidget.setMinimumWidth(0)

        self.structure_control_widget.selected_actors_changed.connect(self.rectangle_rows_selection)
        self.structure_control_widget.geometry_slider.valueChanged.connect(self.update_bonds)
        self.movement_slider_value = 50

    def create_table(self):
        self.tableWidget = TableWidgetDragRows(self)
        self.tableWidget.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.MultiSelection)

        self.tableWidget.setSortingEnabled(True)
        self.tableWidget.horizontalHeader().sortIndicatorChanged.connect(self.sort_by_column)

        # Get data from the data manager
        atom_num_and_symb, coordinates, constraints, magmoms, suffixes, mags = self.structure_control_widget.get_table_data()

        # Set row count based on the data
        num_atoms = len(atom_num_and_symb)
        self.tableWidget.setRowCount(num_atoms)
        self.tableWidget.setColumnCount(11)  # Extra columns for constraints and delete button

        # Set table headers
        headers = ["Atom", "Number", "Tag", "X", "Y", "Z", "Move X", "Move Y", "Move Z", "MagMom", "mags"]
        self.tableWidget.setHorizontalHeaderLabels(headers)

        #for i in range(self.tableWidget.columnCount()):
        #    self.tableWidget.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeToContents)
        self.tableWidget.resizeColumnsToContents()


        # Add data to the table
        for row in range(num_atoms):
            atom = atom_num_and_symb[row]
            x, y, z = coordinates[row]
            move_x, move_y, move_z = constraints[row]
            magmom =magmoms[row]
            suffix = suffixes[row]
            mag = mags[row]

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
            self.tableWidget.setItem(row, 10, QTableWidgetItem(str(mag)))

        # Connect the cellChanged signal to the updateData method
        self.tableWidget.cellChanged.connect(self.updateData)
        self.tableWidget.itemSelectionChanged.connect(self.on_selection_changed)
        self.structure_control_widget.structure_plot_widget.plotter.add_key_event('Delete', self.delete_atoms)

        # Enable custom context menu on header
        header = self.tableWidget.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_menu)

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

    def update_data(self):
        self.change_table_when_atom_added()
        self.remove_bond_lengths()

    @pyqtSlot(int, int)
    def updateData(self, row, column):
        """Update the data list based on the table cell change."""
        header = self.tableWidget.horizontalHeaderItem(column).text()
        header_to_index = self.find_headers(row, column)

        if header in header_to_index:
            # number of column which were updated
            if header in ["X", "Y", "Z"]:
                new_value = self.tableWidget.item(row, column).text()
                self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()][row][column - 3] = float(new_value)
            if header in ["Move X", "Move Y", "Move Z"]:
                new_value = self.tableWidget.item(row, column).text()
                if new_value.upper() in ['T', 'F', 'N/A']:
                    self.structure_control_widget.structure_plot_widget.data.all_constrains[row][
                        column - 6] = new_value.upper()
                else:
                    print("Movement constraint must be 'T' , 'F' or 'N/A'. Resetting to latter")
                    self.structure_control_widget.structure_plot_widget.data.all_constrains[row][
                        column - 6] = 'N/A'
            if header in ["MagMom"]:
                pass
            if header in ["Atom"]:
                pass
            if header in ["Tag"]:
                pass
            if header in ["X", "Y", "Z"]:
                self.after_update_data()

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
        self.create_table()

        # Add the new table to the layout
        self.layout.addWidget(self.tableWidget)

    def on_selection_changed(self):
        colors = vtkNamedColors()
        actors = self.structure_control_widget.structure_plot_widget.sphere_actors
        self.structure_control_widget.selected_actors = []
        for index, actor in enumerate(actors):
            color = self.structure_control_widget.structure_plot_widget.atom_colors[index]
            vtk_color = np.array(color)/255
            actor.GetProperty().SetColor(vtk_color)

        selected_rows = self.tableWidget.selectionModel().selectedRows()
        if not selected_rows:
            return

        selected_rows_indexes = set()
        for item in selected_rows:
            selected_rows_indexes.add(item.row())
        for row in selected_rows_indexes:
            if 0 <= row < len(actors):
                actors[row].GetProperty().SetColor(colors.GetColor3d('Yellow'))
                self.structure_control_widget.selected_actors.append(actors[row])

    def is_row_selected(self, row):
        column_count = self.tableWidget.columnCount()
        for column in range(column_count-2):
            if not self.tableWidget.item(row, column).isSelected():
                return False
        return True

    def rectangle_rows_selection(self):
        shift_pressed = False
        if not self.structure_control_widget.selected_actors:
            self.tableWidget.clearSelection()
        rows = self.get_selected_rows()
        self.tableWidget.blockSignals(True)

        # if shift button is pressed, remove prevoiusly selected rows to avoid unselection
        if self.parent.shift_pressed:
            previous_rows = [x.row() for x in self.tableWidget.selectionModel().selectedRows()]
            new_selected_rows = [x for x in rows if x not in previous_rows]
            for row in new_selected_rows:
                self.tableWidget.selectRow(row)
        else:
            for row in rows:
                self.tableWidget.selectRow(row)
        self.tableWidget.blockSignals(False)
        self.on_selection_changed()

    def get_selected_rows(self):
        rows = []
        # this returns all previously and currently selected actors
        for actor in self.structure_control_widget.selected_actors:
            if actor in self.structure_control_widget.structure_plot_widget.sphere_actors:
                rows.append(self.structure_control_widget.structure_plot_widget.sphere_actors.index(actor))
        # if no actors were selected, get selection from table
        if not rows:
            for item in self.tableWidget.selectedItems():
                rows.append(item.row())
        return rows

    def save_poscar(self, target="default"):
        import io
        import tempfile

        # Prepare data
        data = self.structure_control_widget.structure_plot_widget.data
        x, y, z = data.x, data.y, data.z
        atoms_list = [a + b for a, b in zip(data.symbols, data.suffixes)]
        coordinates = data.outcar_coordinates[self.structure_control_widget.geometry_slider.value()]
        constrains = data.all_constrains

        atoms, numbers = data.poscar.atom_lines_as_in_poscar(atoms_list)

        # check for duplicates - if exists, POSCAR can be saved, but VASP will not run, so it is useless
        if len(atoms) != len(set(atoms)):
            QMessageBox.critical(self, "Error",
                                 f"There are duplicates in elements name. VASP can not accept that. Sort elements first (by clicking \"sort\" on structure tab)")
            return
        else:
            # Decide if we're writing to a file or a stream
            if target == "default":
                options = QFileDialog.Options()
                file_name, _ = QFileDialog.getSaveFileName(self, "Save POSCAR", "POSCAR", "All Files (*)", options=options)
                if not file_name:
                    QMessageBox.warning(self, "No File", "No file selected.")
                    return
                stream = open(file_name, 'w')
                close_after = True
            elif isinstance(target, str):
                stream = open(target, 'w')
                close_after = True
            elif isinstance(target, io.StringIO):
                stream = target
                close_after = False
            elif isinstance(target, tempfile._TemporaryFileWrapper):
                stream = target
                close_after = False
            else:
                raise ValueError("Target must be 'default', a file path string, an io.StringIO object or a tempfile._TemporaryFileWrapper object")



            # Write POSCAR content
            stream.write("created by Leszek Nowakowski with VASPy-vis \n")
            stream.write("1.0000000000000\n")
            stream.write(f" {x:.6f}\t0.000000 0.000000\n")
            stream.write(f" 0.0000000 {y:.6f} 0.000000\n")
            stream.write(f" 0.0000000 0.0000000 {z:.6f}\n")
            stream.write(' '.join(atoms) + "\n")
            stream.write(' '.join(map(str, numbers)) + "\n")
            stream.write("Selective dynamics\n")
            stream.write("Cartesian\n")
            for coord, const in zip(coordinates, constrains):
                coord_str = ' '.join(f"{c:.6f}" for c in coord)
                const_str = ' '.join(const)
                stream.write(f" {coord_str}\t{const_str}\n")

            # Finalize
            if close_after:
                stream.close()
                QMessageBox.information(self, "Success", "File saved successfully.")

    def delete_atoms(self):
        selected_rows = sorted(set(item.row() for item in self.tableWidget.selectedItems()), reverse=True)
        for index in selected_rows:
            self.deleteRow(index)
            self.atom_deleted.emit(index)
        self.structure_control_widget.add_sphere()
        self.structure_control_widget.add_bonds()
        self.all_atoms_deleted.emit("done")

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
        self.create_table()

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
        view_angle = camera.GetParallelScale()

        # Calculate the right direction (left-to-right on the screen)
        right_direction = np.cross(view_direction, view_up)
        right_direction /= np.linalg.norm(right_direction)  # Normalize the vector

        # Calculate the distance to move (1% of the interactor width)
        move_distance = 0.001 * view_angle * self.movement_slider_value

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

            points = actor.GetMapper().GetInput().GetPoints()
            num_points = points.GetNumberOfPoints()
            for i in range(num_points):
                new_points = points.GetPoint(i) + translation_vector
                points.SetPoint(i, new_points)
            points.Modified()

            coordinates[row][0] = actor.GetCenter()[0]
            coordinates[row][1] = actor.GetCenter()[1]
            coordinates[row][2] = actor.GetCenter()[2]

        self.block_and_update_table()
        self.structure_control_widget.add_bonds()
        self.update_bonds()

    def block_and_update_table(self):
        self.tableWidget.blockSignals(True)
        self.tableWidget.clearContents()
        self.layout.removeWidget(self.tableWidget)
        self.tableWidget.blockSignals(False)

        # Rebuild the table with the updated data
        self.create_table()

        # Add the new table to the layout
        self.layout.addWidget(self.tableWidget)

        self.tableWidget.clearSelection()
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            self.tableWidget.selectRow(row)

    def show_header_menu(self, pos: QPoint):
        header = self.tableWidget.horizontalHeader()
        menu = QMenu(self)

        # Build menu with checkboxes for each column
        for col in range(self.tableWidget.columnCount()):
            column_name = self.tableWidget.horizontalHeaderItem(col).text()
            action = QAction(column_name, self, checkable=True)

            # Checked if column is currently visible
            action.setChecked(not self.tableWidget.isColumnHidden(col))

            # Connect toggling to show/hide column
            action.toggled.connect(lambda checked, col=col: self.tableWidget.setColumnHidden(col, not checked))
            menu.addAction(action)

        menu.exec_(header.mapToGlobal(pos))

    def rotate_objects(self, lst):
        import ast
        import io
        import tempfile
        from ase.io import read

        phi, theta, psi, center = lst
        center = ast.literal_eval(center)

        tmp_file =  tempfile.NamedTemporaryFile(mode='w', delete=False)
        with tmp_file as tmp:
            self.save_poscar(target=tmp)

        with open(tmp_file.name) as tmp:
            atoms = read(tmp, format="vasp")

        selected_rows = self.get_selected_rows()
        try:
            rot_atoms = atoms[selected_rows].copy()
            if len(rot_atoms) == 0:
                print("no atoms selected")
            else:
                rot_atoms.euler_rotate(phi=float(phi),
                                       theta=float(theta),
                                       psi=float(psi),
                                       center=center)

                rot_positions = rot_atoms.positions
                coordinates = self.structure_control_widget.structure_plot_widget.data.outcar_coordinates[
                    self.structure_control_widget.geometry_slider.value()]

                for pos, row in zip(rot_positions, selected_rows):
                    coordinates[row][0] = pos[0]
                    coordinates[row][1] = pos[1]
                    coordinates[row][2] = pos[2]

                self.block_and_update_table()
                self.structure_control_widget.add_sphere()
                self.structure_control_widget.add_bonds()
        except IndexError:
            print("no atoms selected")

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
            self.tableWidget.selectRow(number-1)

    def print_magmoms(self): #TODO fix wrong column print
        mags = []
        for row in range(self.tableWidget.rowCount()):
            mags.append(self.tableWidget.item(row, 9).text())
        # Create the compressed string
        compressed_string = " ".join(
            f"{count}*{key}" if count > 1 else key
            for key, group in groupby(mags)
            for count in [len(list(group))]  # Calculate length only once and store in count
        )

        print('MAGMOM = ' + compressed_string)

    def set_magmoms(self):
        def check_type(s):
            try:
                int(s)
                return 'int'
            except ValueError:
                try:
                    float(s)
                    return 'float'
                except ValueError:
                    return 'neither'

        indexes = self.tableWidget.selectionModel().selectedRows()
        magmom = self.set_magmom_input_field.text()
        if check_type(magmom) == 'int' or check_type(magmom) == 'float':
            for index in sorted(indexes):
                self.tableWidget.setItem(index.row(), 9, QTableWidgetItem(magmom))
                self.updateData(index.row(), 9)
            self.after_update_data()
        else:
            QMessageBox.warning(self, "Not a number", "A provided text is not a number")

    def set_tags(self):
        indexes = self.tableWidget.selectionModel().selectedRows()
        self.tableWidget.blockSignals(True)
        for index in sorted(indexes):
            self.tableWidget.setItem(index.row(), 2, QTableWidgetItem(self.set_tags_input_field.text()))
        self.tableWidget.update_all_data()
        self.tableWidget.blockSignals(False)

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
        self.modify_constraints_window = ConstraintsWindow(self)
        self.modify_constraints_window.show()

    def set_movement_sensibility(self, value):
        self.movement_slider_value = value

    def move_atoms_widget(self):
        self.move_atoms_qwidget = MoveAtomsWindow(self)
        self.move_atoms_qwidget.show()
        self.move_atoms_qwidget.atom_moved.connect(self.translate_object)
        self.move_atoms_qwidget.slider_value_changed.connect(self.set_movement_sensibility)

        self.move_atoms_qwidget.atom_rotated.connect(self.rotate_objects)

    def add_bond_length(self):
        selected_atoms = self.get_selected_rows()
        if len(selected_atoms) != 2:
            print(f"selected {len(selected_atoms)} atoms. Please select exactly two atoms")
        else:
            idx1, idx2 = selected_atoms
            bond = Bonds(idx1, idx2, self)
            bond.add_bond_length()
            self.bonds.append(bond)

    def remove_bond_lengths(self):
        for bond in self.bonds:
            bond.clear_bond_labels()
        self.bonds = []

    def update_bonds(self):
        for bond in self.bonds:
            bond.clear_bond_labels()
            bond.add_bond_length()

# noinspection PyUnresolvedReferences
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

# noinspection PyUnresolvedReferences
class ConstraintsWindow(QWidget):
    """
    This class opens a constraint modifier window. It writes a POSCAR-like tempfile with current coordinates and
    and constraints, read it as ASE atoms object and allow to further modify constraints
    """
    sig = pyqtSignal()
    def __init__(self, parent):
        super().__init__()
        self.parent_class = parent
        self.constraints_list = []
        self.process_structure_file()
        self.dir = AppConfig.dir

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

    def process_structure_file(self):
        """ saves a POSCAR tempfile and read it to ASE atoms object"""
        import tempfile
        tmp_poscar = tempfile.TemporaryFile(mode='w+t')
        self.parent_class.save_poscar(tmp_poscar)
        tmp_poscar.seek(0)
        try:
            self.atoms = read(tmp_poscar, format='vasp')
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
        file_dialog = QFileDialog()
        file_dialog.setDirectory(self.dir)
        file_name, _ = file_dialog.getSaveFileName(self, "Save ICONST", "ICONST", "All Files (*)")
        if not file_name:
            QMessageBox.information(self, "ICONST", "ICONST not saved")
            return

        path = os.path.join(self.dir, file_name)
        with open(path, 'w') as file:
            for const in self.constraints_list:
                line = self.constraint_to_ICONST(const)
                line = " ".join(map(str, line))
                file.write(line)
                file.write('\n')
        self.close()
        self.file_choose.close()
        print("constrains modified")

    def write_traj(self):
        from ase.io import write
        file_dialog = QFileDialog()
        file_dialog.setDirectory(self.dir)
        file_name, _ = file_dialog.getSaveFileName(self, "Save .traj", "POSCAR.traj", "All Files (*)")
        if not file_name:
            QMessageBox.warning(self, "No File", "No file selected.")
            return
        self.apply_constraints()
        write(file_name[0], self.atoms, format="traj")
        QMessageBox.information(self, "Success", "File saved successfully.")
        self.close()
        self.file_choose.close()
        print("constrains modified")

    def dont_write(self):
        self.apply_constraints()
        self.file_choose.close()
        self.close()
        print("constrains modified")

    def bonds_constraints_changed(self):
        self.get_selected_atoms()
        for atom in self.selected_atoms:
            self.constrain_bonds(atom)

    def angles_constraints_changed(self):
        self.get_selected_atoms()
        for atom in self.selected_atoms:
            self.constrain_triples(atom)

    def accept(self):
        class FileChooseWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.layout = QVBoxLayout()
                self.file_choose_layout = QHBoxLayout()

                self.iconst_button = QPushButton("Save ICONST")
                self.traj_button = QPushButton("Save TRAJ")
                self.none_button = QPushButton("none, just apply constraints")

                self.layout.addWidget(self.iconst_button)
                self.layout.addWidget(self.traj_button)
                self.layout.addWidget(self.none_button)

                self.setLayout(self.layout)

        self.file_choose = FileChooseWindow()
        self.file_choose.show()
        self.file_choose.iconst_button.clicked.connect(self.write_ICONST)
        self.file_choose.traj_button.clicked.connect(self.write_traj)
        self.file_choose.none_button.clicked.connect(self.dont_write)

    def reject(self):
        self.atoms.set_constraint()
        self.close()
        print("constrains deleted")


class MoveAtomsWindow(QWidget):
    atom_moved = pyqtSignal(str)
    atom_rotated = pyqtSignal(list)
    slider_value_changed = pyqtSignal(int)  # Emits slider value

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Moving atoms")
        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        self.initUI()

    def initUI(self):
        self.main_layout = QHBoxLayout()

        self.movement_layout = QVBoxLayout()
        self.rotation_layout = QVBoxLayout()

        self.init_movement_layout()
        self.init_rotation_layout()

    def init_movement_layout(self):

        # Layout for movement buttons
        self.movement_buttons_layout = QVBoxLayout()
        movement_group = QGroupBox("movement")

        icon_path = os.path.join(self.exec_dir, 'icons')

        # First row (Up)
        up_button = QPushButton()
        up_button.setIcon(QIcon(os.path.join(icon_path, "up-arrow.png")))
        up_button.setToolTip('Move atoms up')
        up_button.clicked.connect(lambda: self.atom_moved.emit("up"))

        # Second row (Left, Inwards, Right)
        middle_row = QHBoxLayout()
        left_button = QPushButton()
        left_button.setIcon(QIcon(os.path.join(icon_path, "left-arrow.png")))
        left_button.setToolTip('Move atoms left')
        left_button.clicked.connect(lambda: self.atom_moved.emit("left"))

        inwards_button = QPushButton()
        inwards_button.setIcon(QIcon(os.path.join(icon_path, "in-plane.png")))
        inwards_button.setToolTip('Move atoms inwards')
        inwards_button.clicked.connect(lambda: self.atom_moved.emit("in"))

        right_button = QPushButton()
        right_button.setIcon(QIcon(os.path.join(icon_path, "right_arrow.png")))
        right_button.setToolTip('Move atoms right')
        right_button.clicked.connect(lambda: self.atom_moved.emit("right"))

        middle_row.addWidget(left_button)
        middle_row.addWidget(inwards_button)
        middle_row.addWidget(right_button)

        # Third row (Down)
        down_button = QPushButton()
        down_button.setIcon(QIcon(os.path.join(icon_path, "down-arrow.png")))
        down_button.setToolTip('Move atoms down')
        down_button.clicked.connect(lambda: self.atom_moved.emit("down"))

        # Fourth row (Outwards)
        outwards_button = QPushButton()
        outwards_button.setIcon(QIcon(os.path.join(icon_path, "out-of-plane.png")))
        outwards_button.setToolTip('Move atoms outwards')
        outwards_button.clicked.connect(lambda: self.atom_moved.emit("out"))

        # Assemble layout
        self.movement_buttons_layout.addWidget(up_button, alignment=Qt.AlignCenter)
        self.movement_buttons_layout.addLayout(middle_row)
        self.movement_buttons_layout.addWidget(down_button, alignment=Qt.AlignCenter)
        self.movement_buttons_layout.addWidget(outwards_button, alignment=Qt.AlignCenter)

        movement_group.setLayout(self.movement_buttons_layout)
        self.movement_layout.addWidget(movement_group)

        # Slider
        self.slider_label = QLabel("Movement Speed: 50")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(50)
        self.slider.setToolTip("Adjust movement sensitivity")

        # Connect slider to update label and emit signal
        self.slider.valueChanged.connect(self.update_slider_value)

        self.movement_buttons_layout.addWidget(self.slider_label)
        self.movement_buttons_layout.addWidget(self.slider)

        self.main_layout.addLayout(self.movement_layout)
        self.setLayout(self.main_layout)

        # Connect signals
        self.atom_moved.connect(self.handle_button_click)

    def init_rotation_layout(self):
        rotation_group = QGroupBox("rotation")
        self.rotation_layout = QHBoxLayout()
        self.rotation_widgets_layout = QVBoxLayout()

        fi_layout = QHBoxLayout()
        fi_label = QLabel("Fi angle: ")
        self.fi_line_edit = QLineEdit("0")
        fi_layout.addWidget(fi_label)
        fi_layout.addWidget(self.fi_line_edit)

        theta_layout = QHBoxLayout()
        theta_label = QLabel("Theta angle: ")
        self.theta_line_edit = QLineEdit('0')
        theta_layout.addWidget(theta_label)
        theta_layout.addWidget(self.theta_line_edit)

        psi_layout = QHBoxLayout()
        psi_label = QLabel("Psi angle: ")
        self.psi_line_edit = QLineEdit('0')
        psi_layout.addWidget(psi_label)
        psi_layout.addWidget(self.psi_line_edit)

        center_layout = QHBoxLayout()
        center_label = QLabel("Center (x,y,x): ")
        x, y, z = self.get_atoms_center()
        self.center_line_edit = QLineEdit(f"({x:.2f}, {y:.2f}, {z:.2f})")
        center_layout.addWidget(center_label)
        center_layout.addWidget(self.center_line_edit)

        self.rotate_button = QPushButton("rotate!")
        self.rotate_button.setToolTip('Rotate atoms at euler angles phi, theta, psi around the center')
        self.rotate_button.clicked.connect(self.rotate_atoms)

        self.rotation_widgets_layout.addLayout(fi_layout)
        self.rotation_widgets_layout.addLayout(theta_layout)
        self.rotation_widgets_layout.addLayout(psi_layout)
        self.rotation_widgets_layout.addLayout(center_layout)
        self.rotation_widgets_layout.addWidget(self.rotate_button)

        rotation_group.setLayout(self.rotation_widgets_layout)
        self.rotation_layout.addWidget(rotation_group)

        self.main_layout.addLayout(self.rotation_layout)

    def get_atoms_center(self):
        centers = []
        if self.parent.structure_control_widget.selected_actors:

            for actor in self.parent.structure_control_widget.selected_actors:
                center = actor.GetCenter()
                centers.append(center)
            centers = np.array(centers)
            mean_x, mean_y, mean_z = np.mean(centers, axis=0)

        else:
            centers = np.array(self.parent.parent.data.coordinates)
            mean_x, mean_y, mean_z = np.mean(centers, axis=0)
        return mean_x, mean_y, mean_z

    def handle_button_click(self, direction):
        print(f"Button clicked: {direction}")

    def update_slider_value(self, value):
        self.slider_label.setText(f"Movement Speed: {value}")
        self.slider_value_changed.emit(value)  # Emit the slider value for other classes

    def rotate_atoms(self):
        phi = self.fi_line_edit.text()
        theta = self.theta_line_edit.text()
        psi = self.psi_line_edit.text()
        center = self.center_line_edit.text()
        self.atom_rotated.emit([phi, theta, psi, center])

class Bonds:
    def __init__(self, index1, index2, structure_variable_control_widget):
        # indexes of atoms to create bond between
        self.index1 = index1
        self.index2 = index2
        self.structure_variable_control_widget = structure_variable_control_widget
        self.structure_control_widget = self.structure_variable_control_widget.structure_control_widget
        self.structure_plot_widget = self.structure_control_widget.structure_plot_widget

    def add_bond_length(self):
        coords = self.structure_plot_widget.data.outcar_data.find_coordinates()
        current_coords = coords[self.structure_control_widget.geometry_slider.value()]
        pt1 = current_coords[self.index1]
        pt2 = current_coords[self.index2]
        self._add_bond_line(pt1, pt2)
        self._add_bond_label(pt1, pt2)


    def _add_bond_line(self, pt1, pt2):
        pt1 = np.array(pt1)
        pt2 = np.array(pt2)
        direction = pt2 - pt1
        length = np.linalg.norm(direction)
        direction /= length  # normalize

        segment_length = 0.2
        num_segments = int(length / segment_length)

        # VTK data structures
        points = vtkPoints()
        lines = vtkCellArray()

        point_id = 0

        for i in range(num_segments):
            start = pt1 + i * segment_length * direction
            end = pt1 + (i + 1) * segment_length * direction

            # Draw only for odd segments (i = 1, 3, 5, ...)
            if i % 2 == 1:
                points.InsertNextPoint(start)
                points.InsertNextPoint(end)

                line = vtkLine()
                line.GetPointIds().SetId(0, point_id)
                line.GetPointIds().SetId(1, point_id + 1)
                lines.InsertNextCell(line)
                point_id += 2

        # Create the polyline
        poly_data = vtkPolyData()
        poly_data.SetPoints(points)
        poly_data.SetLines(lines)

        # Mapper and actor
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(poly_data)

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0, 0.8, 0)
        actor.GetProperty().SetLineWidth(3)

        self.structure_plot_widget.plotter.add_actor(actor)
        self.bond_actor = actor

    def _add_bond_label(self, pt1, pt2):
        """
        Adds a bond label showing the distance between two points in green color.
        """
        # Calculate midpoint
        midpoint = [(pt1[i] + pt2[i]) / 2 for i in range(3)]

        # Calculate distance
        distance = np.linalg.norm(np.array(pt1) - np.array(pt2))
        distance_text = f"{distance:.3f}"

        # Create label actor
        bond_label_actor = self.structure_plot_widget.plotter.add_point_labels(
            [midpoint], [distance_text], font_size=24,
            show_points=False, always_visible=True, text_color=(0,220,0), shape=None
        )
        self.bond_label_actor = bond_label_actor

    def clear_bond_labels(self):
        for actor in [self.bond_label_actor, self.bond_actor]:
            self.structure_plot_widget.plotter.renderer.RemoveActor(actor)
