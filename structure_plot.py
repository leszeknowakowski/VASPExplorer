#import pyqtgraph as pg
#import pyqtgraph.opengl as gl
import time
tic = time.perf_counter()
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter, QHBoxLayout, QFrame
toc = time.perf_counter()
print(f'importing PyQt5 from Structure, time: {toc - tic:0.4f} seconds')

tic = time.perf_counter()
import pyvista as pv
toc = time.perf_counter()
print(f'importing pyvista from Structure, time: {toc - tic:0.4f} seconds')

tic = time.perf_counter()
from pyvistaqt import QtInteractor
toc = time.perf_counter()
print(f'importing pyqt from Structure, time: {toc - tic}')

tic = time.perf_counter()
from vtk import *
import vtkmodules.all as vtk
toc = time.perf_counter()
print(f'importing vtk {toc - tic}')

tic = time.perf_counter()
import platform
toc = time.perf_counter()
print(f'import platform in structure_plot: {toc - tic:0.4f}')

import numpy as np
import os
import json
from scipy.spatial.distance import pdist, squareform

#pg.setConfigOptions(antialias=True)

class StructureViewer(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.coordinates = self.data.init_coordinates
        self.sphere_actors = []
        script_dir = os.path.dirname(__file__)
        colors_file = os.path.join(script_dir, 'elementColorSchemes.json')
        with open(colors_file, 'r') as file:
            color_data = json.load(file)
        self.atom_colors = [color_data[self.data.symbols[i]] for i in range(self.data.number_of_atoms)]
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


    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.plotter = QtInteractor()
        self.plotter.set_background(color="#1e1f22")
        self.plotter.add_camera_orientation_widget()

        self.plotter.view_yz()
        self.plotter.camera_position = [(5, -60, 13),(4.8, 1.7, 12.3), (0,0,1)]
        self.plotter.camera.enable_parallel_projection()
        self.plotter.camera.parallel_scale = 18
        self.layout.addWidget(self.plotter.interactor)
        self.setLayout(self.layout)
        self.add_structure()
        #self.add_bonds(1,1)
        self.add_unit_cell(self.data.x,self.data.y,self.data.z)

    def add_sphere(self, coord, col, radius):
        sphere = pv.Sphere(radius=radius, center=(coord[0], coord[1], coord[2]))
        actor = self.plotter.add_mesh(sphere, color=col, smooth_shading=True)
        self.sphere_actors.append(actor)
        self.plotter.update()
        return self.sphere_actors

    def add_structure(self):
        for idx, coord in enumerate(self.coordinates):
            self.add_sphere(coord, self.atom_colors[idx], 0.5)

    def add_unit_cell(self, x, y, z):
        """renders an parallelpipe representig an unit cell"""
        self.cube_actor = self.make_cube(x, y, z)
        self.cube_actor.visibility = True
        self.plotter.renderer.AddActor(self.cube_actor)

    def make_cube(self, x, y, z):
        '''create a vtk actor of unit cell.
        DISCLAIMER: now it handles only parallelpipes with right angles, eg. tetragonal, orthorombic and regular.
        Further to be improved.'''
        # define basis vectors
        v1 = [x, 0, 0]
        v2 = [0, y, 0]
        v3 = [0, 0, z]

        # Create points for the vertices of the parallelepiped
        points = vtk.vtkPoints()
        points.InsertNextPoint(0.0, 0.0, 0.0)
        points.InsertNextPoint(v1)
        points.InsertNextPoint([v1[i] + v2[i] for i in range(3)])
        points.InsertNextPoint(v2)
        points.InsertNextPoint(v3)
        points.InsertNextPoint([v1[i] + v3[i] for i in range(3)])
        points.InsertNextPoint([v1[i] + v2[i] + v3[i] for i in range(3)])
        points.InsertNextPoint([v2[i] + v3[i] for i in range(3)])

        # Create a VTK cell for the parallelepiped
        parallelepiped = vtk.vtkHexahedron()
        for i in range(8):
            parallelepiped.GetPointIds().SetId(i, i)

        # Create a VTK unstructured grid and add the points and cell to it
        grid = vtk.vtkUnstructuredGrid()
        grid.SetPoints(points)
        grid.InsertNextCell(parallelepiped.GetCellType(), parallelepiped.GetPointIds())

        # Create a mapper
        mapper = vtk.vtkDataSetMapper()
        mapper.SetInputData(grid)

        # Create an actor
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # Make the faces transparent
        actor.GetProperty().SetOpacity(0.05)

        # Set the color of the edges to black
        actor.GetProperty().SetColor(1.0, 1.0, 1.0)

        # Make the edges thicker
        actor.GetProperty().SetLineWidth(1.0)

        return actor
