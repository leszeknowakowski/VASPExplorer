import time

import vtk

tic = time.perf_counter()
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, \
    QFileDialog, QPushButton, QHBoxLayout, QSlider, QMainWindow, QProgressBar, QDialog, QMessageBox
from PyQt5 import QtCore
import numpy as np
import chopPARCHG_test_chgcar_comp as chp
import sys
import os
toc = time.perf_counter()
print(f'importing in chgcar, time: {toc - tic:0.4f} seconds')


class DialogWIndow(QDialog):
    """
    This class provides a window which is shown when heavy I/O operations
    are done, e.g. reading CHGCAR file
    """
    def __init__(self):
        """ Initialize """
        super().__init__()
        self.setModal(True)
        layout = QVBoxLayout()
        #self.setMinimumSize(300,300)
        self.label1 = QLabel('processing CHGCAR file...')
        layout.addWidget(self.label1)

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0,100)
        self.progressBar.setValue(0)
        self.progressBar.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(self.progressBar)
        self.setLayout(layout)

    def update_progress(self, value):
        self.progressBar.setValue(value)

class ChgcarVis(QWidget):
    """ this class provides functionality for reading, displaying and
    controlling the electron charge density plots.

    Parameters
    ----------------------
    plotter : class
        structure control widget plotter from structure plot

    """
    load_data = QtCore.pyqtSignal(str)
    def __init__(self,structure_variable_control):
        """ Initialize """
        super().__init__()
        self.structure_variable_control = structure_variable_control
        self.chg_plotter = self.structure_variable_control.structure_control_widget.plotter
        self.contour_type = 'total'
        self.charge_data = None
        self.chg_button_counter = 0
        self.current_contour_actor = None
        self.box_widget = None
        self.supercell_made = None
        self.charge_data = None
        self.structure_variable_control.atom_deleted.connect(self.delete_atom)
        self.structure_variable_control.all_atoms_deleted.connect(self.create_header_when_deleted)

        self.initUI()

    def initUI(self):
        """ initialize GUI for this tab """
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        # create buttons
        self.chg_file_button = QPushButton('open CHGCAR')
        self.chg_file_button.clicked.connect(self.select_chg_file)
        self.layout.addWidget(self.chg_file_button)

        self.spin_buttons = {
            "total": QPushButton('Total'),
            "spin": QPushButton('Spin'),
            "alfa": QPushButton('Alfa'),
            "beta": QPushButton('Beta'),
            "clear": QPushButton('Clear')
        }
        spin_layout = QHBoxLayout()
        for spin_type, btn in self.spin_buttons.items():
            spin_layout.addWidget(btn)
            btn.clicked.connect(lambda _, t=spin_type: self.set_spin_type(t))
            if spin_type != "clear":
                btn.clicked.connect(self.add_contours)
            else:
                btn.clicked.connect(self.clear_contours)
        self.layout.addLayout(spin_layout)

         # layout for isosurface value slider
        self.eps_layout = QHBoxLayout()
        self.chg_eps_text = QLabel("isosurface value (eps) :")
        self.chg_eps_value_label = QLabel()

        self.chg_eps_slider = QSlider()
        self.chg_eps_slider.setOrientation(QtCore.Qt.Horizontal)
        self.chg_eps_slider.setMinimum(0)
        self.chg_eps_slider.setMaximum(100)
        self.chg_eps_slider.setValue(10)
        self.chg_eps_slider.setTickInterval(1)
        self.chg_eps_slider.setSingleStep(1)
        self.eps = self.chg_eps_slider.value()/100

        self.chg_eps_value_label.setText(str(self.eps))

        self.chg_eps_slider.sliderReleased.connect(self.update_eps)
        self.chg_eps_slider.sliderReleased.connect(self.add_contours)
        self.chg_eps_slider.valueChanged.connect(self.change_eps_label)

        self.eps_layout.addWidget(self.chg_eps_text)
        self.eps_layout.addWidget(self.chg_eps_value_label)
        self.eps_layout.addWidget(self.chg_eps_slider)

        self.manipulate_charge_layout = QHBoxLayout()
        self.add_box_button = QPushButton('Add box')
        self.add_box_button.clicked.connect(self.add_flip_box_widget)

        self.remove_box_button = QPushButton('Remove box')
        self.remove_box_button.clicked.connect(self.remove_flip_box_widget)

        self.flip_spin_button = QPushButton('Flip spin density')
        self.flip_spin_button.clicked.connect(self.flip_spin_density)

        self.remove_density_button = QPushButton('Remove density')
        self.remove_density_button.clicked.connect(self.remove_density)

        self.make_supercell_button = QPushButton('Make supercell')
        self.make_supercell_button.clicked.connect(self.make_supercell)

        save_chgcar_button = QPushButton('Save CHGCAR')
        save_chgcar_button.clicked.connect(self.write_chgcar)

        self.manipulate_charge_layout.addWidget(self.add_box_button)
        self.manipulate_charge_layout.addWidget(self.remove_box_button)
        self.manipulate_charge_layout.addWidget(self.flip_spin_button)
        self.manipulate_charge_layout.addWidget(self.remove_density_button)
        self.manipulate_charge_layout.addWidget(self.make_supercell_button)
        self.manipulate_charge_layout.addWidget(save_chgcar_button)

        self.layout.addLayout(self.eps_layout)
        self.layout.addLayout(self.manipulate_charge_layout)

        self.setLayout(self.layout)


    def update_data(self, data):
        if self.current_contour_actor is not None:
            self.clear_contours()

    def set_spin_type(self, type="total"):
        """ set the type of spin to visualise on charge
        density plot

        Parameters:
        --------------------------
        type: "total" | "spin" | "alfa" | "beta"
            "total" plots total charge density
            "spin" plots spin charge density
            "alfa" plots major spin charge density
            "beta" plots minor spin charge density
        """

        self.contour_type = type

    def create_chgcar_data(self):
        """ creates data for plotting  """

        chopping_factor = 1
        if os.path.exists(self.chg_file_path):
            try:
                self.charge_data = chp.PoscarParser(self.chg_file_path, chopping_factor)
                self.charge_data.progress.connect(self.progress_window.update_progress)
                self.charge_data.start()
                self.charge_data.finished.connect(self.add_contours)
                self.charge_data.finished.connect(self.close_progress_window)

            except Exception as e:
                print("ooopsie! cannot read data")
                print(f"An error occurred: {e}")

    def update_eps(self):
        """ update isosurface value with slider """
        self.eps = self.chg_eps_slider.value() / 100

    def change_eps_label(self, value):
        """ updates the isosurface value label

        Parameters:
        -----------------
        value : int
            Passed by slider

        """

        self.chg_eps_value_label.setText(str(value/100))

    def add_contours(self):
        """ creates the isosurface contours from charge density data """

        if self.charge_data == None:
            # if no charge data was loaded, print message
            print("no data was found")
            return

        if self.current_contour_actor is not None:
            self.chg_plotter.remove_actor(self.current_contour_actor)
        total, spin = self.charge_data.all_numbers
        alfa, beta = [self.charge_data.alfa, self.charge_data.beta]

        # volumetric_data is the actual data with charge
        volumetric_data = {
            "total": total,
            "spin": spin,
            "alfa": alfa,
            "beta": beta
        }.get(self.contour_type, None)

        if volumetric_data is None:
            print("Invalid contour type")
            return

        volumetric_data = volumetric_data.swapaxes(0, 2)

        max_val = np.max(volumetric_data)
        min_val = np.min(volumetric_data)
        largest_value = np.max([np.abs(max_val), np.abs(min_val)])

        basis = np.array(self.charge_data._unit_cell_vectors)*self.charge_data._scale_factor

        nx, ny, nz = volumetric_data.shape

        from vtk.util import numpy_support
        volumetric_data = volumetric_data.ravel(order='F')
        vtk_data = numpy_support.numpy_to_vtk(num_array=volumetric_data, deep=True, array_type=vtk.VTK_DOUBLE)
        vtk_data.SetName("values")

        # Create vtkImageData
        image_data = vtk.vtkImageData()
        image_data.SetDimensions(nx, ny, nz)
        image_data.SetSpacing(1 / (nx - 1), 1 / (ny - 1), 1 / (nz - 1))
        image_data.SetOrigin(0.0, 0.0, 0.0)
        image_data.GetPointData().SetScalars(vtk_data)

        # Cast to vtkUnstructuredGrid (vtkTransformFilter needs PointSet)
        geometry_filter = vtk.vtkImageDataToPointSet()
        geometry_filter.SetInputData(image_data)
        geometry_filter.Update()

        # Now warp the ImageData using vtkTransformFilter
        transform = vtk.vtkTransform()
        transform.SetMatrix([
            basis[0, 0], basis[0, 1], basis[0, 2], 0,
            basis[1, 0], basis[1, 1], basis[1, 2], 0,
            basis[2, 0], basis[2, 1], basis[2, 2], 0,
            0, 0, 0, 1
        ])

        # Apply transform using a transform filter
        transform_filter = vtk.vtkTransformFilter()
        transform_filter.SetTransform(transform)
        transform_filter.SetInputConnection(geometry_filter.GetOutputPort())  # ImageData → UnstructuredGrid
        transform_filter.Update()

        # === Replace PyVista contour with vtkContourFilter ===
        contour_filter = vtk.vtkContourFilter()
        contour_filter.SetInputConnection(transform_filter.GetOutputPort())

        # Set isosurface values
        if self.contour_type == "spin":
            if largest_value> 10:
                contour_filter.SetValue(0, -self.eps * largest_value)
                contour_filter.SetValue(1, self.eps * largest_value)
            else:
                print("there is no spin polarization. Your structure is non-magnetic")
                contour_filter.SetValue(0, largest_value)
        else:
            contour_filter.SetValue(0, self.eps * largest_value)

        contour_filter.Update()

        # === Create lookup table with your colors ===
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(2)
        lut.SetRange(-self.eps * largest_value, self.eps * largest_value)
        lut.SetTableValue(0, 0.0, 1.0, 1.0, 1.0)  # Light blue
        lut.SetTableValue(1, 1.0, 1.0, 0.0, 1.0)  # Yellow
        lut.Build()

        # === Create a mapper ===
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(contour_filter.GetOutputPort())  # Use your vtkContourFilter output
        mapper.SetLookupTable(lut)
        mapper.SetScalarRange(-self.eps * largest_value, self.eps * largest_value)
        mapper.SetColorModeToMapScalars()
        mapper.ScalarVisibilityOn()

        # === Create the actor ===
        contour_actor = vtk.vtkActor()
        contour_actor.SetMapper(mapper)
        contour_actor.GetProperty().SetOpacity(1.0)  # Fully opaque
        contour_actor.GetProperty().SetInterpolationToPhong()  # Optional smooth shading

        self.current_contour_actor = contour_actor
        # add contours to a plotter
        try:
            self.chg_plotter.add_actor(contour_actor)
        except ValueError:
            print("Empty contour - check epsilon or - if You want to plot spin density - structure is non-magnetic")

    def clear_contours(self):
        """ removes the contours from plotter """

        actor = self.current_contour_actor
        self.chg_plotter.remove_actor(actor)
        print('cleared')

    def select_chg_file(self):
        """
        functon to create window with charge density file choose.
        When button is clicked first, it will load CHGCAR from chg_file_path, if it exists.
        When clicked again (or is there is no CHGCAR), it will open file dialog
        """
        if os.path.exists(self.chg_file_path) and self.chg_button_counter == 0:
            self.process_chg_file(self.chg_file_path)
        else:
            file_dialog = QFileDialog()
            file_dialog.setDirectory(self.chg_file_path)
            file_path, _ = file_dialog.getOpenFileName(self, "choose charge density file")
            self.chg_file_path = file_path
            self.process_chg_file(self.chg_file_path)
        self.chg_button_counter += 1

    def process_chg_file(self, file_path):
        """
        function to process CHGCAR file
        """

        self.progress_window = DialogWIndow()
        self.progress_window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.progress_window.show()
        self.chg_file_path = file_path
        self.create_chgcar_data()

    def close_progress_window(self):
        self.progress_window.close()

    def add_flip_box_widget(self):
        if self.box_widget is None:
            self.box_widget = self.chg_plotter.add_box_widget(self.box_widget_callback)
        else:
            QMessageBox.warning(self, "Error", "Box widget already on the screen")

    def remove_flip_box_widget(self):
        self.chg_plotter.clear_box_widgets()
        self.box_widget = None

    def box_widget_callback(self, widget):
        bounds = widget.bounds
        self.box_bounds = bounds

    def change_charge_density(self, density_type, factor, add_contours=True):
        """
        Change charge density grid in a box defined by a box bounds.
        Args:
            density_type (str): type of charge density to change: total, spin, alfa, beta
            factor (float): factor to change the density grid (eg, -1, 0, 1.2)
        Returns:
            charge density grid of a given type
        """
        if density_type not in ['total', 'spin', 'alfa', 'beta']:
            return
        data_map = {
            'total': self.charge_data.all_numbers[0],
            'spin': self.charge_data.all_numbers[1],
            'alfa': self.charge_data.alfa,
            'beta': self.charge_data.beta,
        }
        data = data_map[density_type]

        x_start, x_stop, y_start, y_stop, z_start, z_stop = [x if x >= 0 else 0 for x in self.box_bounds]
        box_min = np.array([x_start, y_start, z_start])
        box_max = np.array([x_stop, y_stop, z_stop])
        voxel_size = self.charge_data.voxel_size()
        x_min, y_min, z_min = np.floor(box_min / voxel_size).astype(int)
        x_max, y_max, z_max = np.ceil(box_max / voxel_size).astype(int)
        grid_max = self.charge_data._grid
        x_max, y_max, z_max = [min(v, l) for v, l in zip(grid_max, [x_max, y_max, z_max])]

        data[z_min: z_max, y_min: y_max, x_min: x_max] *= factor
        if add_contours:
            self.add_contours()

    def flip_spin_density(self):
        """ flip spin density in a box defined by a box bounds."""
        self.change_charge_density('spin', -1)

    def remove_density(self):
        """ remove total and spin density from a box defined by a box bounds."""
        self.change_charge_density('total', 0, add_contours=False)
        self.change_charge_density('spin', 0)

    def matrix_to_ase_matrix(self, matrix):
        x = matrix[0]
        y = matrix[1]
        z = matrix[2]
        ase_matrix = ((x, 0, 0), (0, y, 0), (0, 0, z))
        return ase_matrix

    def make_charge_supercell(self, matrix):
        """ make a supercell from CHGCAR data
        Args:
            matrix (array): an array of (X, Y, Z) factors to duplicate in selected directions
        """
        from ase.build import make_supercell
        x = matrix[0]
        y = matrix[1]
        z = matrix[2]
        total_supercell = np.tile(self.charge_data.all_numbers[0], (z, y, x))
        spin_supercell = np.tile(self.charge_data.all_numbers[1], (z, y, x))
        self.charge_data.all_numbers = [total_supercell, spin_supercell]
        self.charge_data.alfa, self.charge_data.beta = self.charge_data.calc_alfa_beta(1)

        multiplication = x * y * z
        aug_dict, aug_leftovers = self.charge_data.read_augmentation(self.charge_data.aug)
        aug_diff_dict, aug_diff_leftovers = self.charge_data.read_augmentation(self.charge_data.aug_diff)

        new_aug_dict, new_aug_leftovers = self.charge_data.tile_dict_and_list(aug_dict, aug_leftovers, multiplication)
        new_aug_diff_dict, new_aug_diff_leftovers = self.charge_data.tile_dict_and_list(aug_diff_dict, aug_diff_leftovers, multiplication)

        new_aug = self.charge_data.rebuild_string(new_aug_dict, new_aug_leftovers)
        new_aug_diff = self.charge_data.rebuild_string(new_aug_diff_dict, new_aug_diff_leftovers)
        self.charge_data.aug = new_aug
        self.charge_data.aug_diff = new_aug_diff
        print("done")

    def make_atoms_supercell(self, matrix):
        """ make a supercell from atoms. If CONTCAR or POSCAR exists, constraints will be added
        Args:
            matrix (array): an array of (X, Y, Z) factors to duplicate in selected directions
        """
        from ase.io import read, write
        from ase.build import make_supercell
        import io

        chgcar = read(self.chg_file_path, format='vasp')
        atoms = chgcar
        dir = os.path.dirname(self.chg_file_path)
        contcar = os.path.join(dir, 'CONTCAR')
        poscar = os.path.join(dir, 'POSCAR')

        filename = None
        const_atoms = None
        for f in [contcar, poscar]:
            if os.path.isfile(f):
                filename = f
                break

        if filename:
            const_atoms = read(filename, format='vasp')
            constraints = const_atoms.constraints
            atoms.constraints = constraints
        else:
            print("Neither CONTCAR nor POSCAR found. No constraints will be added")


        ase_matrix = self.matrix_to_ase_matrix(matrix)
        supercell_atoms = make_supercell(atoms, ase_matrix, order="atom-major")

        self.buffer = io.StringIO()
        write(self.buffer, supercell_atoms, format='vasp')

        return supercell_atoms

    def read_supercell_to_vaspy(self, matrix):
        from ase.io import write, read
        supercell = self.make_atoms_supercell(matrix)
        if not os.path.exists("tmp"):
            os.mkdir("tmp")
        os.chdir("tmp")
        write("POSCAR", supercell)
        self.load_data.emit(os.getcwd())
        folder = os.getcwd()
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

        os.chdir("../")
        try:
            os.rmdir("tmp")
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))
        self.charge_data._unit_cell_vectors = supercell.cell[:]
        self.charge_data._scale_factor = 1
        self.charge_data._grid = np.flip(np.shape(self.charge_data.all_numbers[0]))
        self.add_contours()

    def make_supercell(self):
        matrix = (2,2,1) # #######################TODO: CHANGE LATER!!!###############################################################
        try:
            self.make_atoms_supercell(matrix)
            self.make_charge_supercell(matrix)
            self.read_supercell_to_vaspy(matrix)
            self.supercell_made = True
        except Exception as e:
            pass

    def delete_atom(self, index):
        print(f'index from chgcar tab {index}')

        idx = index + 1
        if self.charge_data != None:

            aug_dict, aug_leftovers = self.charge_data.read_augmentation(self.charge_data.aug)
            aug_diff_dict, aug_diff_leftovers = self.charge_data.read_augmentation(self.charge_data.aug_diff)

            del aug_dict[idx]
            del aug_leftovers[index]
            del aug_diff_dict[idx]

            def new_dict(old_dict):
                return {i + 1: v for i, (_, v) in enumerate(sorted(old_dict.items()))}

            new_aug_dict = new_dict(aug_dict)
            new_aug_diff_dict = new_dict(aug_diff_dict)
            new_aug = self.charge_data.rebuild_string(new_aug_dict, aug_leftovers)
            new_aug_diff = self.charge_data.rebuild_string(new_aug_diff_dict, aug_diff_leftovers)

            self.charge_data.aug = new_aug
            self.charge_data.aug_diff = new_aug_diff

    def create_header_when_deleted(self, str):
        if self.charge_data != None:
            import io
            stream = io.StringIO()
            self.structure_variable_control.save_poscar(stream)
            self.charge_data.create_new_header(stream)

    def write_chgcar(self):
        file_dialog = QFileDialog()
        file_dialog.setDirectory(self.chg_file_path)
        file_path, _ = file_dialog.getSaveFileName()
        if self.supercell_made is not None:
            self.charge_data.create_new_header(self.buffer)

        self.charge_data.save_all_file(file_path, 1, format='vasp')

    def closeEvent(self, QCloseEvent):
        """former closeEvent in case of many interactors"""
        super().closeEvent(QCloseEvent)
        self.chg_plotter.Finalize()

if __name__ == "__main__":
    """ just for building """
    from pyvistaqt import QtInteractor
    app = QApplication(sys.argv)
    plotter = QtInteractor()
    win = QMainWindow()
    chg_widget = ChgcarVis(plotter)

    central_widget = QWidget()
    win.setCentralWidget(central_widget)
    main_layout = QVBoxLayout(central_widget)

    main_layout.addWidget(chg_widget)
    main_layout.addWidget(plotter)


    chg_widget.chg_file_path = r"D:\syncme\modelowanie DFT\CeO2\1.CeO2(100)\CeO2_100_half_Ce\2.large slab\1.1x1x1\1.HSE"
    #chg_widget.chg_file_path = r"D:\syncme\test_for_doswizard\9.CHGCAR"
    chg_widget.set_spin_type("spin")
    chg_widget.select_chg_file()
    chg_widget.setWindowTitle("Main Window")
    #chg_widget.create_chgcar_data()
    win.resize(1000, 850)
    win.show()
    sys.exit(app.exec_())
