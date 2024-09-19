""" module to GUI control the structure plot"""
import time
import numpy as np
import pyqtgraph as pg

# from functools import partial

tic = time.perf_counter()
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QFrame, QWidget, QVBoxLayout, QLabel, \
    QHBoxLayout

from scipy.spatial.distance import pdist, squareform
from vtk import *
from RangeSlider import QRangeSlider
import pyvista as pv
import os
from PyQt5 import QtGui

# import vtkmodules.all as vtk
toc = time.perf_counter()
print(f'importing Pyqt from structure controls{toc - tic}')


class StructureControlsWidget(QWidget):
    selected_actors_changed = QtCore.pyqtSignal(list)
    def __init__(self, structure_plot_widget):
        super().__init__()
        self.structure_plot_widget = structure_plot_widget
        self.plotter = self.structure_plot_widget.plotter
        self.constrain_actor = self.structure_plot_widget.constrain_actor
        self.bond_actor = self.structure_plot_widget.bond_actors

        self.plotter.enable_rectangle_picking(show_frustum=False, callback=self.on_selection)

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

        self.initUI()
        self.render_structure_control_widget()
        self.text_control_widget()
        self.structure_slider_widget()
        self.planes_layout()
        self.energy_plot_layout()

        #self.add_symbol_and_number()
        self.add_bonds()
        self.add_plane(self.structure_plot_widget.data.z / 2)
        self.add_plane_higher(self.structure_plot_widget.data.z)

    def initUI(self):
        self.vlayout = QVBoxLayout(self)
        # self.setLayout(self.vlayout)
        self.vlayout.setAlignment(QtCore.Qt.AlignTop)

        self.renderFrame = QFrame(self)
        self.renderFrame.setFrameShape(QFrame.Panel)
        self.renderFrame.setFrameShadow(QFrame.Raised)
        self.renderFrame.setStyleSheet("background-color: #1e1f22; color: #cbcdd2;")
        self.renderFrame.setLineWidth(10)

        self.render_frame_layout = QVBoxLayout(self.renderFrame)

        self.geometry_frame = QFrame(self)
        self.geometry_frame.setFrameShape(QFrame.Panel)
        self.geometry_frame.setFrameShadow(QFrame.Raised)
        self.geometry_frame.setStyleSheet("background-color: #1e1f22;color: #cbcdd2;")
        self.geometry_frame.setLineWidth(10)

        self.geometry_frame_layout = QVBoxLayout(self.geometry_frame)

        self.planes_frame = QFrame(self)
        self.planes_frame.setFrameShape(QFrame.Panel)
        self.planes_frame.setFrameShadow(QFrame.Raised)
        self.planes_frame.setStyleSheet("background-color: #1e1f22;color: #cbcdd2;")
        self.planes_frame.setLineWidth(10)

        self.planes_frame_layout = QVBoxLayout(self.planes_frame)

        self.energy_plot_frame = QFrame(self)
        self.energy_plot_frame.setFrameShape(QFrame.Panel)
        self.energy_plot_frame.setFrameShadow(QFrame.Raised)
        self.energy_plot_frame.setStyleSheet("background-color: #1e1f22; color: #cbcdd2;")
        self.energy_plot_frame.setLineWidth(10)
        self.energy_plot_frame_layout = QVBoxLayout(self.energy_plot_frame)

    def render_structure_control_widget(self):
        """ structure  visibility checkbox widget. Control wheater to plot or not the spheres, bonds, unit cell"""
        # ############# spheres part ###########################
        self.sphere_cb = QtWidgets.QCheckBox()
        self.sphere_cb.setChecked(True)
        self.sphere_cb.setText("Sphere")

        self.sphere_cb.stateChanged.connect(self.toggle_spheres)

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
        sphere_layout.addWidget(self.sphere_radius_label)
        sphere_layout.addWidget(self.sphere_radius_slider)
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
        # unit_cell_cb.stateChanged.connect(self.toggle_unit_cell)
        self.render_frame_layout.addWidget(unit_cell_cb)

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
        self.mag_cb.setText('magnetization')
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
        self.geometry_slider.setMaximum(len(self.structure_plot_widget.data.outcar_coordinates) - 2)
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

        self.geometry_value_label = QtWidgets.QLabel()
        self.geometry_value_label.setText(f"Geometry number: {self.geometry_slider.value()}")
        self.geometry_value_label.setFixedWidth(150)

        self.end_geometry_button = QtWidgets.QPushButton()
        self.end_geometry_button.setIcon(QtGui.QIcon(os.path.join(self.icon_path, "end.png")))
        self.end_geometry_button.setFixedWidth(30)
        self.start_geometry_button = QtWidgets.QPushButton()
        self.start_geometry_button.setIcon(QtGui.QIcon(os.path.join(self.icon_path, "start.png")))
        self.start_geometry_button.setFixedWidth(30)
        self.next_geometry_button = QtWidgets.QPushButton()
        self.next_geometry_button.setIcon(QtGui.QIcon(os.path.join(self.icon_path, "next.png")))
        self.next_geometry_button.setFixedWidth(30)
        self.back_geometry_button = QtWidgets.QPushButton()
        self.back_geometry_button.setIcon(QtGui.QIcon(os.path.join(self.icon_path, "back.png")))
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
        top_plane_cb.setChecked(True)
        top_plane_cb.setText('top plane')

        top_plane_cb.stateChanged.connect(self.toggle_plane_heigher)

        bottom_plane_cb = QtWidgets.QCheckBox()
        bottom_plane_cb.setChecked(True)
        bottom_plane_cb.setText('bottom plane')

        bottom_plane_cb.stateChanged.connect(self.toggle_plane)

        self.plane_height_range_slider = QRangeSlider()
       # self.plane_height_range_slider.setRange(10, 99)
       # self.plane_height_range_slider.setMin(0)
       # self.plane_height_range_slider.setMax(100)
        self.plane_height_range_slider.setBackgroundStyle(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #222, stop:1 #333);')
        self.plane_height_range_slider.handle.setStyleSheet(
            'background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #858583, stop:1 #cbcbc9);')
        self.plane_height_range_slider.handle.setTextColor((218,224,218))

        self.plane_height_range_slider.startValueChanged.connect(self.toggle_mag_above_plane)
        self.plane_height_range_slider.startValueChanged.connect(self.all_planes_position)
        self.plane_height_range_slider.startValueChanged.connect(self.toggle_constrain_above_plane)
        self.plane_height_range_slider.startValueChanged.connect(self.toggle_symbols_between_planes)

        self.plane_height_range_slider.endValueChanged.connect(self.toggle_mag_above_plane)
        self.plane_height_range_slider.endValueChanged.connect(self.all_planes_position)
        self.plane_height_range_slider.endValueChanged.connect(self.toggle_constrain_above_plane)
        self.plane_height_range_slider.endValueChanged.connect(self.toggle_symbols_between_planes)

        planes_layout = QtWidgets.QHBoxLayout()
        planes_layout.addWidget(top_plane_cb)
        planes_layout.addWidget(bottom_plane_cb)
        planes_layout.addWidget(self.plane_height_range_slider)

        self.planes_frame_layout.addLayout(planes_layout)
        self.vlayout.addWidget(self.planes_frame)
    def energy_plot_layout(self):
        self.energy_plot_widget = pg.PlotWidget()
        self.update_scatter()
        
        y = self.structure_plot_widget.data.outcar_energies
        x = list(range(len(y)))
        self.energy_plot_widget.plot(x, y)


        self.energy_plot_frame_layout.addWidget(self.energy_plot_widget)
        self.vlayout.addWidget(self.energy_plot_frame)

    def update_scatter(self):
        for item in self.energy_plot_widget.getPlotItem().listDataItems():
            if isinstance(item, pg.ScatterPlotItem):
                self.energy_plot_widget.getPlotItem().removeItem(item)
        y = self.structure_plot_widget.data.outcar_energies
        x = list(range(len(y)))
        current_x = x[self.geometry_slider.value()]
        current_y = y[self.geometry_slider.value()]

        s1 = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 120))
        s1.addPoints([current_x], [current_y])
        self.energy_plot_widget.addItem(s1)

    def toggle_spheres(self, flag):
        """switches on and off spheres visibility"""
        for actor in self.structure_plot_widget.sphere_actors:
            actor.SetVisibility(flag)

    def toggle_bonds_between_planes(self, flag):
        for actor in self.structure_plot_widget.bond_actors:
            actor.SetVisibility(flag)

    def change_sphere_radius(self, value):
        self.sphere_radius = value / 10

    def change_sphere_radius_label(self):
        self.sphere_radius_label.setText(f"Sphere radius: {self.sphere_radius}")

    def add_sphere(self):
        """adds atoms from single geometry as spheres to renderer.
         Using VTK code because it is 100x faster than pyvista
         """
        for actor in self.structure_plot_widget.sphere_actors:
            self.plotter.renderer.RemoveActor(actor)
        self.structure_plot_widget.sphere_actors = []
        coordinates = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0]

        for coord, col in zip(coordinates, self.structure_plot_widget.atom_colors):
            sphere = pv.Sphere(radius=self.sphere_radius, center=(coord[0], coord[1], coord[2]))
            actor = self.plotter.add_mesh(sphere, color=col, smooth_shading=True, render=False)
            self.structure_plot_widget.sphere_actors.append(actor)
        self.plotter.update()

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
            coordinates = self.structure_plot_widget.data.outcar_coordinates[geometry_slider_value][0]
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
        if self.structure_plot_widget.plane_actor is not None:
            self.structure_plot_widget.plotter.remove_actor(self.structure_plot_widget.plane_actor)
        colors = vtkNamedColors()
        colors.SetColor('BkgColor', [26, 51, 77, 255])
        self.planeSource = vtkPlaneSource()
        self.planeSource.SetNormal(0.0, 0.0, 1.0)
        self.planeSource.SetOrigin(-5, -5, value)
        self.planeSource.SetPoint1(self.structure_plot_widget.data.x + 5, -5, value)
        self.planeSource.SetPoint2(-5, self.structure_plot_widget.data.y + 5, value)
        self.planeSource.Update()
        plane = self.planeSource.GetOutput()

        # Create a mapper and actor
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(plane)
        self.structure_plot_widget.plane_actor = vtkActor()
        self.structure_plot_widget.plane_actor.SetMapper(mapper)
        self.structure_plot_widget.plane_actor.GetProperty().SetColor(colors.GetColor3d('Banana'))
        #  self.plane_actor.GetProperty().SetOpacity()

        self.structure_plot_widget.plotter.renderer.AddActor(self.structure_plot_widget.plane_actor)

    def add_plane_higher(self, value):
        """renders a plane perpendicular to XY plane at value height"""
        if self.structure_plot_widget.plane_actor_heigher is not None:
            self.structure_plot_widget.plotter.remove_actor(self.structure_plot_widget.plane_actor_heigher)
        colors = vtkNamedColors()
        colors.SetColor('BkgColor', [26, 51, 77, 255])
        self.planeSource_heigher = vtkPlaneSource()
        self.planeSource_heigher.SetNormal(0.0, 0.0, 1.0)
        self.planeSource_heigher.SetOrigin(-5, -5, value)
        self.planeSource_heigher.SetPoint1(self.structure_plot_widget.data.x + 5, -5, value)
        self.planeSource_heigher.SetPoint2(-5, self.structure_plot_widget.data.y + 5, value)
        self.planeSource_heigher.Update()
        plane = self.planeSource_heigher.GetOutput()

        # Create a mapper and actor
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(plane)
        self.structure_plot_widget.plane_actor_heigher = vtkActor()
        self.structure_plot_widget.plane_actor_heigher.SetMapper(mapper)
        self.structure_plot_widget.plane_actor_heigher.GetProperty().SetColor(colors.GetColor3d('Banana'))
        #  self.plane_actor_heigher.GetProperty().SetOpacity()

        self.structure_plot_widget.plotter.renderer.AddActor(self.structure_plot_widget.plane_actor_heigher)

    def all_planes_position(self):
        val = self.plane_height_range_slider.getRange()
        startVal = val[0]
        endVal = val[1]
        #self.plane_position = startVal
        self.planeSource.SetOrigin(-5, -5, startVal / 100 * self.structure_plot_widget.data.z)
        self.planeSource.SetPoint1(self.structure_plot_widget.data.x + 5, -5, startVal / 100 * self.structure_plot_widget.data.z)
        self.planeSource.SetPoint2(-5, self.structure_plot_widget.data.y + 5, startVal / 100 * self.structure_plot_widget.data.z)
        self.planeSource.Update()

        self.planeSource_heigher.SetOrigin(-5, -5, endVal / 100 * self.structure_plot_widget.data.z)
        self.planeSource_heigher.SetPoint1(self.structure_plot_widget.data.x + 5, -5, endVal / 100 * self.structure_plot_widget.data.z)
        self.planeSource_heigher.SetPoint2(-5, self.structure_plot_widget.data.y + 5, endVal / 100 * self.structure_plot_widget.data.z)
        self.planeSource_heigher.Update()

        self.structure_plot_widget.plotter.renderer.Render()
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
            coords = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0])
            constr = [constr[0] for constr in self.structure_plot_widget.data.all_constrains]
            self.structure_plot_widget.constrain_actor = self.plotter.add_point_labels(coords, constr, font_size=30,
                                                                                       show_points=False,
                                                                                       always_visible=True, shape=None)
            self.structure_plot_widget.constrain_actor.SetVisibility(flag)

    def toggle_constrain_above_plane(self, flag):
        self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.constrain_actor)
        if self.constrains_between_planes_cb.isChecked():
            slidervalue = self.plane_height_range_slider.getRange()
            height = slidervalue[0] / 100 * self.structure_plot_widget.data.z
            end = slidervalue[1] / 100 * self.structure_plot_widget.data.z
            coordinates = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0])
            coords = []
            constr = []
            indice = np.where((coordinates[:, 2] > height) & (coordinates[:, 2] < end))[0]
            indices = indice.tolist()
            for i in range(len(indices)):
                coords.append(list(coordinates[indices[i]]))
                constr.append(self.structure_plot_widget.data.all_constrains[indices[i]][0])
            self.structure_plot_widget.constrain_actor = self.plotter.add_point_labels(coords, constr, font_size=30,
                                                                 show_points=False, always_visible=True, shape=None)
            self.structure_plot_widget.constrain_actor.SetVisibility(flag)

    def toggle_mag_above_plane(self, flag):
        self.plotter.renderer.RemoveActor(self.mag_actor)
        if self.mag_cb.isChecked():
            self.end_geometry()
            slidervalue = self.plane_height_range_slider.getRange()
            height = slidervalue[0] / 100 * self.structure_plot_widget.data.z
            end = slidervalue[1] / 100 * self.structure_plot_widget.data.z

            coordinates = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0])
            coords = []
            magnet = []
            mag = self.structure_plot_widget.data.outcar_data.magnetizations[self.geometry_slider.value()]
            indices = list(np.where((coordinates[:, 2] > height) & (coordinates[:, 2] < end))[0])
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
            coords = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0])
            self.structure_plot_widget.symb_actor = self.plotter.add_point_labels(coords, symbols, font_size=30,
                                                                                  show_points=False, always_visible=True,
                                                                                  shape=None)
            self.structure_plot_widget.symb_actor.SetVisibility(flag)

    def toggle_symbols_between_planes(self, flag):
        self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.symb_actor)
        if self.numbers_between_planes_cb.isChecked():
            slidervalue = self.plane_height_range_slider.getRange()
            height = slidervalue[0] / 100 * self.structure_plot_widget.data.z
            end = slidervalue[1] / 100 * self.structure_plot_widget.data.z
            coordinates = np.array(self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0])
            coords = []
            symb = []
            indice = np.where((coordinates[:, 2] > height) & (coordinates[:, 2] < end))[0]
            indices = indice.tolist()
            for i in range(len(indices)):
                coords.append(list(coordinates[indices[i]]))
                symb.append(self.structure_plot_widget.data.atoms_symb_and_num[indices[i]])
            self.structure_plot_widget.symb_actor = self.plotter.add_point_labels(coords, symb, font_size=30,
                                                                 show_points=False, always_visible=True, shape=None)
            self.structure_plot_widget.symb_actor.SetVisibility(flag)

    def add_symbol_and_number(self):
        """ renders an atom symbol and number"""
        self.structure_plot_widget.plotter.renderer.RemoveActor(self.structure_plot_widget.symb_actor)
        coordinates = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0]
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
        return self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0]

    def get_all_coordinates(self):
        return self.structure_plot_widget.data.outcar_coordinates

    def set_symbols(self, symbols):
        self.structure_plot_widget.data.atoms_symb_and_num = symbols

    def get_constrains(self):
        return self.structure_plot_widget.data.constrains

    def get_table_data(self):
        symb = self.structure_plot_widget.data.atoms_symb_and_num
        if len(self.structure_plot_widget.data.outcar_coordinates) == 1:
            coord = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()]
        else:
            coord = self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0]
        const = self.structure_plot_widget.data.all_constrains
        return symb, coord, const

    def update_row(self, row, atom_num_and_symb, coordinates, constraints):
        self.structure_plot_widget.data.atoms_symb_and_num[row] = atom_num_and_symb
        self.self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0][row] = coordinates
        self.self.structure_plot_widget.data.constrains[row] = constraints

    def delete_row(self, row):
        self.structure_plot_widget.data.atoms_symb_and_num.pop(row)
        self.structure_plot_widget.data.symbols.pop(row)
        self.structure_plot_widget.data.outcar_coordinates[self.geometry_slider.value()][0].pop(row) # delete all geo??
        self.structure_plot_widget.data.constrains.pop(row)
        self.structure_plot_widget.atom_colors.pop(row)
        for actor in self.structure_plot_widget.sphere_actors:
            self.plotter.renderer.RemoveActor(actor)
        self.structure_plot_widget.sphere_actors.pop(row)

    def on_selection(self, RectangleSelection):
        self.selected_actors = []
        actors = self.structure_plot_widget.sphere_actors
        for index, actor in enumerate(actors):
            is_inside = RectangleSelection.frustum.EvaluateFunction(actor.center) < 0
            if is_inside:
                actor.prop.color = 'yellow'
                self.selected_actors.append(actor)
            else:
                actor.prop.color = self.structure_plot_widget.atom_colors[index]

        self.selected_actors_changed.emit(self.selected_actors)

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



