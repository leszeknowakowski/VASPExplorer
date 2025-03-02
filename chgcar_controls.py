import time
tic = time.perf_counter()
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, QFileDialog, QPushButton, QHBoxLayout, QSlider, \
    QLineEdit, QMainWindow
from PyQt5 import QtCore
import pyvista as pv
from pyvistaqt import QtInteractor
import numpy as np
from matplotlib.colors import ListedColormap
import chopPARCHG_test_chgcar_comp as chp
import sys
import os
toc = time.perf_counter()
print(f'importing in chgcar, time: {toc - tic:0.4f} seconds')


class DialogWIndow(QWidget):
    """
    This class provides a window which is shown when heavy I/O operations
    are done, eg. reading CHGCAR file
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
    structure_control_widget : class
        structure control widget from main window

    """
    def __init__(self, plotter):
        """ Initialize """
        super().__init__()
        self.chg_plotter = plotter
        self.contour_type = 'total'
        self.charge_data = None
        self.chg_button_counter = 0

        self.initUI()

    def initUI(self):
        """ initialize GUI for this tab """
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        # this is the same plotter as plotter from StructureControlWidget
        #self.chg_plotter = self.structure_control_widget.plotter

        # create buttons
        self.chg_file_button = QPushButton('open CHGCAR')
        self.chg_file_button.clicked.connect(self.show_chg_dialog)
        self.layout.addWidget(self.chg_file_button)

        spin_btn_layout = QHBoxLayout()

        self.total_btn = QPushButton('total')
        self.spin_btn = QPushButton('spin')
        self.alfa_btn = QPushButton('alfa')
        self.beta_btn = QPushButton('beta')
        self.clear_btn = QPushButton('clear')

        spin_btns = [self.total_btn, self.spin_btn, self.alfa_btn, self.beta_btn, self.clear_btn]
        spin_types = ['total', 'spin', 'alfa', 'beta', 'clear']

        for btn in spin_btns:
            spin_btn_layout.addWidget(btn)

        self.total_btn.clicked.connect(lambda: self.set_spin_type(type="total"))
        self.spin_btn.clicked.connect(lambda: self.set_spin_type(type="spin"))
        self.alfa_btn.clicked.connect(lambda: self.set_spin_type(type="alfa"))
        self.beta_btn.clicked.connect(lambda: self.set_spin_type(type="beta"))

        self.total_btn.clicked.connect(self.add_contours)
        self.spin_btn.clicked.connect(self.add_contours)
        self.alfa_btn.clicked.connect(self.add_contours)
        self.beta_btn.clicked.connect(self.add_contours)
        self.clear_btn.clicked.connect(self.clear_contours)

        self.layout.addLayout(spin_btn_layout)

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

        if type == "total":
            self.contour_type = "total"
        elif type == "spin":
            self.contour_type = "spin"
        elif type == "alfa":
            self.contour_type = "alfa"
        elif type == "beta":
            self.contour_type = "beta"

    def create_chgcar_data(self):
        """ creates data for plotting  """
        # timer
        tic = time.perf_counter()
        chopping_factor = 1
        if os.path.exists(os.path.join(self.chg_file_path, "CHGCAR")):
            self.charge_data = chp.PoscarParser(os.path.join(self.chg_file_path, "CHGCAR"), chopping_factor)
        elif os.path.exists(self.chg_file_path):
            try:
                self.charge_data = chp.PoscarParser(self.chg_file_path, chopping_factor)
            except:
                print("ooopsie! cannot read data")

        # add contours
        self.add_contours()

        toc = time.perf_counter()
        print(f'charge density data read and displayed. Time elapsed: {toc - tic} s')

    def set_contour_type(self, contour_type):
        """
        set the contour type. Function is connected to buttons
        Deprecated/
        """
        self.contour_type = contour_type

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
        else:
            # volumetric_data is the actual data with charge
            if self.contour_type == "total":
                volumetric_data = self.charge_data.all_numbers[0]
            elif self.contour_type == "spin":
                volumetric_data = self.charge_data.all_numbers[1]
            elif self.contour_type == "alfa":
                volumetric_data = self.charge_data.alfa
            elif self.contour_type == "beta":
                volumetric_data = self.charge_data.beta
            volumetric_data = volumetric_data.swapaxes(0, 2)

            max_val = np.max(volumetric_data)
            min_val = np.min(volumetric_data)
            largest_value = np.max([np.abs(max_val), np.abs(min_val)])

            # create point grid
            pvgrid = pv.ImageData()
            pvgrid.dimensions = volumetric_data.shape
            pvgrid.origin = (0, 0, 0)
            pvgrid.spacing = tuple(self.charge_data.calculate_grid_spacings())
            pvgrid.point_data["values"] = volumetric_data.flatten(order="F")

            # create contours. If spin, create two - for positive and negative values
            if self.contour_type == "spin":
                #contours_up = pvgrid.contour(isosurfaces=[self.eps * largest_value])
                #contours_down = pvgrid.contour(isosurfaces=[- self.eps * largest_value])
                contours = pvgrid.contour(isosurfaces=[-self.eps*largest_value, self.eps*largest_value],)
            else:
                contours = pvgrid.contour([self.eps * max_val])

            # create colormap
            colors = pv.LookupTable()
            colors.scalar_range = (self.eps * min_val, self.eps * max_val)
            lightblue = np.array([0 / 256, 255 / 256, 254 / 256, 1.0])
            yellow = np.array([255 / 256, 255 / 256, 0 / 256, 1.0])
            black = np.array([0 / 256, 0 / 256, 0 / 256, 1.0])
            mapping = np.linspace( min_val,  max_val, 2)
            newcolors = np.empty((2, 4))
            newcolors[mapping >= 0] = yellow
            newcolors[mapping < 0] = lightblue
            my_colormap = ListedColormap(newcolors)
            colors.cmap = my_colormap
            # add contours to a plotter
            try:
                if self.contour_type == "spin":

                    self.contours_actor = self.chg_plotter.add_mesh(contours, name='isosurface', smooth_shading=True, opacity=1, cmap=colors) #cmap=my_colormap)
            except ValueError:
                print("contour is empty - there is too large/small epsilon or - if You want to plot spin density - structure is non-magnetic")
        print("done")
    def clear_contours(self):
        """ removes the contours from plotter by adding zero volume contour
        TODO: maybe it is possible to jsut delete actors?
        """
        pvgrid = pv.ImageData()
        pvgrid.dimensions = (10, 10, 10)
        pvgrid.origin = (0, 0, 0)
        pvgrid.spacing = (1, 1, 1)
        data = np.random.rand(10, 10, 10)
        pvgrid.point_data["values"] = data.flatten(order="F")
        contours = pvgrid.contour()
        self.chg_plotter.add_mesh(contours, opacity=0, name='isosurface')
        print('cleared')

    def show_chg_dialog(self):
        """functon to create window with charge density file choose.
        When button is clicked first, it will load CHGCAR from chg_file_path, if it exists.
        When clicked again (or is there is no CHGCAR), it will open file dialog
        """

        if os.path.exists(os.path.join(self.chg_file_path, "CHGCAR*")) and self.chg_button_counter == 0:
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

    chg_widget.chg_file_path = "D:\\syncme-from-c120\\test_for_doswizard\\9.CHGCAR\\1.spinel_spinupdown"
    chg_widget.setWindowTitle("Main Window")
    #chg_widget.create_chgcar_data()
    win.resize(1000, 850)
    win.show()
    sys.exit(app.exec_())
