import time

import vtk

tic = time.perf_counter()
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, \
    QFileDialog, QPushButton, QHBoxLayout, QSlider,  QMainWindow
from PyQt5 import QtCore
import numpy as np
import chopPARCHG_test_chgcar_comp as chp
import sys
import os
toc = time.perf_counter()
print(f'importing in chgcar, time: {toc - tic:0.4f} seconds')


class DialogWIndow(QWidget):
    """
    This class provides a window which is shown when heavy I/O operations
    are done, e.g. reading CHGCAR file
    """
    def __init__(self):
        """ Initialize """
        super().__init__()
        layout = QVBoxLayout()
        self.setMinimumSize(300,300)
        self.label1 = QLabel('processing...')
        layout.addWidget(self.label1)
        self.setLayout(layout)


class ChgcarVis(QWidget):
    """ this class provides functionality for reading, displaying and
    controlling the electron charge density plots.

    Parameters
    ----------------------
    plotter : class
        structure control widget plotter from structure plot

    """
    def __init__(self, plotter):
        """ Initialize """
        super().__init__()
        self.chg_plotter = plotter
        self.contour_type = 'total'
        self.charge_data = None
        self.chg_button_counter = 0
        self.current_contour_actor = None

        self.initUI()

    def initUI(self):
        """ initialize GUI for this tab """
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        # create buttons
        self.chg_file_button = QPushButton('open CHGCAR')
        self.chg_file_button.clicked.connect(self.show_chg_dialog)
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
        self.layout.addLayout(self.eps_layout)

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
        # timer
        tic = time.perf_counter()
        chopping_factor = 1
        if os.path.exists(self.chg_file_path):
            try:
                self.charge_data = chp.PoscarParser(self.chg_file_path, chopping_factor)
            except:
                print("ooopsie! cannot read data")

        # add contours
        self.add_contours()

        toc = time.perf_counter()
        print(f'charge density data read and displayed. Time elapsed: {toc - tic} s')

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

        # volumetric_data is the actual data with charge
        volumetric_data = {
            "total": self.charge_data.all_numbers[0],
            "spin": self.charge_data.all_numbers[1],
            "alfa": self.charge_data.alfa,
            "beta": self.charge_data.beta
        }.get(self.contour_type, None)

        if volumetric_data is None:
            print("Invalid contour type")
            return

        volumetric_data = volumetric_data.swapaxes(0, 2)

        max_val = np.max(volumetric_data)
        min_val = np.min(volumetric_data)
        largest_value = np.max([np.abs(max_val), np.abs(min_val)])

        basis = np.array(self.charge_data.unit_cell_vectors())*self.charge_data.scale_factor()

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
            contour_filter.SetValue(0, -self.eps * largest_value)
            contour_filter.SetValue(1, self.eps * largest_value)
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

    def show_chg_dialog(self):
        """
        functon to create window with charge density file choose.
        When button is clicked first, it will load CHGCAR from chg_file_path, if it exists.
        When clicked again (or is there is no CHGCAR), it will open file dialog
        """

        if os.path.exists(self.chg_file_path) and self.chg_button_counter == 0:
            self.create_chgcar_data()
            self.chg_button_counter += 1
        else:
            self.chg_button_counter += 1
            self.w = DialogWIndow()
            self.w.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
            self.w.show()

            file_dialog = QFileDialog()
            file_dialog.setDirectory(self.chg_file_path)
            file_path, _ = file_dialog.getOpenFileName(self, "choose charge density file")
            self.chg_file_path = file_path

            self.create_chgcar_data()
            self.w.close()

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

    chg_widget.chg_file_path = "D:\\syncme-from-c120\\test_for_doswizard\\9.CHGCAR\\1.spinel_spinupdown\\CHGCAR"
    chg_widget.setWindowTitle("Main Window")
    #chg_widget.create_chgcar_data()
    win.resize(1000, 850)
    win.show()
    sys.exit(app.exec_())
