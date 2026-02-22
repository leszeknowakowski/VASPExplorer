import time
import vtk

tic = time.perf_counter()
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, \
    QFileDialog, QPushButton, QHBoxLayout, QSlider, QMainWindow, QProgressBar, QDialog, QMessageBox, \
    QGroupBox, QSpacerItem, QSizePolicy, QGridLayout, QCheckBox, QSpinBox
from PyQt5 import QtCore
import numpy as np
import subprocess, tempfile
from process_CHGCAR import CHGCARParser
try:
    from memory_profiler import profile
except ImportError:
    pass
import sys
import os
from bader import BaderParser
toc = time.perf_counter()
print(f'importing in chgcar, time: {toc - tic:0.4f} seconds')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'third_party'))

class DialogWIndow(QDialog):
    """
    This class provides a window which is shown when heavy I/O operations
    are done, e.g. reading CHGCAR file
    """
    def __init__(self, file_path):
        """ Initialize """
        super().__init__()
        self.setModal(True)
        layout = QVBoxLayout()
        #self.setMinimumSize(300,300)
        self.header = QLabel("processing CHGCAR file...")
        self.file_size = os.path.getsize(file_path) / 1024 / 1024
        self.size_label = QLabel(f"The size of a file is {self.file_size: .2f}  MB")
        self.timing_label = QLabel(f"Reading will take approx. {self.estimate_timing(self.file_size):.1f} seconds")
        self.label1 = QLabel('processing CHGCAR file...')
        layout.addWidget(self.header)
        layout.addWidget(self.size_label)
        layout.addWidget(self.timing_label)
        layout.addWidget(self.label1)

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0,100)
        self.progressBar.setValue(0)
        self.progressBar.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(self.progressBar)
        self.setLayout(layout)

    def estimate_timing(self, size):
        time = 1.1451 + 0.0222803*size
        return time
    def update_progress(self, value):
        self.progressBar.setValue(value)

    def change_label(self, text):
        self.label1.setText(text)

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
        self.chg_button_counter = 0
        self.current_contour_actor = None
        self.box_widget = None
        self.supercell_made = None
        self.charge_data = None
        self.chg_threads = []
        self.chg_file_paths = []
        self.chgcar_data = {}
        self.structure_variable_control.atom_deleted.connect(self.delete_atom)
        self.structure_variable_control.all_atoms_deleted.connect(self.create_header_when_deleted)

        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.init_chgcar_UI()
        spacer = QSpacerItem(20,40,QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.layout.addSpacerItem(spacer)
        self.init_bader_UI()
        self.init_DDEC_UI()
        self.init_volumetric_edit_UI()

    def init_chgcar_UI(self):
        """ initialize GUI for this tab """

        self.chgcar_frame = QGroupBox(self)
        self.chgcar_frame.setTitle("CHGCAR manipulation")
        self.chgcar_frame.setMaximumHeight(200)

        self.chgcar_frame_layout = QVBoxLayout(self.chgcar_frame)
        self.chgcar_frame_layout.setAlignment(QtCore.Qt.AlignTop)

        # create buttons
        self.chg_file_button = QPushButton('open CHGCAR')
        self.chg_file_button.clicked.connect(self.select_chg_file)
        self.chgcar_frame_layout.addWidget(self.chg_file_button)

        self.spin_buttons = {
            "total": QPushButton('Total'),
            "spin": QPushButton('Spin'),
            "alfa": QPushButton('Alfa'),
            "beta": QPushButton('Beta'),
            "clear": QPushButton('Clear')
        }
        spin_layout = QHBoxLayout()
        for spin_type, btn in self.spin_buttons.items():
            btn.setMinimumWidth(5)
            spin_layout.addWidget(btn)
            btn.clicked.connect(lambda _, t=spin_type: self.set_spin_type(t))
            if spin_type != "clear":
                btn.clicked.connect(self.add_contours)
            else:
                btn.clicked.connect(self.clear_contours)
        self.chgcar_frame_layout.addLayout(spin_layout)

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

        self.manipulate_charge_layout = QGridLayout()
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

        chg_btns = [self.add_box_button, self.remove_box_button, self.flip_spin_button,self.remove_density_button, self.make_supercell_button]
        for btn in chg_btns:
            btn.setMinimumWidth(5)

        self.manipulate_charge_layout.addWidget(self.add_box_button,0,0)
        self.manipulate_charge_layout.addWidget(self.remove_box_button,0,1)
        self.manipulate_charge_layout.addWidget(self.flip_spin_button,1,0)
        self.manipulate_charge_layout.addWidget(self.remove_density_button,1,1)
        self.manipulate_charge_layout.addWidget(self.make_supercell_button,2,0)
        self.manipulate_charge_layout.addWidget(save_chgcar_button,2,1)

        self.chgcar_frame_layout.addLayout(self.eps_layout)
        self.chgcar_frame_layout.addLayout(self.manipulate_charge_layout)
        self.layout.addWidget(self.chgcar_frame)

    def init_bader_UI(self):
        self.bader_file = None
        self.bader_data_loaded = False
        self.bader_frame = QGroupBox(self)
        self.bader_frame.setTitle("Bader charge manipulation")
        self.bader_frame.setMaximumHeight(150)
        self.bader_frame_layout = QVBoxLayout(self.bader_frame)
        self.bader_frame_layout.setAlignment(QtCore.Qt.AlignTop)

        open_file_button = QPushButton("Open ACF.dat-corrected file")
        open_file_button.clicked.connect(self.open_bader_file)
        self.bader_frame_layout.addWidget(open_file_button)

        print_button = QPushButton("Print sum of selection")
        print_button.clicked.connect(self.print_bader_charge)
        self.bader_frame_layout.addWidget(print_button)

        print_separate_button = QPushButton("Print separate selection")
        print_separate_button.clicked.connect(self.print_separate_bader_charges)
        self.bader_frame_layout.addWidget(print_separate_button)

        self.charges_button_cb = QCheckBox()
        self.charges_button_cb.setChecked(False)
        self.charges_button_cb.setText("show bader charges")

        self.charges_button_cb.stateChanged.connect(self.show_bader_charges)
        self.bader_frame_layout.addWidget(self.charges_button_cb)
        self.structure_variable_control.structure_control_widget.plane_height_range_slider.startValueChanged.connect(
            self.show_bader_charges)
        self.structure_variable_control.structure_control_widget.plane_height_range_slider.endValueChanged.connect(
            self.show_bader_charges)

        self.layout.addWidget(self.bader_frame)

    def init_DDEC_UI(self):
        self.DDEC_file = None

        self.ddec_frame = QGroupBox(self)
        self.ddec_frame.setTitle("Bond order manipulation")
        self.ddec_frame.setMaximumHeight(150)
        self.ddec_frame_layout = QVBoxLayout(self.ddec_frame)
        self.ddec_frame_layout.setAlignment(QtCore.Qt.AlignTop)

        self.DDEC_choose_window_btn = QPushButton("Choose DDEC fragments")
        self.DDEC_choose_window_btn.clicked.connect(self.perform_BO)
        self.ddec_frame_layout.addWidget(self.DDEC_choose_window_btn)

        self.layout.addWidget(self.ddec_frame)

    def init_volumetric_edit_UI(self):
        self.volumetric_edit_data = []
        self.vol_edit_frame = QGroupBox(self)
        self.vol_edit_frame.setTitle("Volumetric data editing")
        self.vol_edit_frame.setMaximumHeight(150)
        self.vol_edit_frame_layout = QVBoxLayout(self.vol_edit_frame)

        self.vol_edit_window_btn = QPushButton("Choose Volumetric editing data")
        self.vol_edit_window_btn.clicked.connect(self.edit_volumetric_data)
        self.vol_edit_frame_layout.addWidget(self.vol_edit_window_btn)

        self.layout.addWidget(self.vol_edit_frame)

    def open_bader_file(self):
        """
        functon to create window with bader charge file choose.
        """
        if self.bader_file is None:
            file_path = os.path.join(self.chg_file_path, "ACF.dat-corrected")
            if os.path.exists(file_path):
                self.bader_file = file_path
            else:
                file_dialog = QFileDialog()
                file_dialog.setDirectory(self.chg_file_path)
                file_path, _ = file_dialog.getOpenFileName(self, "choose bader charge file")

            if file_path != "":
                self.bader_file = file_path
                self.process_bader_file(self.bader_file)

    def process_bader_file(self, file_path):
        """
        Process Bader charge file
        """
        bader = BaderParser()
        bader.parse(file_path)

        # sanity check
        symb = [item[-1] for item in bader.atoms]
        num = [item[0] for item in bader.atoms]
        symb_and_num = [a+b for a, b, in zip(symb, num)]

        symbols = self.structure_variable_control.structure_control_widget.structure_plot_widget.data.stripped_symbols
        symbols_and_numbers = []
        for i, symbol in enumerate(symbols):
            symbols_and_numbers.append(symbol + str(i+1))

        if symbols_and_numbers != symb_and_num:
            print('oopsie, bader elements doesnt match this structure. Choose other bader file')

        coords = self.structure_variable_control.structure_control_widget.structure_plot_widget.data.outcar_data.find_coordinates()[-1]
        x = [item[1] for item in bader.atoms]
        y = [item[2] for item in bader.atoms]
        z = [item[3] for item in bader.atoms]
        coords_bader = [[float(x_), float(y_), float(z_)] for x_, y_, z_, in zip(x, y, z)]

        matches = []
        threshold = 0.1
        lst = ['X', 'Y', 'Z']
        for i, (sub1, sub2) in enumerate(zip(coords, coords_bader)):
            for j, (a, b) in enumerate(zip(sub1, sub2)):
                diff = abs(a-b)
                match = diff <= threshold
                matches.append(match)
                if not match:
                    atom = symb_and_num[i]
                    print(f"Element {atom} at coordinate {lst[j]}: "
                    f"{a:.2f} vs {b:.2f} does not match!")

        if not all(matches):
            reply = QMessageBox.question(self, 'Proceed',
                                         "It seems like some of Your atoms doesn't match this structure when comparing bader vs CONTCAR coordinates. \n \
                                         Check atoms positions. Are you sure you want to proceed?",
                                         QMessageBox.Yes | QMessageBox.No,
                                         QMessageBox.No)

        if all(matches) or reply == QMessageBox.Yes:
            self.bader_data = bader.atoms
            self.bader_data_loaded = True

    def print_bader_charge(self):
        if self.bader_data_loaded:
            indexes = self.structure_variable_control.get_selected_rows()
            charges = np.array([float(self.bader_data[index][4]) for index in indexes])
            sum_charges = np.sum(charges)
            print(sum_charges)

    def print_separate_bader_charges(self):
        if self.bader_data_loaded:
            indexes = self.structure_variable_control.get_selected_rows()
            charges = [float(self.bader_data[index][4]) for index in indexes]
            atomic_symbols = [self.bader_data[index][5] for index in indexes]
            symb_and_num = [x+y for x, y in zip(atomic_symbols, [str(num) for num in indexes])]
            chg_dict = dict(zip(symb_and_num, charges))
            for key, value in chg_dict.items():
                print(key, ": ", value)
            return chg_dict

    def show_bader_charges(self, flag):
        if self.bader_data_loaded:
            if hasattr(self, "bader_charges_actor"):
                self.chg_plotter.renderer.RemoveActor(self.bader_charges_actor)
            indices, coordinates = self.structure_variable_control.structure_control_widget.find_indices_between_planes()
            coords = []
            baders = []

            bader_charges = [self.bader_data[index][4] for index in range(len(self.bader_data))]
            for i in range(len(indices)):
                coords.append(list(coordinates[indices[i]]))
                baders.append(bader_charges[indices[i]])
            self.bader_charges_actor = self.chg_plotter.add_point_labels(coords, baders, font_size=30,
                                                                         show_points=False, always_visible=True,
                                                                         shape=None)
            self.bader_charges_actor.SetVisibility(flag)
                  
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

    def perform_BO(self):
        self.ddec_window = DDECAtomSelector(self)
        self.ddec_window.fragments_selected.connect(self.run_bo_script)
        self.ddec_window.show()

    def run_bo_script(self, frag1, frag2):

        if not frag1:
            print("ERROR: Fragment 1 cannot be empty.")
            return

        base_dir = "./"
        base_name = "DDEC6_even_tempered_bond_orders"
        script_dir = os.path.join(os.path.dirname(__file__), "scripts")

        xyz_file = os.path.join(base_dir, f"{base_name}.xyz")
        csv_file = os.path.join(base_dir, f"{base_name}.csv")
        corrected_path = os.path.join(base_dir, f"{base_name}-corrected.xyz")
        fragments_path = os.path.join(base_dir, f"{base_name}-fragments.xyz")

        if not os.path.exists(xyz_file):
            print("Cannot read xyz file")
            return

        # Step 1 ? cleanup
        subprocess.run([
            "awk",
            "-f", os.path.join(script_dir, "chargemol_cleanup_bo.awk"),
            "-v", "threshold=0",
            "-v", "format=csv",
            "-v", "triangle=yes"
        ], input=open(xyz_file).read(), text=True,
            stdout=open(csv_file, "w"))

        ranges_script = os.path.join(script_dir, "vasp_bader_get_ranges.awk")

        atoms_value = subprocess.getoutput(f"awk -f {ranges_script}")

        # Step 2 ? fragments
        awk_command = [
            "awk",
            "-v", f'atoms="{atoms_value}"',
            "-v", f"frag1={frag1}",
        ]

        if frag2:
            awk_command += ["-v", f"frag2={frag2}"]

        awk_command += [
            "-f", os.path.join(script_dir, "chargemol_frags.awk"),
            csv_file
        ]

        with open(corrected_path, "w") as stdout_file, \
                open(fragments_path, "w") as stderr_file:

            result = subprocess.run(
                awk_command,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True
            )

        with open(fragments_path, "r") as fragment_file:
            lines = fragment_file.readlines()
            print(lines[-1])

    def edit_volumetric_data(self):
        self.volume_editing_window = VolumetricDataEditingWindow(self)
        self.volume_editing_window.show()

    #@profile
    def create_chgcar_data(self, file_path, init):
        """ creates data for plotting.  """

        chopping_factor = 1
        if not os.path.exists(file_path):
            return
        # freeze plotter rendering (it slows down reading CHGCAR, even if
        # it is in another thread
        self.chg_plotter.setup_render_thread(0)

        self.chg_file_paths.append(file_path)
        # read CHGCAR using ASE VaspChargeDensity class in CHGCARParser
        thread = CHGCARParser(file_path, 1)
        thread.file_path = file_path

        self.chg_threads.append(thread)
        thread.progress.connect(self.progress_window.update_progress)
        thread.change_label.connect(self.progress_window.change_label)

        # it runs in another thread, so we have to use start() to run
        # the worker thread
        thread.start()
        thread.finished.connect(lambda: self._on_chgcar_finished(thread, init))

    def _on_chgcar_finished(self, thread, init):
        self.chgcar_data[thread.file_path] = thread

        if init:
            self.add_contours()
        self.close_progress_window()
        self._after_reading()

        thread.deleteLater()
        self.chg_threads.remove(thread)

        if hasattr(self, "volume_editing_window"):
            self.volume_editing_window.notify_chgcar_loaded(thread.file_path)

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

    def get_chopping_factor(self):
        voxel_size = self.chgcar_data[self.chg_file_path].voxel_size()
        optimal_size = 0.25
        grid = self.chgcar_data[self.chg_file_path].chgcar._grid
        common_divisors = self.chgcar_data[self.chg_file_path].common_divisors(*grid)
        if voxel_size[0] < optimal_size:
            chop = optimal_size / voxel_size[0]
            if int(chop) not in common_divisors:
                chop = int(chop) - 1
            else:
                chop = int(chop)
            return chop
        else:
            return 1

    def get_volumetric_data(self, chopping_factor):
        if self.contour_type == "total":
            volumetric_data = self.chgcar_data[self.chg_file_path].chop(
                self.chgcar_data[self.chg_file_path].all_numbers[0],
                chopping_factor
            )
        elif self.contour_type == "spin":
            volumetric_data = self.chgcar_data[self.chg_file_path].chop(
                self.chgcar_data[self.chg_file_path].all_numbers[1],
                chopping_factor
            )
        elif self.contour_type == "alfa":
            if self.chgcar_data[self.chg_file_path].alfa is None:
                self.chgcar_data[self.chg_file_path].calc_alfa_beta()
                volumetric_data = self.chgcar_data[self.chg_file_path].chop(
                    self.chgcar_data[self.chg_file_path].alfa,
                    chopping_factor
                )
            else:
                volumetric_data = self.chgcar_data[self.chg_file_path].alfa

        elif self.contour_type == "beta":
            if self.chgcar_data[self.chg_file_path].beta is None:
                self.chgcar_data[self.chg_file_path].calc_alfa_beta()
                volumetric_data = self.chgcar_data[self.chg_file_path].chop(
                    self.chgcar_data[self.chg_file_path].beta,
                    chopping_factor
                )
            else:
                volumetric_data = self.chgcar_data[self.chg_file_path].beta

        if volumetric_data is None:
            print("Invalid contour type")
            return
        else:
            return volumetric_data

    #@profile
    def add_contours(self):
        """ creates the isosurface contours from charge density data """

        if self.chgcar_data[self.chg_file_path] == None:
            # if no charge data was loaded, print message
            print("no data was found")
            return
        chopping_factor = self.get_chopping_factor()

        if self.current_contour_actor is not None:
            self.chg_plotter.remove_actor(self.current_contour_actor)

        volumetric_data = self.get_volumetric_data(chopping_factor)

        max_val = np.max(volumetric_data)
        min_val = np.min(volumetric_data)
        largest_value = np.max([np.abs(max_val), np.abs(min_val)])

        basis = self.chgcar_data[self.chg_file_path].atoms.cell[:]

        nx, ny, nz = volumetric_data.shape

        from vtk.util import numpy_support
        vtk_data = numpy_support.numpy_to_vtk(num_array=volumetric_data.ravel(order='F'), deep=False, array_type=vtk.VTK_DOUBLE)
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
        basis = basis.T
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
        if self.contour_type == "spin" :
            if largest_value> 0.5:
                contour_filter.SetValue(0, -self.eps * largest_value)
                contour_filter.SetValue(1, self.eps * largest_value)
            else:
                print("there is no spin polarization. Your structure is non-magnetic")
                contour_filter.SetValue(0, largest_value)
        else:
            contour_filter.SetValue(0, -self.eps * largest_value)
            contour_filter.SetValue(1, self.eps * largest_value)

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
            if file_path:
                self.chg_file_path = file_path
                self.process_chg_file(self.chg_file_path)
        self.chg_button_counter += 1

    def process_chg_file(self, file_path, init=True):
        """
        function to process CHGCAR file
        """
        self.progress_window = DialogWIndow(file_path)
        self.progress_window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.progress_window.show()
        if init:
            self.chg_file_path = file_path
        self.create_chgcar_data(self.chg_file_path, init)

    def close_progress_window(self):
        self.progress_window.close()

    def _after_reading(self):
        self.chg_plotter.setup_render_thread(5)

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
        data = self.get_volumetric_data(1)

        x_start, x_stop, y_start, y_stop, z_start, z_stop = [x if x >= 0 else 0 for x in self.box_bounds]
        box_min = np.array([x_start, y_start, z_start])
        box_max = np.array([x_stop, y_stop, z_stop])
        voxel_size = self.chgcar_data[self.chg_file_path].voxel_size()
        x_min, y_min, z_min = np.floor(box_min / voxel_size).astype(int)
        x_max, y_max, z_max = np.ceil(box_max / voxel_size).astype(int)
        grid_max = list(self.chgcar_data[self.chg_file_path].chgcar._grid)
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
        z = matrix[0]
        y = matrix[1]
        x = matrix[2]
        total_supercell = np.tile(self.chgcar_data[self.chg_file_path].all_numbers[0], (z, y, x))
        spin_supercell = np.tile(self.chgcar_data[self.chg_file_path].all_numbers[1], (z, y, x))
        self.chgcar_data[self.chg_file_path].all_numbers = [total_supercell, spin_supercell]

        multiplication = x * y * z
        aug_dict, aug_leftovers = self.chgcar_data[self.chg_file_path].read_augmentation(self.chgcar_data[self.chg_file_path].aug)
        aug_diff_dict, aug_diff_leftovers = self.chgcar_data[self.chg_file_path].read_augmentation(self.chgcar_data[self.chg_file_path].aug_diff)

        new_aug_dict, new_aug_leftovers = self.chgcar_data[self.chg_file_path].tile_dict_and_list(aug_dict, aug_leftovers, multiplication)
        new_aug_diff_dict, new_aug_diff_leftovers = self.chgcar_data[self.chg_file_path].tile_dict_and_list(aug_diff_dict, aug_diff_leftovers, multiplication)

        new_aug = self.chgcar_data[self.chg_file_path].rebuild_string(new_aug_dict, new_aug_leftovers)
        new_aug_diff = self.chgcar_data[self.chg_file_path].rebuild_string(new_aug_diff_dict, new_aug_diff_leftovers)
        self.chgcar_data[self.chg_file_path].aug = new_aug
        self.chgcar_data[self.chg_file_path].aug_diff = new_aug_diff
        print("done")

    def make_atoms_supercell(self, matrix, write_buffer=True):
        """ make a supercell from atoms. If CONTCAR or POSCAR exists, constraints will be added
        Args:
            matrix (array): an array of (X, Y, Z) factors to duplicate in selected directions
        """
        from  ase.io import read, write
        from  ase.build import make_supercell
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
        if write_buffer:
            self.buffer = io.StringIO()
            write(self.buffer, supercell_atoms, format='vasp')

        return supercell_atoms

    def read_supercell_to_vaspy(self, matrix):
        from ase.io import write, read
        import tempfile
        chg_path = self.chg_file_path
        supercell = self.make_atoms_supercell(matrix, write_buffer=True)

        # create temporary directory automatically
        tmpdir = tempfile.mkdtemp(prefix="vaspviewer_")

        # write POSCAR there
        write(os.path.join(tmpdir, "POSCAR"), supercell)

        # emit path exactly as your app expects
        self.load_data.emit(tmpdir)

        self.chg_file_path = chg_path
        # update internal CHGCAR data
        chg = self.chgcar_data[self.chg_file_path]
        chg._unit_cell_vectors = supercell.cell[:]
        chg.atoms = supercell
        chg._scale_factor = 1
        chg._grid = np.shape(chg.all_numbers[0])

        self.add_contours()

    def make_supercell(self):
        dialog = SupercellShapeDialog(initial_values=(2,2,1))

        if not dialog.exec_() == QDialog.Accepted:
            return
        else:
            matrix = dialog.get_values()
            print("User selected:", matrix)
            self.make_charge_supercell(matrix)
            self.read_supercell_to_vaspy(matrix)
            self.supercell_made = True


    def delete_atom(self, index):
        #print(f'index from chgcar tab {index}')

        idx = index + 1
        if self.chg_file_path in self.chgcar_data:
            aug_dict, aug_leftovers = self.chgcar_data[self.chg_file_path].read_augmentation(self.chgcar_data[self.chg_file_path].aug)
            aug_diff_dict, aug_diff_leftovers = self.chgcar_data[self.chg_file_path].read_augmentation(self.chgcar_data[self.chg_file_path].aug_diff)

            del aug_dict[idx]
            del aug_leftovers[index]
            del aug_diff_dict[idx]

            def new_dict(old_dict):
                return {i + 1: v for i, (_, v) in enumerate(sorted(old_dict.items()))}

            new_aug_dict = new_dict(aug_dict)
            new_aug_diff_dict = new_dict(aug_diff_dict)
            new_aug = self.chgcar_data[self.chg_file_path].rebuild_string(new_aug_dict, aug_leftovers)
            new_aug_diff = self.chgcar_data[self.chg_file_path].rebuild_string(new_aug_diff_dict, aug_diff_leftovers)

            self.chgcar_data[self.chg_file_path].aug = new_aug
            self.chgcar_data[self.chg_file_path].aug_diff = new_aug_diff

    def create_header_when_deleted(self):
        if self.chg_file_path in self.chgcar_data:
            import io
            stream = io.StringIO()
            self.structure_variable_control.save_poscar(stream)
            self.chgcar_data[self.chg_file_path].create_new_header(stream)
            stream.close()

    def write_chgcar(self):
        file_dialog = QFileDialog()
        file_dialog.setDirectory(self.chg_file_path)
        file_path, _ = file_dialog.getSaveFileName()
        if file_path:
            #if self.supercell_made is not None:
            #    self.chgcar_data[self.chg_file_path].create_new_header(self.buffer)

            self.chgcar_data[self.chg_file_path].save_all_file(
                file_path,
                [self.chgcar_data[self.chg_file_path].all_numbers[0]],
                [self.chgcar_data[self.chg_file_path].all_numbers[1]],
                self.chgcar_data[self.chg_file_path].aug,
                self.chgcar_data[self.chg_file_path].aug_diff
            )
        print("done")

    def closeEvent(self, QCloseEvent):
        """former closeEvent in case of many interactors"""
        super().closeEvent(QCloseEvent)
        self.chg_plotter.Finalize()


class SupercellShapeDialog(QDialog):
    """ Dialog Window for choosing a supercell shape"""
    def __init__(self, parent=None, initial_values=(1,1,1)):
        super().__init__(parent)
        self.setWindowTitle("Enter three integers")

        layout = QVBoxLayout(self)

        # Create spinboxes
        self.spin1 = QSpinBox()
        self.spin2 = QSpinBox()
        self.spin3 = QSpinBox()

        # Optional: set ranges
        for spin in (self.spin1, self.spin2, self.spin3):
            spin.setRange(-1000, 1000)

        # Set initial values
        self.spin1.setValue(initial_values[0])
        self.spin2.setValue(initial_values[1])
        self.spin3.setValue(initial_values[2])

        # Add to layout with labels
        for i, spin in enumerate((self.spin1, self.spin2, self.spin3), start=1):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Value {i}:"))
            row.addWidget(spin)
            layout.addLayout(row)

        # Buttons
        button_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(ok_btn)
        button_row.addWidget(cancel_btn)

        layout.addLayout(button_row)

    def get_values(self):
        return (self.spin1.value(), self.spin2.value(), self.spin3.value())

class DDECAtomSelector(QWidget):
    fragments_selected = QtCore.pyqtSignal(str, str)  # frag1, frag2
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.frag1_atoms = []
        self.frag2_atoms = []

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Fragment Selector")

        # Buttons
        self.btn_frag1 = QPushButton("choose selected atoms for frag1")
        self.btn_frag2 = QPushButton("choose selected atoms for frag2")

        # Labels to show selected atoms
        self.label_frag1 = QLabel("[]")
        self.label_frag2 = QLabel("[]")

        # Connect buttons
        self.btn_frag1.clicked.connect(self.handle_frag1)
        self.btn_frag2.clicked.connect(self.handle_frag2)

        # Layouts
        layout_frag1 = QHBoxLayout()
        layout_frag1.addWidget(self.btn_frag1)
        layout_frag1.addWidget(self.label_frag1)

        layout_frag2 = QHBoxLayout()
        layout_frag2.addWidget(self.btn_frag2)
        layout_frag2.addWidget(self.label_frag2)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout_frag1)
        main_layout.addLayout(layout_frag2)

        self.setLayout(main_layout)

    # -------- Button handlers --------

    def handle_frag1(self):
        self.frag1_atoms = self.choose_atoms_frag1()
        formatted = self.format_atoms(self.frag1_atoms)
        self.label_frag1.setText(formatted)
        self.frag1_formatted_atoms = formatted

    def handle_frag2(self):
        self.frag2_atoms = self.choose_atoms_frag2()
        formatted = self.format_atoms(self.frag2_atoms)
        self.label_frag2.setText(formatted)
        self.frag2_formatted_atoms = formatted

    # -------- Dummy selection functions --------
    # Replace these with your real selection logic

    def choose_atoms_frag1(self):
        frag = self.parent.structure_variable_control.print_selected_atoms(print_atoms=False)
        return frag

    def choose_atoms_frag2(self):
        frag = self.parent.structure_variable_control.print_selected_atoms(print_atoms=False)
        return frag

    # -------- Formatting logic --------

    def format_atoms(self, atom_list):
        if not atom_list:
            return "[]"

        atom_list = sorted(atom_list)
        result = []
        start = atom_list[0]
        prev = atom_list[0]

        for num in atom_list[1:]:
            if num == prev + 1:
                prev = num
            else:
                result.append(self._format_range(start, prev))
                start = num
                prev = num

        result.append(self._format_range(start, prev))

        return ",".join(result)

    def _format_range(self, start, end):
        length = end - start + 1
        if length >= 3:
            return f"{start}-{end}"
        elif length == 2:
            return f"{start}, {end}"
        else:
            return f"{start}"

    def closeEvent(self, event):
        if not self.frag1_formatted_atoms:
            QMessageBox.warning(self, "Warning", "Fragment 1 cannot be empty!")
            event.ignore()
            return
        if hasattr(self, "frag2_formatted_atoms"):
            frag2 = self.frag2_formatted_atoms
        else:
            frag2 = ""
        self.fragments_selected.emit(self.frag1_formatted_atoms, frag2)
        event.accept()

import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QFileDialog, QScrollArea
)


class RowWidget(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window  # reference to main window

        layout = QHBoxLayout(self)

        self.combo = QComboBox()
        self.combo.addItems(["add", "subtract", "multiply", "divide"])

        self.file_btn = QPushButton("Choose file")
        self.file_label = QLabel("No file selected")
        self.file_path = None

        self.remove_btn = QPushButton("−")  # remove button
        self.remove_btn.setFixedWidth(30)

        self.file_btn.clicked.connect(self.choose_file)
        self.remove_btn.clicked.connect(self.remove_row)

        layout.addWidget(self.combo)
        layout.addWidget(self.file_btn)
        layout.addWidget(self.file_label)
        layout.addWidget(self.remove_btn)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", self.parent_window.parent.chg_file_path)
        if path:
            import os
            self.file_path = path
            self.file_label.setText(os.path.basename(path))

    def get_data(self):
        return self.combo.currentText(), self.file_path

    def remove_row(self):
        # Remove this widget from layout and main list
        self.setParent(None)
        self.parent_window.rows.remove(self)


class VolumetricDataEditingWindow(QWidget):
    def __init__(self, chgcar_widget):
        super().__init__()
        self.parent = chgcar_widget
        self.vol_editing_paths = []
        self.setWindowTitle("File Math Processor")
        self.resize(600, 400)

        main_layout = QVBoxLayout(self)

        # Scroll area for many rows
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.rows_layout = QVBoxLayout(self.container)

        self.scroll.setWidget(self.container)

        main_layout.addWidget(self.scroll)

        is_chgcar_loaded = self.check_main_outcar()
        msg_layout = QHBoxLayout(self)
        msg_text = QLabel(is_chgcar_loaded)
        msg_layout.addWidget(msg_text)
        main_layout.addLayout(msg_layout)

        # Buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("+")
        self.do_btn = QPushButton("Do Math")

        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.do_btn)

        main_layout.addLayout(btn_layout)

        self.rows = []

        self.add_btn.clicked.connect(self.add_row)
        self.do_btn.clicked.connect(self.process)

        # Start with one row
        self.add_row()

    def check_main_outcar(self):
        if self.parent.chgcar_data == {}:
            msg = "No main CHGCAR data found! To manipulate grid density, load a CHGCAR first"
        else:
            msg = ""
        return msg

    def add_row(self):
        row = RowWidget(self)
        self.rows.append(row)
        self.rows_layout.addWidget(row)

    import numpy as np

    def process(self):
        if self.parent.chgcar_data == {}:
            print("No main CHGCAR loaded!")
            return

        self.operations_queue = []  # store (operation, filepath)
        self.pending_loads = 0

        for row in self.rows:
            op, path = row.get_data()
            if path:
                self.operations_queue.append((op, path))
                self.pending_loads += 1
                self.parent.create_chgcar_data(path, init=False)

        if self.pending_loads == 0:
            print("Nothing to load")
            return

        print("Loading files asynchronously...")

    def notify_chgcar_loaded(self, path):
        self.pending_loads -= 1

        if self.pending_loads == 0:
            print("All files loaded — performing math")
            self.perform_math()

    def perform_math(self):
        main_chg = self.parent.chgcar_data[self.parent.chg_file_path]

        main_total = main_chg.all_numbers[0]
        main_spin = main_chg.all_numbers[1]

        for op, path in self.operations_queue:
            thread = self.parent.chgcar_data[path]

            grid_total = thread.all_numbers[0]
            grid_spin = thread.all_numbers[1]

            if grid_total.shape != main_total.shape:
                print("Shape mismatch:", path)
                continue

            # ---- TOTAL CHANNEL ----
            self.apply_operation(main_total, grid_total, op)

            # ---- SPIN CHANNEL ----
            self.apply_operation(main_spin, grid_spin, op)

        # add contours
        self.parent.add_contours()
        print("Math completed.")

    def apply_operation(self, target, other, op):
        if op == "add":
            target += other

        elif op == "subtract":
            target -= other

        elif op == "multiply":
            target *= other

        elif op == "divide":
            with np.errstate(divide='ignore', invalid='ignore'):
                np.divide(target, other, out=target, where=other != 0)



