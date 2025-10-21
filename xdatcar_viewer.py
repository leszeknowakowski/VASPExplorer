import time

import sys
import platform
import os
import numpy as np
from scipy.spatial.distance import pdist, squareform
from console_widget import PythonConsole
import pyqtgraph as pg
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'third_party'))

from config import AppConfig
tic = time.perf_counter()
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, \
    QToolBar, QAction, QFileDialog, QMenu, QSplashScreen, QLabel, QStyleFactory, QDialog, QHBoxLayout, QVBoxLayout, QGroupBox
from PyQt5.QtGui import QIcon, QPixmap, QFont, QPalette, QColor
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5 import QtWidgets
from PyQt5 import QtCore

from vtk import vtkNamedColors, vtkPlaneSource, vtkActor, vtkLineSource, vtkSphereSource, \
    vtkPoints, vtkCellArray, vtkLine, vtkPolyData, vtkPolyDataMapper, vtkArrowSource, \
vtkTransformPolyDataFilter, vtkTransform
from vtkmodules.vtkCommonCore import (
    vtkMath,
    vtkMinimalStandardRandomSequence
)
from vtkmodules.vtkCommonMath import vtkMatrix4x4

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        from structure_plot import StructureViewer
        from vasp_data import VaspData
        dir = self.set_working_dir()
        self.data = VaspData(dir)

        self.structure_plot_interactor_widget = StructureViewer(self.data, self)
        self.structure_plot_control_tab = StructureControlsWidget(self.structure_plot_interactor_widget, self)

        main_layout.addWidget(self.structure_plot_interactor_widget)
        main_layout.addWidget(self.structure_plot_control_tab)

    def set_working_dir(self):
        """ gets the current working dir. Useful for building"""
        if platform.system() == 'Linux':
            dir = './'
        elif platform.system() == 'Windows':
            cwd = os.getcwd()
            files_to_check = ['CONTCAR', 'POSCAR', 'OUTCAR']

            if any(os.path.isfile(os.path.join(cwd, fname)) for fname in files_to_check):
                dir = cwd
            else:
                # dir = ("D:\\syncme\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98")
                # dir = ("D:\\syncme\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt")
                # dir = "D:\\syncme\\modelowanie DFT\\lobster_tests\\Si\\Si"
                dir = r"D:\syncme\modelowanie DFT\1.interface\2.interface_3x3\34.co3o4_3x3_ceria_mlff"
                # dir = r"H:\3.LUMI\6.interface\2.interface\4.MLFF\3.validation\2.new_june2025\8.interaface_spinel_3x3_ceria_mlff_closer\2.MLFF"
                # dir = r'D:\syncme\modelowanie DFT\2.all_from_lumi\6.interface\2.interface\1.Co3O4_3x3\4.co3o4_3x3_ceria_mlff\1.cluster_separate\1.first\1.bader'
                #dir = r'D:\syncme\test_for_doswizard\999.fast_atoms'
                # dir = r"D:\syncme\test_for_doswizard\colorful_atoms"
                # dir = r'D:\syncme\test_for_doswizard\5.only_POSCAR' # poscar with D1, D2, Ce1 etc.
                #dir = r"D:\syncme\modelowanie DFT\2.all_from_lumi\6.interface\2.interface\1.Co3O4_3x3\4.co3o4_3x3_ceria_mlff\2.closer\rotation"
                dir = r"D:\syncme\modelowanie DFT\2.all_from_lumi\6.interface\2.interface\4.MLFF\1.production\3.massive_search\1.3x3\1.spinel_3x3_ceria_mlff"

                # dir = "C:\\Users\\lesze\\OneDrive\\Materials Studio Projects\\interfaceCo3O4_CeO2_Files\\Documents\\interface\\Co3o4 3x3\\v4_with_mlff_ceria\\spinel_3x3_supercell CASTEP Energy"
            # print("can't resolve operating system")
            self.dir = dir
        return dir

class StructureControlsWidget(QWidget):
    def __init__(self, structure_plot, parent=None):
        super().__init__()
        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(self.exec_dir, 'icons')
        self.structure_plot_widget = structure_plot
        self.vlayout = QVBoxLayout(self)
        self.vlayout.setAlignment(Qt.AlignTop)

        self.geometry_slider = QtWidgets.QSlider()
        self.geometry_slider.setOrientation(Qt.Horizontal)
        self.geometry_slider.setMinimum(0)
        self.geometry_slider.setMaximum(len(self.structure_plot_widget.data.outcar_coordinates) - 1)
        self.geometry_slider.setValue(0)
        self.geometry_slider.setTickInterval(1)
        self.geometry_slider.setSingleStep(1)

        self.geometry_slider.valueChanged.connect(lambda: self.add_sphere(initialize=False))
        self.geometry_slider.valueChanged.connect(self.update_geometry_value_label)
        self.geometry_slider.valueChanged.connect(self.update_scatter)
        #self.geometry_slider.valueChanged.connect(self.add_bonds)

        self.geometry_value_label = QtWidgets.QLabel()
        self.geometry_value_label.setText(f"Geometry: {self.geometry_slider.value()}")

        self.end_geometry_button = QtWidgets.QPushButton()
        self.end_geometry_button.setIcon(QIcon(os.path.join(self.icon_path, "end.png")))
        self.end_geometry_button.setFixedWidth(30)
        self.start_geometry_button = QtWidgets.QPushButton()
        self.start_geometry_button.setIcon(QIcon(os.path.join(self.icon_path, "start.png")))
        self.start_geometry_button.setFixedWidth(30)
        self.next_geometry_button = QtWidgets.QPushButton()
        self.next_geometry_button.setIcon(QIcon(os.path.join(self.icon_path, "next.png")))
        self.next_geometry_button.setFixedWidth(30)
        self.back_geometry_button = QtWidgets.QPushButton()
        self.back_geometry_button.setIcon(QIcon(os.path.join(self.icon_path, "back.png")))
        self.back_geometry_button.setFixedWidth(30)

        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.addWidget(self.geometry_slider)
        slider_layout.addWidget(self.geometry_value_label)
        slider_layout.addWidget(self.start_geometry_button)
        slider_layout.addWidget(self.back_geometry_button)
        slider_layout.addWidget(self.next_geometry_button)
        slider_layout.addWidget(self.end_geometry_button)
        slider_layout.setAlignment(QtCore.Qt.AlignLeft)

        self.start_geometry_button.clicked.connect(self.start_geometry)
        self.back_geometry_button.clicked.connect(self.back_geometry)
        self.next_geometry_button.clicked.connect(self.next_geometry)
        self.end_geometry_button.clicked.connect(self.end_geometry)


        self.geometry_frame = QGroupBox(self)
        self.geometry_frame.setTitle("Geometry")
        self.geometry_frame_layout = QVBoxLayout(self.geometry_frame)


        self.geometry_frame_layout.addLayout(slider_layout)
        self.vlayout.addWidget(self.geometry_frame)

        self.energy_plot_frame = QGroupBox(self)
        self.energy_plot_frame.setTitle("Energy plot")
        self.energy_plot_frame_layout = QVBoxLayout(self.energy_plot_frame)
        self.energy_plot_layout()

        self.sphere_radius = 1
        self.bond_threshold = 2.45
        self.plotter = self.structure_plot_widget.plotter

        self.bond_actor = self.structure_plot_widget.bond_actors

        self.add_sphere()


    def end_geometry(self):
        last = len(self.structure_plot_widget.data.outcar_coordinates)
        self.geometry_slider.setValue(last)

    def start_geometry(self):
        self.geometry_slider.setValue(0)

    def back_geometry(self):
        value = self.geometry_slider.value()
        value -= 1
        self.geometry_slider.setValue(value)

    def next_geometry(self):
        value = self.geometry_slider.value()
        value += 1
        self.geometry_slider.setValue(value)

    def update_geometry_value_label(self):
        """updates the label indicating current geometry number"""
        self.geometry_value_label.setText(f'geometry number: {self.geometry_slider.value()}')

    def add_sphere(self, initialize=False):
        """adds atoms from single geometry step as spheres to renderer.
         Using VTK code because it is 100x faster than pyvista
         """

        for actor in self.structure_plot_widget.sphere_actors:
            self.plotter.renderer.RemoveActor(actor)
        self.structure_plot_widget.sphere_actors = []
        cell = np.array(self.structure_plot_widget.data.unit_cell_vectors)
        if self.structure_plot_widget.data.xdatcar_file:
            init_coords = [cell@ np.array(lst[1:]) for lst in self.structure_plot_widget.data.outcar_coordinates[0]]
            coords_to_change = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]
            for c in coords_to_change:
                idx = int(c[0])
                init_coords[idx-1] = np.array(self.structure_plot_widget.data.unit_cell_vectors).T @ np.array(c[1:])
        else:
            init_coords = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]
        coordinates = init_coords
        self.structure_plot_widget.assign_missing_colors()
        for idx, (coord, col) in enumerate(zip(coordinates, self.structure_plot_widget.atom_colors)):
            actor, source = self._create_vtk_sphere(coord, col)
            actor.SetObjectName(str(idx))
            self.plotter.renderer.AddActor(actor)
            self.structure_plot_widget.sphere_actors.append(actor)
        for actor in self.structure_plot_widget.sphere_actors:
            actor.SetVisibility(True)

        if not initialize:
            actors = self.structure_plot_widget.sphere_actors
            colors = vtkNamedColors()
            self.selected_actors = []
            try:
                selected_rows = self.parent.structure_variable_control_tab.tableWidget.selectionModel().selectedRows()
                if not selected_rows:
                    return

                selected_rows_indexes = set()
                for item in selected_rows:
                    selected_rows_indexes.add(item.row())
                for row in selected_rows_indexes:
                    if 0 <= row < len(actors):
                        actors[row].GetProperty().SetColor(colors.GetColor3d('Yellow'))
                        self.selected_actors.append(actors[row])
            except:
                pass

    def _create_vtk_sphere(self, coord, col, theta_resolution=20, phi_resolution=20):
        # Create a sphere
        sphere_source = vtkSphereSource()
        sphere_source.SetRadius(self.sphere_radius)
        sphere_source.SetCenter(coord[0], coord[1], coord[2])
        sphere_source.SetThetaResolution(theta_resolution)
        sphere_source.SetPhiResolution(phi_resolution)
        sphere_source.Update()

        # Create a mapper
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(sphere_source.GetOutputPort())

        # Create an actor
        actor = vtkActor()
        actor.SetMapper(mapper)
        col = list(np.array(col) / np.array([255, 255, 255]))

        prop = actor.GetProperty()
        prop.SetColor(col)
        prop.SetInterpolationToPhong()  # Smooth shading

        # actor.GetProperty().SetColor(*color)
        prop.SetSpecular(0.33)
        prop.SetSpecularPower(14)
        prop.SetAmbient(0.37)
        prop.SetDiffuse(0.64)
        prop.SetInterpolationToPhong()

        # Optional: disable rendering until ready
        actor.VisibilityOff()  # Equivalent to render=False in PyVista
        return actor, sphere_source

    def add_bonds(self):
        """
        render bonds as lines. First calculate all pairs, which distance is less than threshold,
        and then uses vtkLine to create a bond. For unknown reason, function doesn't work with
        connect signal when self.bond_threshold is passed as argument, so it has to be implemen-
        ted in this module. So does all functions which depend on slider/checkbox variables
        """
        bond_threshold = self.bond_threshold
        geometry_slider_value = self.geometry_slider.value()
        coord_pairs = []
        if len(self.structure_plot_widget.data.outcar_coordinates) == 1:
            coordinates = self.structure_plot_widget.data.outcar_coordinates[geometry_slider_value]
        else:
            coordinates = self.structure_plot_widget.data.outcar_coordinates[geometry_slider_value]
        if self.structure_plot_widget.bond_actors is not None:
            for actor in self.structure_plot_widget.bond_actors:
                self.structure_plot_widget.plotter.renderer.RemoveActor(actor)

        self.structure_plot_widget.bond_actors = []
        self.structure_plot_widget.coord_pairs = []

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

                self.structure_plot_widget.plotter.renderer.AddActor(actor)
                self.structure_plot_widget.bond_actors.append(actor)

    def energy_plot_layout(self):
        self.energy_plot_widget = pg.PlotWidget()
        self.energy_plot_widget.setTitle("")
        self.add_scatter_plot()
        self.update_scatter()

        self.add_line_plot()

        self.energy_plot_frame_layout.addWidget(self.energy_plot_widget)
        self.vlayout.addWidget(self.energy_plot_frame)

    def clear_energy_plot(self):
        for item in self.energy_plot_widget.getPlotItem().listDataItems():
            self.energy_plot_widget.removeItem(item)

    def add_line_plot(self):
        try:
            self.energy_plot_widget.removeItem(self.line_plot)
        except:
            pass
        y = self.structure_plot_widget.data.outcar_energies
        x = list(range(len(y)))
        self.line_plot = self.energy_plot_widget.plot(x, y)

    def add_scatter_plot(self):
        """
        Plot scatter with geometry optimization energies.
        When point is clicked, it shows the window with SCF energy convergence plot
        """
        y = self.structure_plot_widget.data.outcar_energies
        x = list(range(len(y)))
        s1 = pg.ScatterPlotItem(
            size=10,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(255, 255, 255, 0),
            hoverable=True,
            hoverSymbol='s',
            hoverSize=10,
            hoverPen=pg.mkPen('r', width=2),
            hoverBrush=pg.mkBrush('g')
        )
        s1.addPoints(x, y)
        self.energy_plot_widget.addItem(s1)

    def update_scatter(self):
        """
        Updates scatter plot regarding geometry optimization step
        """
        for item in self.energy_plot_widget.getPlotItem().listDataItems():
            if isinstance(item, MoveableScatterPlotItem):
                self.energy_plot_widget.getPlotItem().removeItem(item)
        y = self.structure_plot_widget.data.outcar_energies
        x = list(range(len(y)))
        current_x = x[self.geometry_slider.value()]
        current_y = y[self.geometry_slider.value()]

        brush = pg.mkBrush("#979797")
        self.moveable_scatter_plot_item = (
            MoveableScatterPlotItem(size=10,
                                    pen=pg.mkPen(None),
                                    brush=brush)
        )
        self.moveable_scatter_plot_item.addPoints([current_x], [current_y])
        self.energy_plot_widget.addItem(self.moveable_scatter_plot_item)


class MoveableScatterPlotItem(pg.ScatterPlotItem):
    """
    A Class for scatter plots which points can move.
    Used to check instances and clear only moveable points
    """
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)


if __name__ == '__main__':
    tic = time.perf_counter()
    app = QApplication(sys.argv)

    os.chdir("/net/scratch/hscra/plgrid/plglnowakowski/3.LUMI/6.interface/2.interface/4.MLFF/1.production/3.massive_search/1.3x3/1.spinel_3x3_ceria_mlff/1.MLFF/2.good/")

    window = MainWindow()




    toc = time.perf_counter()
    print(f'Execution time: {toc - tic:0.4f} seconds')

    window.show()
    sys.exit(app.exec_())