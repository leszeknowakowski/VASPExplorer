import time
tic = time.perf_counter()
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, QFileDialog, QPushButton, QHBoxLayout, QSlider, \
    QLineEdit
from PyQt5 import QtCore
import pyvista as pv
from pyvistaqt import QtInteractor
import numpy as np
from matplotlib.colors import ListedColormap
#sys.path.insert(1, "/home/lnowakowski/python/Scripts/")
import chopPARCHG_test_chgcar_comp as chp
import sys
import os
toc = time.perf_counter()
print(f'importing in chgcar, time: {toc - tic:0.4f} seconds')


class DialogWIndow(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setMinimumSize(300,300)
        self.label1 = QLabel('processing...')
        layout.addWidget(self.label1)
        self.setLayout(layout)


class ChgcarVis(QWidget):
    def __init__(self, structure_control_widget):
        super().__init__()
        self.structure_control_widget = structure_control_widget
        self.contour_type = 'total'
        self.charge_data = None

        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.chg_plotter = self.structure_control_widget.plotter

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
        if type == "total":
            self.contour_type = "total"
        elif type == "spin":
            self.contour_type = "spin"
        elif type == "alfa":
            self.contour_type = "alfa"
        elif type == "beta":
            self.contour_type = "beta"

    def create_chgcar_data(self):
        tic = time.perf_counter()
        chopping_factor = 1
        self.charge_data = chp.PoscarParser(os.path.join(self.chg_file_path, "CHGCAR"), chopping_factor)
        self.add_contours()

        toc = time.perf_counter()
        print(f'charge density data read and displayed. Time elapsed: {toc - tic} s')

    def set_contour_type(self, contour_type):
        self.contour_type = contour_type

    def update_eps(self):
        self.eps = self.chg_eps_slider.value() / 100

    def change_eps_label(self, value):
        self.chg_eps_value_label.setText(str(value/100))

    def add_contours(self):
        if self.charge_data == None:
            print("no data was found")
        else:
            if self.contour_type == "total":
                test_vol = self.charge_data.all_numbers[0]
            elif self.contour_type == "spin":
                test_vol = self.charge_data.all_numbers[1]
            elif self.contour_type == "alfa":
                test_vol = self.charge_data.alfa
            elif self.contour_type == "beta":
                test_vol = self.charge_data.beta
            test_vol = test_vol.swapaxes(0, 2)
            max_val = np.max(test_vol)
            min_val = np.min(test_vol)
            pvgrid = pv.ImageData()
            pvgrid.dimensions = test_vol.shape
            pvgrid.origin = (0, 0, 0)
            pvgrid.spacing = tuple(self.charge_data.calculate_grid_spacings())
            pvgrid.point_data["values"] = test_vol.flatten(order="F")
            if self.contour_type == "spin":
                contours = pvgrid.contour([self.eps * max_val, self.eps * min_val])
            else:
                contours = pvgrid.contour([self.eps * max_val])

            colors = pv.LookupTable()
            colors.scalar_range = (self.eps * min_val, self.eps * max_val)
            lightblue = np.array([0 / 256, 255 / 256, 254 / 256, 1.0])
            yellow = np.array([255 / 256, 255 / 256, 0 / 256, 1.0])
            black = np.array([0 / 256, 0 / 256, 0 / 256, 1.0])
            mapping = np.linspace(self.eps * min_val, self.eps * max_val, 256)
            newcolors = np.empty((256, 4))
            newcolors[mapping >= 0] = yellow
            #newcolors[mapping == 0] = black
            newcolors[mapping < 0] = lightblue
            my_colormap = ListedColormap(newcolors)
            colors.cmap = ['red', 'red']
            try:
                self.chg_plotter.add_mesh(contours, name='isosurface', smooth_shading=True, opacity=1, cmap=my_colormap)
            except ValueError:
                print("contour is empty - there is too large/small epsilon or - if You want to plot spin density - structure is non-magnetic")

    def clear_contours(self):
        pvgrid = pv.ImageData()
        pvgrid.dimensions=(10,10,10)
        pvgrid.origin=(0,0,0)
        pvgrid.spacing=(1,1,1)
        data = np.random.rand(10,10,10)
        pvgrid.point_data["values"]=data.flatten(order="F")
        contours = pvgrid.contour()
        self.plotter.add_mesh(contours, opacity=0, name='isosurface')

    def add_structure(self):
        for actor in self.structure_control_widget.plotter.actors.values():
            self.chg_plotter.add_actor(actor)

    def clear_contours(self):
        pvgrid = pv.ImageData()
        pvgrid.dimensions = (10, 10, 10)
        pvgrid.origin = (0, 0, 0)
        pvgrid.spacing = (1, 1, 1)
        data = np.random.rand(10, 10, 10)
        pvgrid.point_data["values"] = data.flatten(order="F")
        contours = pvgrid.contour()
        self.chg_plotter.add_mesh(contours, opacity=0, name='isosurface')

    def show_chg_dialog(self):
        if self.chg_file_path:
            self.create_chgcar_data()
        else:
            self.w = DialogWIndow()
            self.w.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
            self.w.show()

            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getOpenFileName(self, "choose charge density file")
            self.chg_file_path = file_path

            self.create_chgcar_data()
            self.w.close()
    def closeEvent(self, QCloseEvent):
        super().closeEvent(QCloseEvent)
        self.chg_plotter.Finalize()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = ChgcarVis("a")
    main_window.chg_file_path = "D:\\OneDrive - Uniwersytet Jagielloński\\Studia\\python\\vasp_geo\\scripts_from_Krypton"
    main_window.setWindowTitle("Main Window")
    main_window.create_chgcar_data()
    main_window.resize(1000, 850)
    main_window.show()
    sys.exit(app.exec_())
