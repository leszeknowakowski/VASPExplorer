import pyqtgraph as pg
import pyvista as pv
from pyvista.plotting import plotter
from pyvistaqt import QtInteractor, MainWindow
from vasp_data import VaspData
import os
import sys
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout,QLabel, QHBoxLayout, QFrame, QSlider
from PyQt5.QtGui import QCloseEvent, QIcon
from functools import reduce
import operator
from PyQt5 import QtCore
from scipy.spatial.distance import pdist, squareform
import numpy as np

import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkFiltersSources import vtkPointSource, vtkSphereSource, vtkConeSource, vtkLineSource
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkInteractionWidgets import vtkCameraOrientationWidget
from vtkmodules.vtkRenderingCore import vtkActor, vtkGlyph3DMapper, vtkRenderWindow, vtkRenderWindowInteractor, vtkRenderer, vtkPolyDataMapper
import QVTKRenderWindowInteractor as QVTK
from vtk import vtkCamera
QVTKRenderWindowInteractor = QVTK.QVTKRenderWindowInteractor
colors = vtkNamedColors()
import time
import platform


class ReadNebData:
    def __init__(self, dir):
        self.dir = dir
        self.neb_dirs = []
        self.max_min_dirs = self.find_start_stop_dirs()
        self.neb_energies = []
        self.neb_positions = []
        self.start_stop_energies = []
        self.start_stop_positions = []

        self.parse_middle_dirs()
        self.parse_start_stop_dirs()

    def find_start_stop_dirs(self):
        for item in os.listdir(self.dir):
            if os.path.isdir(os.path.join(self.dir, item)):
                self.neb_dirs.append(item)
        max_min_dirs = [min(self.neb_dirs), max(self.neb_dirs)]
        return max_min_dirs

    def parse_middle_dirs(self):
        for item in os.listdir(self.dir):
            neb_dir = os.path.join(self.dir, item)
            if os.path.isdir(neb_dir) and item not in self.max_min_dirs:
                data = VaspData(neb_dir)
                self.neb_energies.append(data.outcar_data.find_energy())
                self.neb_positions.append(data.outcar_data.find_coordinates())

    def parse_start_stop_dirs(self):
        for item in os.listdir(self.dir):
            neb_dir = os.path.join(self.dir, item)
            if os.path.isdir(neb_dir) and item in self.max_min_dirs:
                self.data = VaspData(neb_dir)
                self.start_stop_positions.append(self.data.coordinates)
                self.start_stop_energies.append(self.data.outcar_energies)

#####################################################################################################################

class NebWindow(MainWindow):
    def __init__(self, parent=None, show=True):
        """ Initialize GUI """
        super().__init__()

        QMainWindow.__init__(self, parent)
        if platform.system() == 'Linux':
            dir = './'
        else:
            dir = "D:\\syncme-from-c120\\modelowanie DFT\\co3o4_new_new\\9.deep_o2_reduction\\5.newest_after_statistics\\2.NEB\\1.2ominus_o2ads\\3.third"
        self.neb = ReadNebData(dir)

        script_dir = os.path.dirname(__file__)
        colors_file = os.path.join(script_dir, 'elementColorSchemes.json')
        with open(colors_file, 'r') as file:
            self.color_data = json.load(file)
        self.atom_colors = [self.color_data[self.neb.data.symbols[i]] for i in range(len(self.neb.data.atoms_symb_and_num))]


        self.init_UI()




    def init_UI(self):
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Create main layout
        self.main_layout = QVBoxLayout()
        main_widget.setLayout(self.main_layout)

        self.sliderLayout = QHBoxLayout()
        self.geo_slider = QSlider()
        self.geo_slider.setOrientation(QtCore.Qt.Horizontal)
        self.geo_slider.setMinimum(1)
        self.geo_slider.setMaximum(len(self.neb.neb_positions[0]))
        self.geo_slider.setValue(1)
        self.geo_slider.valueChanged.connect(self.update_chart)
        self.geo_slider.valueChanged.connect(self.update_intermediate_structures)
        self.sliderLayout.addWidget(self.geo_slider)

        self.main_layout.addLayout(self.sliderLayout)

        # Top layout with QVTKRenderWindowInteractor
        self.topLayout = QHBoxLayout()

        self.add_plotters()

        self.main_layout.addLayout(self.topLayout)

        ## energy plot frame
        self.energy_plot_frame = QFrame(self)
        self.energy_plot_frame.setFrameShape(QFrame.Panel)
        self.energy_plot_frame.setFrameShadow(QFrame.Raised)
        self.energy_plot_frame.setStyleSheet("background-color: #1e1f22; color: #cbcdd2;")
        self.energy_plot_frame.setLineWidth(10)
        self.energy_plot_frame.setMaximumHeight(300)
        self.energy_plot_frame_layout = QVBoxLayout(self.energy_plot_frame)
        self.energy_plot_layout()

        self.add_start_end_structures()
        self.add_intermediate_structures()


        # Set main window properties
        self.setWindowTitle("PyQt5 with PyVistaQt")
        self.resize(1600, 800)

    def add_plotters(self):
        self.plotters = []
        widget = QVTKRenderWindowInteractor() # maybe add parent
        self.topLayout.addWidget(widget)
        style = vtkInteractorStyleTrackballCamera()
        widget.GetRenderWindow().GetInteractor().SetInteractorStyle(style)

        x = list(np.linspace(0, 1, len(self.neb.neb_dirs)+1))
        for i in range(len(self.neb.neb_dirs)):
            ren = vtkRenderer()
            ren.SetViewport(x[i], 0, x[i + 1], 1)
            ren.SetBackground(colors.GetColor3d("White"))

            self.camera = vtkCamera()
            self.camera.SetPosition(0, -50, 0)  # Position on the x-axis
            self.camera.SetFocalPoint(5, 5,5)  # Look towards the origin
            self.camera.SetViewUp(0, 0, 1)  # z-axis is up
            self.camera.SetParallelProjection(1)
            self.camera.SetParallelScale(14)


            ren.SetActiveCamera(self.camera)
            ren.ResetCamera()

            widget.GetRenderWindow().AddRenderer(ren)

            orientation_widget = vtkCameraOrientationWidget()
            orientation_widget.SetParentRenderer(ren)
            orientation_widget.SetAnimate(True)
            orientation_widget.SetAnimatorTotalFrames(20)
            orientation_widget.On()

            self.plotters.append(ren)
        widget.Initialize()
        widget.Start()
        widget.GetRenderWindow().Render()

    def energy_plot_layout(self):
        self.energy_plot_widget = pg.PlotWidget()
        self.update_chart()
        x, y = self.update_energy_data()
        self.energy_plot_widget.plot(x,y)

        self.energy_plot_frame_layout.addWidget(self.energy_plot_widget)
        self.main_layout.addWidget(self.energy_plot_frame)

    def update_energy_data(self):
        x = list(range(1, len(self.neb.neb_dirs) + 1))
        y = []
        #y.append(self.neb.start_stop_energies[0])
        y.append(float("-.42642023E+03"))
        for i in range(len(self.neb.neb_energies)):
            lst = self.neb.neb_energies[i]
            y.append(lst[self.geo_slider.value()])
        y.append(self.neb.start_stop_energies[1])
        y = [item for sublist in y for item in (sublist if isinstance(sublist, list) else [sublist])]
        return x, y

    def update_chart(self):
        self.energy_plot_widget.clear()
        x, y = self.update_energy_data()
        self.energy_plot_widget.plot(x, y)
        self.scatter_plot = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 120))
        self.scatter_plot.addPoints(x=x, y=y)
        self.energy_plot_widget.addItem(self.scatter_plot)

    def add_sphere(self, coord, col, radius, plotter):
        sphereSource = vtkSphereSource()
        sphereSource.SetRadius(radius)
        sphereSource.SetCenter(*coord)
        sphereSource.SetPhiResolution(10)
        sphereSource.SetThetaResolution(10)

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(sphereSource.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)
        if col == [0, 0, 175]:
           color='Blue'
        elif col == [254,3,0]:
            color = "Red"
        actor.GetProperty().SetColor(colors.GetColor3d(color))

        plotter.AddActor(actor)

    def add_bonds(self, coordinates, plotter):
        """
        render bonds as lines. First calculate all pairs, which distance is less than threshold,
        and then uses vtkLine to create a bond. For unknown reason, function doesn't work with
        connect signal when self.bond_threshold is passed as argument, so it has to be implemen-
        ted in this module. So does all functions which depend on slider/checkbox variables
        """
        self.bond_threshold = 2.3
        bond_threshold = self.bond_threshold
        geometry_slider_value = self.geo_slider.value()
        coord_pairs = []

        # Calculate pairwise distances
        distances = squareform(pdist(coordinates))

        # Get the upper triangular part of the distances matrix
        upper_triangle = np.triu(distances, k=1)

        # Find pairs with distance less than threshold (excluding distances between the same point pairs)
        pairs = np.argwhere((upper_triangle < bond_threshold) & (upper_triangle > 0))
        colors = vtkNamedColors()
        for pair in pairs:
            point1, point2 = pair
            coord1 = coordinates[point1]
            coord2 = coordinates[point2]
            coord_pairs.append([coord1, coord2])
        for pair in coord_pairs:
            if True:  # self.master_bond_visibility == 2:
                line_source = vtkLineSource()
                line_source.SetPoint1(pair[0])
                line_source.SetPoint2(pair[1])
                mapper = vtkPolyDataMapper()
                mapper.SetInputConnection(line_source.GetOutputPort())
                actor = vtkActor()
                actor.SetMapper(mapper)
                actor.GetProperty().SetLineWidth(5)
                actor.GetProperty().SetColor(colors.GetColor3d('Black'))

                plotter.AddActor(actor)
                #self.structure_plot_widget.bond_actors.append(actor)

    def add_structure(self, coordinates, plotter):
        for idx, coord in enumerate(coordinates):
            self.add_sphere(coord, self.atom_colors[idx], 0.5, plotter)

    def add_start_end_structures(self):
        plotter1 = self.plotters[0]
        plotter_last = self.plotters[-1]
        start_pos = self.neb.start_stop_positions[0]
        stop_pos = self.neb.start_stop_positions[1]

        self.add_structure(start_pos, plotter1)
        self.add_bonds(start_pos, plotter1)
        self.add_structure(stop_pos, plotter_last)
        self.add_bonds(stop_pos, plotter_last)

    def add_intermediate_structures(self):
        images = len(self.neb.neb_dirs)
        coordinates = self.neb.neb_positions
        image_coordinates = []
        for image in coordinates:
            image_coordinates.append(image[self.geo_slider.value()])
        for i in range(0, images-2): # loop for plotters
            plotter = self.plotters[i+1]
            self.add_structure(image_coordinates[i], plotter)
            self.add_bonds(image_coordinates[i], plotter)

    def update_intermediate_structures(self):
        images = len(self.neb.neb_dirs)
        coordinates = self.neb.neb_positions
        image_coordinates = []
        tic = time.perf_counter()
        for i in range(0, images-2):
            plotter = self.plotters[i+1]
            for actor in list(plotter.GetActors()):
                plotter.RemoveActor(actor)

        for image in coordinates:
            image_coordinates.append(image[self.geo_slider.value()])
        for i in range(0, images-2): # loop for plotters
            plotter = self.plotters[i+1]
            self.add_structure(image_coordinates[i], plotter)
            self.add_bonds(image_coordinates[i], plotter)
        for i in range(0, images - 2):  # loop for plotters
            plotter.GetRenderWindow().Render()
        toc = time.perf_counter()
        print(toc-tic)
'''
    def closeEvent(self, QCloseEvent):
        super().closeEvent(QCloseEvent)
        for plotter in self.plotters:
            plotter.Finalize()
'''

if __name__ == "__main__":
    dir = ("D:\\syncme-from-c120\\modelowanie DFT\\co3o4_new_new\\9.deep_o2_reduction\\5.newest_after_statistics\\2.NEB\\1"
           ".2ominus_o2ads\\2.second")
    #neb = ReadNebData(dir)
    app = QApplication(sys.argv)
    #app.setStyleSheet(STYLE_SHEET)
    window = NebWindow()
    window.show()
    #sys.exit(app.exec_())
    app.exec_()
    print('done')

