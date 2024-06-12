import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter, QHBoxLayout
import numpy as np
import os
import json

pg.setConfigOptions(antialias=True)

class StructureViewer(QWidget):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.initUI()


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
        md = gl.MeshData.sphere(rows=100, cols=200)
        md.setFaceColors([self.element_colors[atom]]*md.faceCount())
        m3 = gl.GLMeshItem(meshdata=md, smooth=False, shader='shaded')
        m3.translate(*coords)
        self.structure_widget.addItem(m3)

    def add_structure(self):
        coords = self.data.init_coordinates
        for idx, coord in enumerate(coords):
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


