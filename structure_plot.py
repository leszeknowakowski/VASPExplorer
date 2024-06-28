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
        if platform.system() == 'Linux':
            colors_file = "/home/lnowakowski/venv/vasp-projects/view_poscar/scripts/9999.VASPExplorer"
        elif platform.system() == 'Windows':
            file = "F:\\syncme-from-c120\\Studia\\python\\vasp_geo\\project_geo\\2.Splitted_PyQtGraph\\elementColorSchemes.json"
            if os.path.isfile(file):
                colors_file = file
            else:
                colors_file = ("D:\\syncme-from-c120\\Studia\\python\\vasp_geo\\project_geo\\2.Splitted_PyQtGraph\\elementColorSchemes.json")
        else:
            print("can't resolve operating system. lol, Please Leszek, write your code only on Windows or Linux")
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
        self.bond_actors = None
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
        """adds atoms from single geometry as spheres to renderer.
         Using VTK code because it is 100x faster than pyvista
         """
        sphere = vtkSphereSource()
        sphere.SetRadius(radius)
        sphere.SetThetaResolution(10)
        sphere.SetPhiResolution(15)
        sphere.SetCenter(*coord)
        sphere_mapper = vtkPolyDataMapper()
        sphere_mapper.SetInputConnection(sphere.GetOutputPort())
        sphere_actor = vtkActor()
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(col[0] / 255, col[1] / 255, col[2] / 255)
        self.sphere_actors.append(sphere_actor)
        self.plotter.renderer.AddActor(sphere_actor)
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
        DISCLAIMER: now it handles only parallelpipes with right angles, eg. tetragonal, orthoromic and regular.
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




'''
### lets switch to PyVista for a while... better vis options and shaders
    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.structure_widget = gl.GLViewWidget()
        self.structure_widget.setBackgroundColor('w')
        self.structure_widget.setCameraPosition(distance=40)
        self.element_colors = self.import_json()
        self.layout.addWidget(self.structure_widget)

        #self.add_structure()
        #self.add_sphere([0,0,0], "O")
        #self.add_sphere([2,2,2], "O")
        self.add_structure()
        self.add_unit_cell(self.data.unit_cell_vectors)
        self.add_numbers()
        self.add_top_plane()


    @staticmethod
    def import_json():
        script_dir = os.path.dirname(os.path.realpath(__file__))
        json_file_path = os.path.join(script_dir, 'elementColorSchemes.json')
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        for key in data:
            rescaled_list = [x / 255 for x in data[key]]
            rescaled_list.append(1)
            data[key] = rescaled_list
        return data

    def add_sphere(self, coords, atom):
        md = gl.MeshData.sphere(rows=10, cols=20)
        md.setFaceColors([self.element_colors[atom]]*md.faceCount())
        m3 = gl.GLMeshItem(meshdata=md, smooth=True, shader='shaded')
        m3.translate(*coords)
        self.structure_widget.addItem(m3)

    def add_structure(self):
        for idx, coord in enumerate(self.coordinates):
            self.add_sphere(coord, self.data.list_atomic_symbols[idx])

    def add_unit_cell(self, basis_vectors):
        v1 = np.array(basis_vectors[0])
        v2 = np.array(basis_vectors[1])
        v3 = np.array(basis_vectors[2])

        # Define vertices
        verts = np.array([
            [0, 0, 0],  # Vertex 0
            v1,  # Vertex 1
            v2,  # Vertex 2
            v3,  # Vertex 3
            v1 + v2,  # Vertex 4
            v1 + v3,  # Vertex 5
            v2 + v3,  # Vertex 6
            v1 + v2 + v3  # Vertex 7
        ])

        # Define faces using the vertices indices
        faces = np.array([
            [0, 1, 4], [0, 4, 2],  # Bottom face
            [0, 1, 5], [0, 5, 3],  # Front face
            [0, 2, 6], [0, 6, 3],  # Left face
            [1, 4, 7], [1, 7, 5],  # Right face
            [2, 4, 7], [2, 7, 6],  # Back face
            [3, 5, 7], [3, 7, 6]  # Top face
        ])
        color =  [0.7, 0.7, 0.7, 0.3]
        color_array = []
        for i in range(12):
            color_array.append(color)


        ## Mesh item will automatically compute face normals.
        m1 = gl.GLMeshItem(vertexes=verts, faces=faces, faceColors=color_array, smooth=False, glOptions="translucent")
        m1.translate(0, 0, 0)
        self.structure_widget.addItem(m1)

    def add_numbers(self):
        numbers = self.data.atoms_symb_and_num
        for idx, coord in enumerate(self.coordinates):
            text = gl.GLTextItem()
            text.setData(pos=(coord[0], coord[1], coord[2]), color=(1, 1, 1, 255), text=numbers[idx])
            self.structure_widget.addItem(text)

    def add_top_plane(self):
        z = pg.gaussianFilter(np.random.normal(size=(50, 50)), (10, 10))
        p1 = gl.GLSurfacePlotItem(z=z, shader='shaded', color=(0, 0, 0, 0.3), glOptions='translucent')
        p1.scale(1,1, 1.0)
        p1.translate(0, 0, 10)
        self.structure_widget.addItem(p1)

    def add_bottom_plane(self):
        pass
'''