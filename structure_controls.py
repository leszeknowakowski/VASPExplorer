import time

tic = time.perf_counter()
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QFrame, QWidget, QVBoxLayout, QLabel, \
    QHBoxLayout,QApplication, QSizePolicy
from PyQt5.QtGui import QIcon, QCursor

from scipy.spatial.distance import pdist, squareform

from RangeSlider import QRangeSlider
from vtk import vtkNamedColors, vtkPlaneSource, vtkActor, vtkLineSource, vtkSphereSource, \
    vtkPoints, vtkCellArray, vtkLine, vtkPolyData, vtkPolyDataMapper, vtkArrowSource, \
vtkTransformPolyDataFilter, vtkTransform
from vtkmodules.vtkCommonCore import (
    vtkMath,
    vtkMinimalStandardRandomSequence
)
from vtkmodules.vtkCommonMath import vtkMatrix4x4
import os
toc = time.perf_counter()
print(f'importing in structure controls, time: {toc - tic:0.4f} seconds')

def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()  # Record the start time
        result = func(*args, **kwargs)  # Call the original function
        end_time = time.time()  # Record the end time
        execution_time = end_time - start_time
        print(f"Function '{func.__name__}' executed in {execution_time:.4f} seconds.")
        return result  # Return the original function's result
    return wrapper

class StructureControlsWidget(QWidget):
    """
        A widget for managing and interacting with 3D structures within a PyQt5 and PyVista application.
        This class provides controls for selecting, toggling, and adjusting structural elements
        like atoms, bonds, and planes, along with managing display and interaction properties.
    """
    selected_actors_changed = QtCore.pyqtSignal(list)

    def __init__(self, structure_plot_widget, parent=None):
        super().__init__()
        self.parent = parent
        self.structure_plot_widget = structure_plot_widget
        self.plotter = self.structure_plot_widget.plotter
        self.constrain_actor = self.structure_plot_widget.constrain_actor
        self.bond_actor = self.structure_plot_widget.bond_actors

        self.plotter.enable_rectangle_picking(show_frustum=False, callback=self.on_selection)
        self.plotter.add_key_event(key='r', callback=self.shift_event)

        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(self.exec_dir, 'icons')

        self.vlayout = None
        self.mag_actor = None
        self.plane_height_range_slider = None
        self.geometry_value_label = None
        self.geometry_slider = None
        self.constrains_all_cb = None
        self.constrains_between_planes_cb = None
        self.mag_cb = None
        self.bond_threshold_label = None
        self.bond_threshold_slider = None
        self.sphere_radius_label = None
        self.sphere_radius_slider = None
        self.planes_frame_layout = None
        self.planes_frame = None
        self.geometry_frame_layout = None
        self.geometry_frame = None
        self.render_frame_layout = None
        self.renderFrame = None
        self.bond_threshold = 2.8
        self.sphere_radius = 0.5
        self.constrains = self.structure_plot_widget.data.constrains
        self.selected_actors = []

        self.shift_pressed = False

        self.initUI()
        self.render_structure_control_widget()
        self.text_control_widget()
        self.structure_slider_widget()
        self.planes_layout()
        self.energy_plot_layout()
        self.bond_length_actors = []
        self.forces_actors = []

        self.add_bonds()
        self.add_sphere()

    def update_data(self):
        self.geometry_slider.setMaximum(len(self.structure_plot_widget.data.outcar_coordinates) - 1)
        self.geometry_slider.setValue(0)
        self.geometry_value_label.setText(f"Geometry number: {self.geometry_slider.value()}")

        self.add_bonds()
        self.add_sphere()

        self.clear_energy_plot()
        self.add_line_plot()
        self.add_scatter_plot()
        self.update_scatter()

    def initUI(self):
        self.vlayout = QVBoxLayout(self)
        # self.setLayout(self.vlayout)
        self.vlayout.setAlignment(QtCore.Qt.AlignTop)

        self.renderFrame = QFrame(self)
        self.renderFrame.setFrameShape(QFrame.Panel)
        self.renderFrame.setFrameShadow(QFrame.Raised)
        #self.renderFrame.setStyleSheet("background-color: #1e1f22; color: #cbcdd2;")
        self.renderFrame.setLineWidth(10)

        self.render_frame_layout = QVBoxLayout(self.renderFrame)

        self.geometry_frame = QFrame(self)
        self.geometry_frame.setFrameShape(QFrame.Panel)
        self.geometry_frame.setFrameShadow(QFrame.Raised)
        #self.geometry_frame.setStyleSheet("background-color: #1e1f22;color: #cbcdd2;")
        self.geometry_frame.setLineWidth(10)

        self.geometry_frame_layout = QVBoxLayout(self.geometry_frame)

        self.planes_frame = QFrame(self)
        self.planes_frame.setFrameShape(QFrame.Panel)
        self.planes_frame.setFrameShadow(QFrame.Raised)
        #self.planes_frame.setStyleSheet("background-color: #1e1f22;color: #cbcdd2;")
        self.planes_frame.setLineWidth(10)

        self.planes_frame_layout = QVBoxLayout(self.planes_frame)

        self.energy_plot_frame = QFrame(self)
        self.energy_plot_frame.setFrameShape(QFrame.Panel)
        self.energy_plot_frame.setFrameShadow(QFrame.Raised)
        #self.energy_plot_frame.setStyleSheet("background-color: #1e1f22; color: #cbcdd2;")
        self.energy_plot_frame.setLineWidth(10)
        self.energy_plot_frame_layout = QVBoxLayout(self.energy_plot_frame)

    def render_structure_control_widget(self):
        """ structure  visibility checkbox widget. Control wheater to plot or not the spheres, bonds, unit cell"""
        # ############# spheres part ###########################
        self.sphere_cb = QtWidgets.QCheckBox()
        self.sphere_cb.setChecked(True)
        self.sphere_cb.setText("Show/hide all spheres")
        self.sphere_cb.stateChanged.connect(self.toggle_spheres)

        self.sphere_selected_cb = QtWidgets.QCheckBox()
        self.sphere_selected_cb.setText("Show/hide spheres between planes")
        self.sphere_selected_cb.stateChanged.connect(self.toggle_spheres_between_planes)
        self.sphere_selected_cb.setChecked(False)

        self.sphere_radius_slider = QtWidgets.QSlider()
        self.sphere_radius_slider.setOrientation(QtCore.Qt.Horizontal)
        self.sphere_radius_slider.setMinimum(0)
        self.sphere_radius_slider.setMaximum(10)
        self.sphere_radius_slider.setValue(5)
        self.sphere_radius_slider.setFixedWidth(200)


        self.sphere_radius_label = QLabel()
        self.sphere_radius_label.setText(f"Sphere Radius: {self.sphere_radius_slider.value()/10}")

        self.sphere_radius_slider.valueChanged.connect(self.change_sphere_radius)
        self.sphere_radius_slider.valueChanged.connect(self.change_sphere_radius_label)
        self.sphere_radius_slider.valueChanged.connect(self.add_sphere)

        sphere_layout = QHBoxLayout()
        sphere_layout.setSpacing(10)
        sphere_layout.addWidget(self.sphere_cb)
        sphere_layout.addWidget(self.sphere_selected_cb)
        sphere_layout.addWidget(self.sphere_radius_label)
        sphere_layout.addWidget(self.sphere_radius_slider, stretch=4)
        sphere_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.render_frame_layout.addLayout(sphere_layout)

        # ############### bonds part #########################
        self.bonds_cb = QtWidgets.QCheckBox()
        self.bonds_cb.setChecked(True)
        self.bonds_cb.setText("bonds")
        self.bonds_cb.stateChanged.connect(self.toggle_bonds)

        self.bond_threshold_slider = QtWidgets.QSlider()
        self.bond_threshold_slider.setOrientation(QtCore.Qt.Horizontal)
        self.bond_threshold_slider.setMinimum(100)
        self.bond_threshold_slider.setMaximum(400)
        self.bond_threshold_slider.setValue(300)
        self.bond_threshold_slider.setTickInterval(100)
        self.bond_threshold_slider.setFixedWidth(200)

        self.bond_threshold_label = QtWidgets.QLabel()
        self.update_bond_threshold_label()

        self.bond_threshold_slider.valueChanged.connect(self.set_bond_threshold)
        self.bond_threshold_slider.valueChanged.connect(self.add_bonds)
        self.bond_threshold_slider.valueChanged.connect(self.update_bond_threshold_label)

        bond_layaout = QHBoxLayout()
        bond_layaout.addWidget(self.bonds_cb)
        bond_layaout.addWidget(self.bond_threshold_label)
        bond_layaout.addWidget(self.bond_threshold_slider)
        self.render_frame_layout.addLayout(bond_layaout)

        # ############ unit cell part #####################
        unit_cell_cb = QtWidgets.QCheckBox()
        unit_cell_cb.setChecked(True)
        unit_cell_cb.setText('unit cell')
        unit_cell_cb.stateChanged.connect(self.toggle_unit_cell)
        self.render_frame_layout.addWidget(unit_cell_cb)

        # ############### forces ########################
        self.forces_cb = QtWidgets.QCheckBox()
        self.forces_cb.setChecked(False)
        self.forces_cb.setText('forces')
        self.forces_cb.stateChanged.connect(self.toggle_forces)
        self.render_frame_layout.addWidget(self.forces_cb)

    def text_control_widget(self):
        """ widgets connected to rendering text on 3d structure, such as numbers of atom, constrains """
        self.numbers_cb = QtWidgets.QCheckBox()
        self.numbers_cb.setChecked(False)
        self.numbers_cb.setText('numbers')
        self.numbers_cb.stateChanged.connect(self.toggle_symbols)
        self.render_frame_layout.addWidget(self.numbers_cb)

        self.numbers_between_planes_cb = QtWidgets.QCheckBox()
        self.numbers_between_planes_cb.setChecked(False)
        self.numbers_between_planes_cb.setText('numbers between planes')
        self.numbers_between_planes_cb.stateChanged.connect(self.toggle_symbols_between_planes)
        self.render_frame_layout.addWidget(self.numbers_between_planes_cb)

        self.mag_cb = QtWidgets.QCheckBox()
        self.mag_cb.setChecked(False)
        self.mag_cb.setText('magnetization between planes')
        self.mag_cb.stateChanged.connect(self.toggle_mag_above_plane)
        self.render_frame_layout.addWidget(self.mag_cb)

        self.constrains_between_planes_cb = QtWidgets.QCheckBox()
        self.constrains_between_planes_cb.setChecked(False)
        self.constrains_between_planes_cb.setText('show constrains')

        self.constrains_all_cb = QtWidgets.QCheckBox()
        self.constrains_all_cb.setChecked(False)
        self.constrains_all_cb.setText('show all constrains')

        constrain_layout = QtWidgets.QHBoxLayout()
        constrain_layout.addWidget(self.constrains_between_planes_cb)
        constrain_layout.addWidget(self.constrains_all_cb)
        constrain_layout.setAlignment(QtCore.Qt.AlignLeft)
        self.render_frame_layout.addLayout(constrain_layout)

        self.constrains_between_planes_cb.stateChanged.connect(self.toggle_constrain_above_plane)
        self.constrains_all_cb.stateChanged.connect(self.toggle_all_constrains)

        self.vlayout.addWidget(self.renderFrame)

    def structure_slider_widget(self):
        """ widget to control current structure rendering """
        self.geometry_slider = QtWidgets.QSlider()
        self.geometry_slider.setOrientation(QtCore.Qt.Horizontal)
        self.geometry_slider.setMinimum(0)
        self.geometry_slider.setMaximum(len(self.structure_plot_widget.data.outcar_coordinates) - 1)
        self.geometry_slider.setValue(0)
        self.geometry_slider.setTickInterval(1)
        self.geometry_slider.setSingleStep(1)
        self.geometry_slider.setFixedWidth(200)

        self.geometry_slider.valueChanged.connect(self.add_sphere)
        self.geometry_slider.valueChanged.connect(self.update_geometry_value_label)
        self.geometry_slider.valueChanged.connect(self.add_bonds)
        self.geometry_slider.valueChanged.connect(self.toggle_symbols)
        self.geometry_slider.valueChanged.connect(self.toggle_mag_above_plane)
        self.geometry_slider.valueChanged.connect(self.toggle_constrain_above_plane)
        self.geometry_slider.valueChanged.connect(self.toggle_all_constrains)
        self.geometry_slider.valueChanged.connect(self.toggle_symbols_between_planes)
        self.geometry_slider.valueChanged.connect(self.update_scatter)
        self.geometry_slider.valueChanged.connect(self.create_forces_arrows)

        self.geometry_value_label = QtWidgets.QLabel()
        self.geometry_value_label.setText(f"Geometry number: {self.geometry_slider.value()}")
        self.geometry_value_label.setFixedWidth(150)

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

        self.geometry_frame_layout.addLayout(slider_layout)
        self.vlayout.addWidget(self.geometry_frame)

    def planes_layout(self):
        """widgets to control cutoff planes posistion and color"""
        top_plane_cb = QtWidgets.QCheckBox()
        top_plane_cb.setChecked(False)
        top_plane_cb.setText('top plane')

        top_plane_cb.stateChanged.connect(self.toggle_plane_heigher)

        bottom_plane_cb = QtWidgets.QCheckBox()
        bottom_plane_cb.setChecked(True)
        bottom_plane_cb.setText('bottom plane')

        bottom_plane_cb.stateChanged.connect(self.toggle_plane)
        z = self.structure_plot_widget.data.z

        # setRange -> aktualny, teraźniejszy zares slidera
        # setMin, setMax - maksymalna wartość slidera (granice)
        self.plane_height_range_slider = QRangeSlider()
        self.plane_height_range_slider.show()
        self.plane_height_range_slider.setMin(-1)
        self.plane_height_range_slider.setMax(100)
        self.plane_height_range_slider.setRange(38,90)


        self.plane_height_range_slider.handle.setTextColor((218,224,218))

        self.plane_height_range_slider.startValueChanged.connect(self.toggle_mag_above_plane)
        self.plane_height_range_slider.startValueChanged.connect(self.all_planes_position)
        self.plane_height_range_slider.startValueChanged.connect(self.toggle_constrain_above_plane)
        self.plane_height_range_slider.startValueChanged.connect(self.toggle_symbols_between_planes)

        self.plane_height_range_slider.endValueChanged.connect(self.toggle_mag_above_plane)
        self.plane_height_range_slider.endValueChanged.connect(self.all_planes_position)
        self.plane_height_range_slider.endValueChanged.connect(self.toggle_constrain_above_plane)
        self.plane_height_range_slider.endValueChanged.connect(self.toggle_symbols_between_planes)

        self.add_plane(self.plane_height_range_slider.getRange()[0])
        self.add_plane_higher(self.plane_height_range_slider.getRange()[1])
        self.structure_plot_widget.plane_actor_heigher.GetProperty().SetOpacity(0)

        plane_color_label = QtWidgets.QLabel("planes color:")

        self.plane_color_button = pg.ColorButton()
        self.plane_color_button.setColor(np.array([0.890, 0.8119, 0.341])*255)
        self.plane_color_button.sigColorChanging.connect(self.change_plane_color)

        planes_layout = QtWidgets.QHBoxLayout()
        planes_layout.addWidget(top_plane_cb)
        planes_layout.addWidget(bottom_plane_cb)
        planes_layout.addWidget(self.plane_height_range_slider)
        planes_layout.addWidget(plane_color_label)
        planes_layout.addWidget(self.plane_color_button)

        self.planes_frame_layout.addLayout(planes_layout)
        self.vlayout.addWidget(self.planes_frame)

    def energy_plot_layout(self):
        self.energy_plot_widget = pg.PlotWidget()
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
        s1.sigClicked.connect(self.clicked_scatter_plot)
        self.energy_plot_widget.addItem(s1)

    def clicked_scatter_plot(self, plot, points):
        """
        Show scatter plot with energy optimization plot for certain geometry step.
        For unknown reason signal is not send when first point is clicked.
        """
        print("clicked points", points)
        if len(points) > 1:
            print("oopsie, to many points clicked. Please click only one point")
            return
        else:
            screen_rect = QApplication.primaryScreen().geometry()
            pos = QCursor.pos()
            energies = self.structure_plot_widget.data.scf_energies[points[0]._index]
            x = range(len(energies))
            self.scf_window =  SCFEnergyPlot(x, energies, pos, screen_rect)
            self.scf_window.show()

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

        s1 = MoveableScatterPlotItem(size=10, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 120))
        s1.addPoints([current_x], [current_y])
        self.energy_plot_widget.addItem(s1)

    def toggle_spheres(self, flag):
        """switches on and off spheres visibility"""
        for actor in self.structure_plot_widget.sphere_actors:
            if self.selected_actors == []:
                actor.SetVisibility(flag)
            elif actor in self.selected_actors:
                actor.SetVisibility(flag)

    def toggle_spheres_between_planes(self, flag):
        if self.sphere_selected_cb.isChecked():
            for actor in self.structure_plot_widget.sphere_actors:
                actor.SetVisibility(0)

            indices, coordinates = self.find_indices_between_planes()
            #for i in range(len(indices)):
            #    self.structure_plot_widget.sphere_actors[i].SetVisibility(flag)
            for i, actor in enumerate(self.structure_plot_widget.sphere_actors):
                center = actor.GetCenter()
                for coord in coordinates:
                    if (np.round(np.array(center), 2) == np.round(np.array(coord), 2)).all():
                        actor.SetVisibility(flag)
        else:
            for actor in self.structure_plot_widget.sphere_actors:
                actor.SetVisibility(1)

    def toggle_bonds_between_planes(self, flag):
        for actor in self.structure_plot_widget.bond_actors:
            actor.SetVisibility(flag)

    def change_sphere_radius(self, value):
        self.sphere_radius = value / 10

    def change_sphere_radius_label(self):
        self.sphere_radius_label.setText(f"Sphere radius: {self.sphere_radius}")

    def add_sphere(self):
        """adds atoms from single geometry step as spheres to renderer.
         Using VTK code because it is 100x faster than pyvista
         """
        for actor in self.structure_plot_widget.sphere_actors:
            self.plotter.renderer.RemoveActor(actor)
        self.structure_plot_widget.sphere_actors = []
        coordinates = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]

        for coord, col in zip(coordinates, self.structure_plot_widget.atom_colors):
            actor =  self._create_vtk_sphere(coord, col)
            self.plotter.renderer.AddActor(actor)
            self.structure_plot_widget.sphere_actors.append(actor)
        for actor in self.structure_plot_widget.sphere_actors:
            actor.SetVisibility(True)

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
        col = list(np.array(col)/np.array([255,255,255]))

        prop = actor.GetProperty()
        prop.SetColor(col)
        prop.SetInterpolationToPhong()  # Smooth shading

        #actor.GetProperty().SetColor(*color)
        prop.SetSpecular(0.33)
        prop.SetSpecularPower(14)
        prop.SetAmbient(0.37)
        prop.SetDiffuse(0.64)
        prop.SetInterpolationToPhong()

        # Optional: disable rendering until ready
        actor.VisibilityOff()  # Equivalent to render=False in PyVista
        return actor

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

    def toggle_unit_cell(self, flag):
        """ switches on and off unit cell visibility"""
        self.structure_plot_widget.cube_actor.SetVisibility(flag)

    def add_plane(self, value):
        self.planeSource = vtkPlaneSource()
        self.structure_plot_widget.plane_actor = vtkActor()
        self._add_plane(self.planeSource, self.structure_plot_widget.plane_actor, value)

    def add_plane_higher(self, value):
        """renders a plane perpendicular to XY plane at value height"""

        self.planeSource_heigher = vtkPlaneSource()
        self.structure_plot_widget.plane_actor_heigher = vtkActor()
        self._add_plane(self.planeSource_heigher, self.structure_plot_widget.plane_actor_heigher, value)

    def _add_plane(self, source, actor, value):
        """renders a plane perpendicular to XY plane at value height"""
        if actor is not None:
            self.structure_plot_widget.plotter.remove_actor(actor)
        z = self.structure_plot_widget.data.z
        colors = vtkNamedColors()
        colors.SetColor('BkgColor', [26, 51, 77, 255])

        source.SetNormal(0.0, 0.0, 1.0)
        source.SetOrigin(-5, -5, z / 100 * value)
        source.SetPoint1(self.structure_plot_widget.data.x + 5, -5, z / 100 * value)
        source.SetPoint2(-5, self.structure_plot_widget.data.y + 5, z / 100 * value)
        source.Update()
        plane = source.GetOutput()

        # Create a mapper and actor
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(plane)

        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(colors.GetColor3d('White'))
        actor.GetProperty().SetAmbient(100)
        #  self.plane_actor_heigher.GetProperty().SetOpacity()

        self.structure_plot_widget.plotter.renderer.AddActor(actor)

    def all_planes_position(self):
        val = self.plane_height_range_slider.getRange()
        startVal = val[0]
        endVal = val[1]
        z = self.structure_plot_widget.data.z
        #self.plane_position = startVal
        self.planeSource.SetOrigin(-5, -5, z / 100 * startVal)
        self.planeSource.SetPoint1(self.structure_plot_widget.data.x + 5, -5, z / 100 * startVal)
        self.planeSource.SetPoint2(-5, self.structure_plot_widget.data.y + 5, z / 100 * startVal)
        self.planeSource.Update()

        self.planeSource_heigher.SetOrigin(-5, -5, z / 100 * endVal)
        self.planeSource_heigher.SetPoint1(self.structure_plot_widget.data.x + 5, -5, z / 100 * endVal)
        self.planeSource_heigher.SetPoint2(-5, self.structure_plot_widget.data.y + 5, z / 100 * endVal)
        self.planeSource_heigher.Update()

        self.structure_plot_widget.plotter.renderer.Render()

    def change_plane_color(self):
        color = self.plane_color_button.color()
        r = color.red()/255
        g = color.green()/255
        b = color.blue()/255
        self.structure_plot_widget.plane_actor.GetProperty().SetColor((r,g,b))
        self.structure_plot_widget.plane_actor_heigher.GetProperty().SetColor((r,g,b))

    def toggle_plane(self, flag):
        """ switches on and off plane visibility"""
        self.structure_plot_widget.plane_actor.GetProperty().SetOpacity(flag)

    def toggle_plane_heigher(self, flag):
        """ switches on and off plane visibility"""
        self.structure_plot_widget.plane_actor_heigher.GetProperty().SetOpacity(flag)

    def toggle_all_constrains(self, flag):
        """ switches on and off constrains visibility"""
        if self.constrains_all_cb.isChecked():
            self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.constrain_actor)
            coords = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()])
            constr = [constr[0] for constr in self.structure_plot_widget.data.all_constrains]
            self.structure_plot_widget.constrain_actor = self.plotter.add_point_labels(coords, constr, font_size=30,
                                                                                       show_points=False,
                                                                                       always_visible=True, shape=None)
        if self.structure_plot_widget.constrain_actor is not None:
            self.structure_plot_widget.constrain_actor.SetVisibility(flag)

    def toggle_constrain_above_plane(self, flag):
        self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.constrain_actor)
        if self.constrains_between_planes_cb.isChecked():
            indices, coordinates = self.find_indices_between_planes()
            coords = []
            constr = []
            for i in range(len(indices)):
                coords.append(list(coordinates[indices[i]]))
                constr.append(self.structure_plot_widget.data.all_constrains[indices[i]][0])
            self.structure_plot_widget.constrain_actor = self.plotter.add_point_labels(coords, constr, font_size=30,
                                                                 show_points=False, always_visible=True, shape=None)
            self.structure_plot_widget.constrain_actor.SetVisibility(flag)

    def toggle_mag_above_plane(self, flag):
        self.plotter.renderer.RemoveActor(self.mag_actor)
        if self.mag_cb.isChecked():
            #self.end_geometry()
            indices, coordinates = self.find_indices_between_planes()
            coords = []
            magnet = []
            mag = self.structure_plot_widget.data.outcar_data.magnetizations[self.geometry_slider.value()]
            for i in range(len(indices)):
                coords.append(list(coordinates[indices[i]]))
                magnet.append(mag[indices[i]])
            self.mag_actor = self.plotter.add_point_labels(coords, magnet, font_size=30,
                                                           show_points=False, always_visible=True, shape=None)
            self.mag_actor.SetVisibility(flag)

    def toggle_symbols(self, flag):
        """ switches on and off symbols and numbers visibility"""
        self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.symb_actor)
        if self.numbers_cb.isChecked():
            symbols = self.structure_plot_widget.data.atoms_symb_and_num
            coords = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()])
            self.structure_plot_widget.symb_actor = self.plotter.add_point_labels(coords, symbols, font_size=30,
                                                                                  show_points=False, always_visible=True,
                                                                                  shape=None)
            self.structure_plot_widget.symb_actor.SetVisibility(flag)

    def find_indices_between_planes(self):
        slidervalue = self.plane_height_range_slider.getRange()
        height = slidervalue[0] / 100 * self.structure_plot_widget.data.z
        end = slidervalue[1] / 100 * self.structure_plot_widget.data.z
        indices = []
        global_coordinates = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()])
        if self.selected_actors != []:
            coordinates = []
            for actor in self.selected_actors:
                center = actor.GetCenter()
                coordinates.append(list(center))
            coordinates = np.array(coordinates)
            for center in coordinates:
                for index, coord in enumerate(np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()])):
                    if (np.round(center, 2) == np.round(coord, 2)).all():
                        indices.append(index)
        else:

            indice = np.where((global_coordinates[:, 2] > height) & (global_coordinates[:, 2] < end))[0]
            indices = indice.tolist()
        return indices, global_coordinates

    def toggle_symbols_between_planes(self, flag):
        self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.symb_actor)
        if self.numbers_between_planes_cb.isChecked():
            coords = []
            symb = []
            indices, coordinates = self.find_indices_between_planes()
            for i in range(len(indices)):
                coords.append(list(coordinates[indices[i]]))
                symb.append(self.structure_plot_widget.data.atoms_symb_and_num[indices[i]])
            self.structure_plot_widget.symb_actor = self.plotter.add_point_labels(coords, symb, font_size=30,
                                                                 show_points=False, always_visible=True, shape=None)
            self.structure_plot_widget.symb_actor.SetVisibility(flag)

    def add_symbol_and_number(self):
        """ renders an atom symbol and number"""
        self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.symb_actor)
        coordinates = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]
        symb_num = self.structure_plot_widget.data.atoms_symb_and_num
        coords = list(np.array(coordinates) + [0, -0.2, 0.5])
        self.structure_plot_widget.symb_actor = self.structure_plot_widget.plotter.add_point_labels(coords, symb_num,
                                    font_size=30, show_points=False, always_visible=False, shape=None)
        self.structure_plot_widget.symb_actor.SetVisibility(False)

    def toggle_bonds(self, flag):
        for actor in self.structure_plot_widget.bond_actors:
            actor.SetVisibility(flag)


    def set_bond_threshold(self, value):
        """ setter of the bond_threshold_value"""
        self.bond_threshold = value / 100

    def update_bond_threshold_label(self):
        """ updates the label indicating current bond visibility value"""
        self.bond_threshold_label.setText(f'bond visibility: {self.bond_threshold_slider.value() / 100}')

    def update_sphere_radius_label(self):
        self.sphere_radius_label.setText(f'sphere radius: {self.sphere_radius_slider.value()}')

    def update_geometry_value_label(self):
        """updates the label indicating current geometry number"""
        self.geometry_value_label.setText(f'geometry number: {self.geometry_slider.value()}')

    def start_button(self):
        self.geometry_slider.setValue(0)

    def back_geometry(self):
        value = self.geometry_slider.value()
        value -= 1
        self.geometry_slider.setValue(value)

    def next_geometry(self):
        value = self.geometry_slider.value()
        value += 1
        self.geometry_slider.setValue(value)

    def end_geometry(self):
        last = len(self.structure_plot_widget.data.outcar_coordinates)
        self.geometry_slider.setValue(last)

    def get_symbols(self):
        return self.structure_plot_widget.data.atoms_symb_and_num

    def get_current_coordinates(self):
        return self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]

    def get_all_coordinates(self):
        return self.structure_plot_widget.data.outcar_coordinates

    def set_symbols(self, symbols):
        self.structure_plot_widget.data.atoms_symb_and_num = symbols

    def get_constrains(self):
        return self.structure_plot_widget.data.constrains

    def get_table_data(self):
        symb = self.structure_plot_widget.data.symbols
        if len(self.structure_plot_widget.data.outcar_coordinates) == 1:
            coord = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]
        else:
            coord = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]
        const = self.structure_plot_widget.data.all_constrains
        magmoms = self.structure_plot_widget.data.magmoms
        suffixes = self.structure_plot_widget.data.suffixes
        return symb, coord, const, magmoms, suffixes

    def update_row(self, row, atom_num_and_symb, coordinates, constraints):
        self.structure_plot_widget.data.atoms_symb_and_num[row] = atom_num_and_symb
        self.self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][row] = coordinates
        self.self.structure_plot_widget.data.constrains[row] = constraints

    def delete_row(self, row):
        import inspect
        atoms = len(self.structure_plot_widget.data.atoms_symb_and_num)
        data = self.structure_plot_widget.data
        values = [value for name, value in inspect.getmembers(data)
                  if type(value) == list and len(value) == atoms]
        properties = [name for name, value in inspect.getmembers(data)
                  if type(value) == list and len(value) == atoms]
        for value, property in zip(values, properties):
            value.pop(row)
            setattr(data, property, value)
        self.structure_plot_widget.atom_colors.pop(row)
        if hasattr(self.structure_plot_widget.data, 'outcar_data'):
            outcar_data = self.structure_plot_widget.data.outcar_data
            for mag in outcar_data.magnetizations:
                mag.pop(row)

        for geo in self.structure_plot_widget.data.outcar_coordinates:
            geo.pop(row) # delete atom from all geometries


        for actor in self.structure_plot_widget.sphere_actors:
            self.plotter.renderer.RemoveActor(actor)
        self.structure_plot_widget.sphere_actors.pop(row)

    #@timer_decorator
    def on_selection(self, RectangleSelection):
        if not self.parent.shift_pressed:
            self.selected_actors = []
            for index, actor in enumerate(self.structure_plot_widget.sphere_actors):
                actor.GetProperty().SetColor(self.structure_plot_widget.atom_colors[index])

        actors = self.structure_plot_widget.sphere_actors
        colors = vtkNamedColors()
        for index, actor in enumerate(actors):
            if actor.GetVisibility():
                is_inside = RectangleSelection.frustum.EvaluateFunction(actor.GetCenter()) < 0
                if is_inside:
                    if actor not in self.selected_actors:
                        actor.GetProperty().SetColor(colors.GetColor3d('Yellow'))
                        self.selected_actors.append(actor)


        self.selected_actors_changed.emit(self.selected_actors)

    def shift_event(self):
        if self.shift_pressed:
            self.shift_pressed = False
            self.plotter.renderer.GetRenderWindow().SetCurrentCursor(1)
        else:
            self.shift_pressed = True
            self.plotter.renderer.GetRenderWindow().SetCurrentCursor(10)

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

    def create_forces_arrows(self):
        if self.forces_actors != []:
            for actor in self.forces_actors:
                self.plotter.renderer.RemoveActor(actor)
        current_iter = self.geometry_slider.value()
        forces = self.structure_plot_widget.data.outcar_data.forces[current_iter]
        coordinates = self.structure_plot_widget.data.outcar_data.find_coordinates()[current_iter]
        self.forces_actors = []
        if self.forces_cb.isChecked():
            for i, (center, force) in enumerate(zip(coordinates, forces)):
                actor = self.create_arrow(center, force)
                self.forces_actors.append(actor)
                self.plotter.renderer.AddActor(actor)

    def toggle_forces(self, flag):
        if self.forces_actors == []:
            self.create_forces_arrows()
        else:
            for actor in self.forces_actors:
                actor.SetVisibility(flag)

    def create_arrow(self, center, vector):
        colors = vtkNamedColors()

        # Set the background color.
        colors.SetColor('BkgColor', [26, 51, 77, 255])

        # Create an arrow.
        arrowSource = vtkArrowSource()
        arrowSource.SetTipResolution(100)
        arrowSource.SetShaftResolution(100)

        # Generate a random start and end point
        startPoint = np.array(center)
        endPoint = center + np.array(vector)
        rng = vtkMinimalStandardRandomSequence()

        # Compute a basis
        normalizedX = [0] * 3
        normalizedY = [0] * 3
        normalizedZ = [0] * 3

        # The X axis is a vector from start to end
        vtkMath.Subtract(endPoint, startPoint, normalizedX)
        length = vtkMath.Norm(normalizedX)
        vtkMath.Normalize(normalizedX)

        # The Z axis is an arbitrary vector cross X
        arbitrary = [0] * 3
        for i in range(0, 3):
            rng.Next()
            arbitrary[i] = rng.GetRangeValue(-10, 10)
        vtkMath.Cross(normalizedX, arbitrary, normalizedZ)
        vtkMath.Normalize(normalizedZ)

        # The Y axis is Z cross X
        vtkMath.Cross(normalizedZ, normalizedX, normalizedY)
        matrix = vtkMatrix4x4()

        # Create the direction cosine matrix
        matrix.Identity()
        for i in range(0, 3):
            matrix.SetElement(i, 0, normalizedX[i])
            matrix.SetElement(i, 1, normalizedY[i])
            matrix.SetElement(i, 2, normalizedZ[i])

        # Apply the transforms
        transform = vtkTransform()
        transform.Translate(startPoint)
        transform.Concatenate(matrix)
        transform.Scale(length, length, length)

        # Transform the polydata
        transformPD = vtkTransformPolyDataFilter()
        transformPD.SetTransform(transform)
        transformPD.SetInputConnection(arrowSource.GetOutputPort())

        # Create a mapper and actor for the arrow
        mapper = vtkPolyDataMapper()
        actor = vtkActor()

        mapper.SetInputConnection(transformPD.GetOutputPort())
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(colors.GetColor3d('Cyan'))

        return actor

    def closeEvent(self, QCloseEvent):
        super().closeEvent(QCloseEvent)
        self.structure_plot_widget.plotter.Finalize()


class SCFEnergyPlot(QWidget):
    """Window that shows a SCF convergence plot"""
    def __init__(self, steps, energies, pos, screen_rect):
        super().__init__()
        self.setWindowTitle("Random Line Plot")
        self.resize(800, 600)  # Fixed window size

        win_width, win_height = self.width(), self.height()

        # Adjust position to keep window within screen boundaries
        x = min(pos.x(), screen_rect.right() - win_width-60)  # Prevent right overflow
        y = min(pos.y(), screen_rect.bottom() - win_height-60)  # Prevent bottom overflow

        x = max(x, screen_rect.left()-30)  # Prevent left overflow
        y = max(y, screen_rect.top()-30)  # Prevent top overflow

        self.setGeometry(x, y, 800, 600)

        layout = QVBoxLayout()
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

        self.plot_widget.plot(steps, energies, pen='w')


class MoveableScatterPlotItem(pg.ScatterPlotItem):
    """
    A Class for scatter plots which points can move.
    Used to check instances and clear only moveable points
    """
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)


