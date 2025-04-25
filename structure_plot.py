#import pyqtgraph as pg
#import pyqtgraph.opengl as gl
import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter, QHBoxLayout, QFrame, QMenu, QAction
from PyQt5.QtGui import QCloseEvent
import platform
from pyvistaqt import QtInteractor

tic = time.perf_counter()
from vtk import vtkPolyDataMapper, vtkNamedColors, vtkPlaneSource, vtkActor, vtkLineSource, vtkSphereSource, \
    vtkPoints, vtkUnstructuredGrid, vtkHexahedron, vtkDataSetMapper
toc = time.perf_counter()
print(f'importing vtk, time: {toc - tic} seconds')

import numpy as np
import os
import json
from scipy.spatial.distance import pdist, squareform


class QtInteractor(QtInteractor):
    def __init__(self):
        super().__init__()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        camera_menu = QMenu("Camera")
        reset_camera_action = QAction("Reset Camera", self)
        reset_camera_action.triggered.connect(self.main_reset_camera)
        camera_menu.addAction(reset_camera_action)

        action2 = QAction("Take Screenshot", self)
        action2.triggered.connect(self.take_screenshot)

        menu.addMenu(camera_menu)
        menu.addAction(action2)

        menu.exec_(event.globalPos())

    def main_reset_camera(self):
        self.reset_camera()

    def take_screenshot(self):
        self.screenshot("screenshot.png")
        print("Screenshot saved!")

class StructureViewer(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.coordinates = self.data.init_coordinates
        self.sphere_actors = []
        self.symbol_mapping = None
        script_dir = os.path.dirname(__file__)
        colors_file = os.path.join(script_dir, 'elementColorSchemes.json')
        with open(colors_file, 'r') as file:
            self.color_data = json.load(file)
        self.assign_missing_colors()
        self.coord_pairs = []  # pairs of points connected by a bond
        self.bond_actors = []  # list of bond actors
        self.sphere_actors = []  # list of sphere actors
        self.geometry_actors = []  # list of geometries, each with actors list
        self.constrain_actor = None

        self.planeSource = None
        self.plane_position = int(self.data.z / 2) * 100
        self.plane_actor = None
        self.plane_actor_heigher = None
        self.symb_actor = None
        self.cube_actor = None
        self.mag_actor = None
        self.bond_actor = None
        self.master_bond_visibility = 2
        self.scatter_item = None
        self.charge_data = None
        self.contour_type = 'total'
        self.eps = 0.1
        self.sphere_radius = 0.5

        self.initUI()

        self.plotter.add_key_event('z', lambda: self.turn_camera("z"))
        self.plotter.add_key_event('x', lambda: self.turn_camera("x"))
        self.plotter.add_key_event('y', lambda: self.turn_camera("y"))


    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.plotter = QtInteractor()

        #self.plotter.set_background(color="#1e1f22")
        self.plotter.add_camera_orientation_widget()

        self.plotter.view_yz()
        self.plotter.camera_position = [(5, -60, 13),(4.8, 1.7, 12.3), (0,0,1)]
        self.plotter.camera.enable_parallel_projection()
        self.plotter.camera.parallel_scale = 18
        self.layout.addWidget(self.plotter.interactor)
        self.setLayout(self.layout)
        #self.add_structure()
        unit_vector_a = self.data.poscar.unit_cell_vectors()[0]
        unit_vector_b = self.data.poscar.unit_cell_vectors()[1]
        unit_vector_c = self.data.poscar.unit_cell_vectors()[2]
        self.add_unit_cell(unit_vector_a, unit_vector_b, unit_vector_c)

    def assign_missing_colors(self):
        splitted_symbols = [symbol.split("_")[0] for symbol in self.data.symbols]
        stripped_symbols = [''.join([char for char in input_string if char.isalpha()]) for input_string in splitted_symbols]
        missing_symbols = set(stripped_symbols) - set(self.color_data.keys())

        # Create a mapping of missing symbols to known elements
        if self.symbol_mapping is None:
            self.symbol_mapping = {}

            for missing_symbol in missing_symbols:
                print(f"The symbol '{missing_symbol}' is not in self.color_data.")
                while True:
                    user_input = input(
                        f"Please provide a known element name for '{missing_symbol}' (e.g., 'O', 'C', etc.): ").strip()
                    if user_input in self.color_data:
                        self.symbol_mapping[missing_symbol] = user_input
                        break
                    else:
                        print(f"'{user_input}' is not in self.color_data. Please try again.")

        # Assign colors to atoms based on the mapping or directly from self.color_data
        self.atom_colors = [
            self.color_data[self.symbol_mapping[symbol]] if symbol in self.symbol_mapping else self.color_data[symbol]
            for symbol in stripped_symbols
        ]

    def update_atom_colors(self):
        self.atom_colors = [self.color_data[self.data.symbols[i]] for i in range(len(self.data.atoms_symb_and_num))]

    def add_sphere(self, coord, col, radius):
        #sphere = pv.Sphere(radius=radius, center=(coord[0], coord[1], coord[2])) # TODO: change to vtk
        #actor = self.plotter.add_mesh(sphere, color=col, smooth_shading=True, render=False)
        actor = self._create_vtk_sphere(radius, coord, col)
        self.plotter.add_actor(actor)
        self.sphere_actors.append(actor)
        self.plotter.update()
        return self.sphere_actors

    def _create_vtk_sphere(self, radius, coord, col, theta_resolution=20, phi_resolution=20):
        # Create a sphere
        sphere_source = vtkSphereSource()
        sphere_source.SetRadius(radius)
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
        actor.GetProperty().SetColor(col)  # col should be an RGB tuple like (1.0, 0.0, 0.0)
        actor.GetProperty().SetInterpolationToPhong()  # Smooth shading
        # Optional: disable rendering until ready
        # actor.VisibilityOff()  # Equivalent to render=False in PyVista
        return actor

    def add_structure(self):
        for idx, coord in enumerate(self.coordinates):
            self.add_sphere(coord, self.atom_colors[idx], 0.5)

    def add_unit_cell(self, x, y, z):
        """renders an parallelpipe representig an unit cell"""
        self.cube_actor = self.make_cube(x, y, z)
        self.cube_actor.visibility = True
        self.plotter.renderer.AddActor(self.cube_actor)

    def make_cube(self, a1, a2, a3):
        '''
        create a vtk actor of unit cell.
        '''
        # define basis vectors
        #v1 = [x, 0, 0]
        #v2 = [0, y, 0]
        #v3 = [0, 0, z]
        origin = np.array([0.0, 0.0, 0.0])
        # Create points for the vertices of the parallelepiped
        points_np = [
            origin,
            origin + a2,
            origin + a2 + a1,
            origin + a1,
            origin + a3,
            origin + a3 + a2,
            origin + a3 + a2 + a1,
            origin + a3 + a1
        ]

        # Convert to vtkPoints
        points = vtkPoints()
        for pt in points_np:
            points.InsertNextPoint(pt.tolist())

        # Create a VTK cell for the parallelepiped
        parallelepiped = vtkHexahedron()
        for i in range(8):
            parallelepiped.GetPointIds().SetId(i, i)

        # Create a VTK unstructured grid and add the points and cell to it
        grid = vtkUnstructuredGrid()
        grid.SetPoints(points)
        grid.InsertNextCell(parallelepiped.GetCellType(), parallelepiped.GetPointIds())

        # Create a mapper
        mapper = vtkDataSetMapper()
        mapper.SetInputData(grid)

        # Create an actor
        actor = vtkActor()
        actor.SetMapper(mapper)
        # Make the faces transparent
        actor.GetProperty().SetOpacity(0.05)

        # Set the color of the edges to black
        actor.GetProperty().SetColor(1.0, 1.0, 1.0)

        # Make the edges thicker
        actor.GetProperty().SetLineWidth(1.0)
        return actor

    def turn_camera(self, direction):
        position, scale = self.get_camera_params()
        if direction == "x":
            self.plotter.view_yz()
        elif direction == "y":
            self.plotter.view_xz()
        elif direction == "z":
            self.plotter.view_xy()
        self.plotter.camera.parallel_scale = scale

    def get_camera_params(self):
        position = self.plotter.camera_position
        scale = self.plotter.camera.parallel_scale
        return position, scale

    def set_camera_params(self, position, scale):
        self.plotter.camera_position = position
        self.plotter.camera.parallel_scale = scale

    def closeEvent(self, QCloseEvent):
        super().closeEvent(QCloseEvent)
        self.plotter.Finalize()

