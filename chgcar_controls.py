import time
tic = time.perf_counter()
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel, QFileDialog, QPushButton
from PyQt5 import QtCore
import pyvista as pv
from pyvistaqt import QtInteractor
import numpy as np
from matplotlib.colors import ListedColormap
#sys.path.insert(1, "/home/lnowakowski/python/Scripts/")
import chopPARCHG_test_chgcar_comp as chp
import sys
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

        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.chg_plotter = QtInteractor()
        self.chg_plotter.set_background(color="#1e1f22")
        self.chg_plotter.add_camera_orientation_widget()

        self.chg_file_button = QPushButton('open CHGCAR')
        self.chg_file_button.clicked.connect(self.show_chg_dialog)
        self.layout.addWidget(self.chg_file_button)

        self.chg_plotter.view_yz()
        self.chg_plotter.camera_position = [(5, -60, 13), (4.8, 1.7, 12.3), (0, 0, 1)]
        self.chg_plotter.camera.enable_parallel_projection()
        self.chg_plotter.camera.parallel_scale = 18
        self.layout.addWidget(self.chg_plotter.interactor)
        self.setLayout(self.layout)
        #self.add_structure()
        # self.add_bonds(1,1)
        #self.add_unit_cell(self.data.x, self.data.y, self.data.z)

    def create_chgcar_data(self):
        tic = time.perf_counter()
        chopping_factor = 1
        self.charge_data = chp.PoscarParser(self.chg_file_path, chopping_factor)
        self.add_contours()

        toc = time.perf_counter()
        print(f'charge density data read and displayed. Time elapsed: {toc - tic} s')

    def set_contour_type(self, contour_type):
        self.contour_type = contour_type

    def update_eps(self):
        self.eps = self.chg_eps_slider.value() / 100

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
            ##### dokończyć ######
            self.structure_control_widget.end_geometry()
            self.plane_actor.GetProperty().SetOpacity(0)
            if self.contour_type == "spin":
                contours = pvgrid.contour([self.eps * max_val, self.eps * min_val])
            else:
                contours = pvgrid.contour([self.eps * max_val])

            colors = pv.LookupTable()
            colors.scalar_range = (self.eps * min_val, self.eps * max_val)
            lightblue = np.array([0 / 256, 255 / 256, 254 / 256, 1.0])
            yellow = np.array([255 / 256, 255 / 256, 0 / 256, 1.0])
            mapping = np.linspace(self.eps * min_val, self.eps * max_val, 256)
            newcolors = np.empty((256, 4))
            newcolors[mapping > 0] = yellow
            newcolors[mapping < 0] = lightblue
            my_colormap = ListedColormap(newcolors)
            # colors.cmap = [(0,255,254), 'yellow']
            self.chg_plotter.add_mesh(contours, name='isosurface', smooth_shading=True, opacity=1, cmap=my_colormap)

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
    main_window = ChgcarVis()
    main_window.chg_file_path = "F:\\syncme\\modelowanie DFT\\lobster_tests\\1.ceo_bulk\\1.lobster_5.1.0\\1.ceo_bulk\\CHGCAR"
    main_window.setWindowTitle("Main Window")
    main_window.resize(300, 150)
    main_window.show()
    sys.exit(app.exec_())
