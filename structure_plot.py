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
import vtk
toc = time.perf_counter()
print(f'importing vtk, time: {toc - tic} seconds')

import numpy as np
import os
import json
from scipy.spatial.distance import pdist, squareform


class QtInteractor(QtInteractor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

        script_dir = os.path.dirname(__file__)
        colors_file = os.path.join(script_dir, 'elementColorSchemes.json')
        with open(colors_file, 'r') as file:
            self.color_data = json.load(file)
        self.symbol_mapping = None
        self.constrain_actor = None
        self.planeSource = None
        self.plane_actor = None
        self.plane_actor_heigher = None
        self.symb_actor = None
        self.cube_actor = None
        self.mag_actor = None
        self.bond_actor = None
        self.scatter_item = None
        self.charge_data = None
        self.contour_type = 'total'
        self.sphere_actors = []
        self.coord_pairs = []  # pairs of points connected by a bond
        self.bond_actors = []  # list of bond actors
        self.sphere_actors = []  # list of sphere actors
        self.geometry_actors = []  # list of geometries, each with actors list
        self.reset_variables()

        self.initUI()

        self.plotter.add_key_event('z', lambda: self.turn_camera("z"))
        self.plotter.add_key_event('x', lambda: self.turn_camera("x"))
        self.plotter.add_key_event('y', lambda: self.turn_camera("y"))

    def reset_variables(self):
        self.coordinates = self.data.init_coordinates
        self.plane_position = int(self.data.z / 2) * 100
        self.master_bond_visibility = 2
        self.eps = 0.1
        self.sphere_radius = 0.5
        self.assign_missing_colors()

    def update_data(self, data):
        self.data = data
        self.reset_variables()
        self.reset_unit_cell()
        self.plotter.view_yz()
        self.plotter.camera_position = [(5, -60, 13), (4.8, 1.7, 12.3), (0, 0, 1)]
        self.plotter.camera.enable_parallel_projection()
        self.plotter.camera.parallel_scale = 18

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.plotter = QtInteractor(auto_update=0)

        #self.plotter.set_background(color="#1e1f22")
        self.plotter.add_camera_orientation_widget()

        self.plotter.view_yz()
        self.plotter.camera_position = [(5, -60, 13),(4.8, 1.7, 12.3), (0,0,1)]
        self.plotter.camera.enable_parallel_projection()
        self.plotter.camera.parallel_scale = 18
        self.layout.addWidget(self.plotter.interactor)
        self.setLayout(self.layout)
        self.reset_unit_cell()

        #self.setup_lighting(self.plotter.renderer)

    def setup_lighting(self, renderer):
        # Add a headlight (follows camera)
        light = vtk.vtkLight()
        light.SetLightTypeToHeadlight()
        light.SetIntensity(0.1)
        renderer.AddLight(light)

        # Add subtle ambient light
        ambient_light = vtk.vtkLight()
        ambient_light.SetLightTypeToSceneLight()
        ambient_light.SetPosition(1, 1, 1)
        ambient_light.SetIntensity(0.1)
        renderer.AddLight(ambient_light)

    def reset_unit_cell(self):
        try:
            self.plotter.renderer.RemoveActor(self.cube_actor)
        except:
            pass
        unit_vector_a = self.data.poscar.unit_cell_vectors()[0]
        unit_vector_b = self.data.poscar.unit_cell_vectors()[1]
        unit_vector_c = self.data.poscar.unit_cell_vectors()[2]
        self.add_unit_cell(unit_vector_a, unit_vector_b, unit_vector_c)

    def assign_missing_colors(self):
        splitted_symbols = [symbol.split("_")[0] for symbol in self.data.symbols]
        stripped_symbols = [''.join([char for char in input_string if char.isalpha()]) for input_string in splitted_symbols]
        self.data.stripped_symbols = stripped_symbols
        missing_symbols = set(stripped_symbols) - set(self.color_data.keys())

        # Create a mapping of missing symbols to known elements
        #if self.symbol_mapping is None:
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

