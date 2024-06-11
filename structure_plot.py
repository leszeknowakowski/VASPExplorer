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

        self.add_structure()

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
        for coord in coords:
            self.add_sphere(coord, "O")
        pass

