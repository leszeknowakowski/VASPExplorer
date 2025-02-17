from vasp_data import VaspData
import os
import sys
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                             QSlider, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
                             QPushButton)

from PyQt5.QtGui import QFont
from PyQt5 import QtCore
from scipy.spatial.distance import pdist, squareform
import numpy as np
import pyqtgraph as pg
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkFiltersSources import vtkSphereSource,  vtkLineSource
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkInteractionWidgets import vtkCameraOrientationWidget
from vtkmodules.vtkRenderingCore import vtkActor,  vtkRenderer, vtkPolyDataMapper
import platform
from vtk import vtkCamera
import QVTKRenderWindowInteractor as QVTK
QVTKRenderWindowInteractor = QVTK.QVTKRenderWindowInteractor
colors = vtkNamedColors()


class ReadNebData:
    def __init__(self, dir):
        self.dir = dir
        self.neb_dirs = []
        self.max_min_dirs = self.find_start_stop_dirs()
        self.neb_energies = []
        self.neb_positions = []
        self.neb_magnetizations = []
        self.start_stop_energies = []
        self.start_stop_positions = []
        self.start_stop_magnetizations = []

        self.parse_middle_dirs()
        self.parse_start_stop_dirs()

    def find_start_stop_dirs(self):
        for item in os.listdir(self.dir):
            if os.path.isdir(os.path.join(self.dir, item)) and len(item) == 2:
                self.neb_dirs.append(item)
        max_min_dirs = [min(self.neb_dirs), max(self.neb_dirs)]
        return max_min_dirs

    def parse_middle_dirs(self):
        middle_neb_dirs = []
        for item in os.listdir(self.dir):
            neb_dir = os.path.join(self.dir, item)
            if os.path.isdir(neb_dir) and item not in self.max_min_dirs:
                middle_neb_dirs.append(neb_dir)
        middle_neb_dirs.sort()
        for neb_dir in middle_neb_dirs:
            data = VaspData(neb_dir)
            self.neb_energies.append(data.outcar_data.find_energy())
            self.neb_positions.append(data.outcar_data.find_coordinates())
            self.neb_magnetizations.append(data.outcar_data.magnetizations)

    def parse_start_stop_dirs(self):
        dirs = os.listdir(self.dir)
        dirs.sort()
        for item in dirs:
            neb_dir = os.path.join(self.dir, item)
            if os.path.isdir(neb_dir) and item in self.max_min_dirs:
                self.data = VaspData(neb_dir)
                self.start_stop_positions.append(self.data.outcar_coordinates[-1])
                self.start_stop_energies.append(self.data.outcar_energies[-1])
                self.start_stop_magnetizations.append(self.data.outcar_data.magnetizations[-1])


class NebWindow(QMainWindow):
    def __init__(self, parent=None, show=True):
        """ Initialize GUI """
        super().__init__()

        QMainWindow.__init__(self, parent)
        if platform.system() == 'Linux':
            dir = './'
        else:
            #dir = "F:\\syncme\\modelowanie DFT\\co3o4_new_new\\9.deep_o2_reduction\\5.newest_after_statistics\\2.NEB\\1.2ominus_o2ads\\3.NEB\\4.again_with_converged_wavecars\\2.NEB"
            dir = "D:\\test_fir_doswizard\\1.NEBS\\4.from_zasada\\4.Peroxy_desorption\\2.TS_search"
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
        self.main_layout = QHBoxLayout()
        main_widget.setLayout(self.main_layout)
        self.splitter = QSplitter(QtCore.Qt.Vertical)
        self.main_layout.addWidget(self.splitter)

        self.add_slider_widget()

        self.topLayout = QHBoxLayout()
        self.top_widget = QWidget()
        self.top_widget.setLayout(self.topLayout)
        self.splitter.addWidget(self.top_widget)

        self.add_table_widget()
        self.add_plotters()
        self.add_label_and_button()

        self.energy_plot_frame_layout = QVBoxLayout()
        self.energy_plot_layout()

        self.energy_plotWidget = QWidget()
        self.energy_plotWidget.setLayout(self.energy_plot_frame_layout)
        self.splitter.addWidget(self.energy_plotWidget)

        self.add_start_end_structures()
        self.add_intermediate_structures()


        # Set main window properties
        self.setWindowTitle("NEBviewer v0.0.1")
        self.resize(1600, 800)

    def add_slider_widget(self):
        self.geo_slider = QSlider()
        self.geo_slider.setOrientation(QtCore.Qt.Horizontal)
        self.geo_slider.setMinimum(0)
        self.geo_slider.setMaximum(len(self.neb.neb_positions[0])-1)
        self.geo_slider.setValue(1)
        self.geo_slider.valueChanged.connect(self.update_chart)
        self.geo_slider.valueChanged.connect(self.update_intermediate_structures)
        self.geo_slider.valueChanged.connect(self.update_slider_label)
        self.geo_slider.valueChanged.connect(self.update_table)
        self.geo_slider.valueChanged.connect(self.set_Eakt_label)
        self.sliderLayout = QHBoxLayout()

        self.slider_count_label = QLabel()
        self.slider_count_label.setText(f"Steps: {self.geo_slider.value()}")

        self.sliderLayout.addWidget(self.slider_count_label)
        self.sliderLayout.addWidget(self.geo_slider)
        slider_widget=QWidget()
        slider_widget.setLayout(self.sliderLayout)

        self.splitter.addWidget(slider_widget)

    def add_plotters(self):
        self.plotters = []
        self.widget = QVTKRenderWindowInteractor() # maybe add parent
        self.topLayout.addWidget(self.widget)
        style = vtkInteractorStyleTrackballCamera()
        self.widget.GetRenderWindow().GetInteractor().SetInteractorStyle(style)

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

            self.widget.GetRenderWindow().AddRenderer(ren)

            orientation_widget = vtkCameraOrientationWidget()
            orientation_widget.SetParentRenderer(ren)
            orientation_widget.SetAnimate(True)
            orientation_widget.SetAnimatorTotalFrames(20)
            orientation_widget.On()

            self.plotters.append(ren)

        self.last_renderer = None
        self.widget.GetRenderWindow().GetInteractor().AddObserver("LeftButtonPressEvent", self.on_left_click)

        self.widget.Initialize()
        self.widget.Start()
        self.widget.GetRenderWindow().Render()

    def on_left_click(self, obj, event):
        # Get the position of the mouse click
        x, y = self.widget.GetRenderWindow().GetInteractor().GetEventPosition()

        # Find the renderer at the clicked position
        renderer = self.widget.GetRenderWindow().GetInteractor().FindPokedRenderer(x, y)

        # If a renderer is clicked, update highlighting
        if renderer:
            # Reset the previous renderer's background color
            if self.last_renderer:
                self.last_renderer.SetBackground((1,1,1))

            # Set the new renderer's background to the highlight color
            renderer.SetBackground((1.0, 1.0, 0.8) )

            # Store the current renderer as the last clicked renderer
            self.last_renderer = renderer

            # Render the window to update the colors
            self.widget.GetRenderWindow().Render()

    def add_table_widget(self):
        self.mag_table_widget = QTableWidget()
        self.mag_table_widget.setRowCount(7)
        columns_count = 2*len(self.neb.neb_dirs)
        self.mag_table_widget.setColumnCount(columns_count)
        for i in range(columns_count):
            self.mag_table_widget.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        rows = ['Co18', 'Co25', 'O71', 'O72', 'Co18-O71', 'Co25-O72', 'O71-O72']
        for column in range(0, columns_count, 2):
            for row, item in enumerate(rows):
                self.mag_table_widget.setItem(row, column, QTableWidgetItem(item))
        mags = []

        #indices of atoms to add information to table, further to imporove with user input or DOSwizard input
        self.indices = (17,24,70,71)
        try:
            mags.append([self.neb.start_stop_magnetizations[0][i] for i in self.indices])
        except IndexError:
            input_indices = input("Write indices of atoms to show separates by commas : ")
            self.indices = tuple(int(x) for x in input_indices.split(','))
            mags = []
        mags.append([self.neb.start_stop_magnetizations[0][i] for i in self.indices])
        for i in range(int(columns_count/2 -2)):
            mags.append([self.neb.neb_magnetizations[i][0][j] for j in self.indices])
        mags.append([self.neb.start_stop_magnetizations[1][i] for i in self.indices])

        bond_lengths = self.update_bond_lengths()
        start_stop_bond_length = self.get_start_stop_bond_length()

        bonds = []
        bonds.append(start_stop_bond_length[0])
        for i in range(len(bond_lengths)):
            bonds.append(bond_lengths[i])
        bonds.append(start_stop_bond_length[1])

        for column in range(1, columns_count, 2):
            col = int((column-1)/2)
            for row in [0,1,2,3]:
                text = str(mags[col][row])
                self.mag_table_widget.setItem(row, column, QTableWidgetItem(text))
            for row in [4,5,6]:
                text = f"{bonds[col][row-4]:.2f}"
                self.mag_table_widget.setItem(row, column, QTableWidgetItem(text))

        self.mag_table_widget.resizeRowsToContents()
        self.mag_table_widget.resizeColumnsToContents()
        self.splitter.addWidget(self.mag_table_widget)

    def update_table(self):
        columns_count = 2 * len(self.neb.neb_dirs)
        mags = []
        # indices of atoms to choose magnetization from (num of atom - 1 )
        #self.indices = (17, 24, 70, 71)

        # append start magnetization
        mags.append([self.neb.start_stop_magnetizations[0][i] for i in self.indices])
        val = self.geo_slider.value()

        # append middle magnetizations
        for i in range(int(columns_count / 2 - 2)):
            mags.append([self.neb.neb_magnetizations[i][val][j] for j in self.indices])

        # append stop magnetization
        mags.append([self.neb.start_stop_magnetizations[1][i] for i in self.indices])

        bond_lengths = self.update_bond_lengths()
        start_stop_bond_length = self.get_start_stop_bond_length()

        bonds = []
        bonds.append(start_stop_bond_length[0])
        for i in range(len(bond_lengths)):
            bonds.append(bond_lengths[i])
        bonds.append(start_stop_bond_length[1])

        for column in range(1, columns_count, 2):
            col = int((column - 1) / 2)
            for row in [0, 1, 2, 3]:
                text = str(mags[col][row])
                self.mag_table_widget.setItem(row, column, QTableWidgetItem(text))
            for row in [4, 5, 6]:
                text = f"{bonds[col][row - 4]:.2f}"
                self.mag_table_widget.setItem(row, column, QTableWidgetItem(text))


    def add_label_and_button(self):
        self.label_and_btn_widget = QWidget()
        self.label_layout = QHBoxLayout()

        self.label = QLabel()
        self.button = QPushButton("copy view from 1st window")
        self.button.clicked.connect(self.copy_view)
        self.Eakt_label = QLabel()
        self.set_Eakt_label()
        self.label_layout.addWidget(self.label)
        self.label_layout.addWidget(self.Eakt_label)
        self.label_layout.addWidget(self.button)

        self.label_and_btn_widget.setLayout(self.label_layout)
        self.splitter.addWidget(self.label_and_btn_widget)

    def copy_view(self):
        renderer = self.last_renderer
        original_camera = renderer.GetActiveCamera()
        for render in self.plotters:
            if render is not renderer:
                new_camera = render.GetActiveCamera()
                new_camera.SetPosition(original_camera.GetPosition())
                new_camera.SetFocalPoint(original_camera.GetFocalPoint())
                new_camera.SetViewUp(original_camera.GetViewUp())
                new_camera.SetClippingRange(original_camera.GetClippingRange())
                new_camera.SetParallelScale(original_camera.GetParallelScale())
                new_camera.SetViewAngle(original_camera.GetViewAngle())
                render.ResetCameraClippingRange()
        self.widget.GetRenderWindow().Render()

    def energy_plot_layout(self):
        self.graphics_layout_widget = pg.GraphicsLayoutWidget()
        self.energy_plot_widget = self.graphics_layout_widget.addPlot(row=0)
        self.energy_plot_widget.setAutoVisible(y=True)

        my_font = QFont("Times", 15, QFont.Bold)
        self.energy_plot_widget.setLabel('bottom', "image")
        self.energy_plot_widget.setLabel('left', "energy")

        # Set your custom font for both axes
        self.energy_plot_widget.getAxis("bottom").label.setFont(my_font)
        self.energy_plot_widget.getAxis("left").label.setFont(my_font)
        self.energy_plot_widget.getAxis("bottom").setTickFont(my_font)
        self.energy_plot_widget.getAxis("left").setTickFont(my_font)

        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.hLine = pg.InfiniteLine(angle=0, movable=False)
        self.energy_plot_widget.addItem(self.vLine, ignoreBounds=True)
        self.energy_plot_widget.addItem(self.hLine, ignoreBounds=True)

        self.vb = self.energy_plot_widget.vb

        self.update_chart()
        self.energy_plot_widget.scene().sigMouseMoved.connect(self.mouseMoved)
        x, y = self.update_energy_data()
        self.energy_plot_widget.plot(x,y)
        self.energy_plot_frame_layout.addWidget(self.graphics_layout_widget)

    def mouseMoved(self, evt):
        pos = evt
        if self.energy_plot_widget.sceneBoundingRect().contains(pos):
            mousePoint = self.vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            if index > 0 and index < len(self.update_energy_data()[0]):
                self.label.setText(
                    "<span style='font-size: 12pt'>x=%0.1f,   <span style='color: red'>y1=%1f</span>" % (
                    mousePoint.x(), mousePoint.y()))
            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())

    def update_energy_data(self):
        x = list(range(1, len(self.neb.neb_dirs) + 1))
        y = []
        y.append(self.neb.start_stop_energies[0])
        for i in range(len(self.neb.neb_energies)):
            lst = self.neb.neb_energies[i]
            y.append(lst[self.geo_slider.value()])
        y.append(self.neb.start_stop_energies[1])
        y = [item for sublist in y for item in (sublist if isinstance(sublist, list) else [sublist])]
        return x, y

    def update_chart(self):
        for item in self.energy_plot_widget.listDataItems():
            if isinstance(item, pg.graphicsItems.PlotDataItem.PlotDataItem) or isinstance(item, pg.graphicsItems.ScatterPlotItem.ScatterPlotItem):
                self.energy_plot_widget.removeItem(item)
        x, y = self.update_energy_data()
        self.energy_plot_widget.plot(x, y)
        self.scatter_plot = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 120))
        self.scatter_plot.addPoints(x=x, y=y)
        self.energy_plot_widget.addItem(self.scatter_plot)


    def update_slider_label(self):
        self.slider_count_label.setText(f"Steps: {self.geo_slider.value()}")

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

    def find_bond_length(self, coord1, coord2):
        A = np.array([coord1[0], coord1[1], coord1[2]])
        B = np.array([coord2[0], coord2[1], coord2[2]])
        bond_length = np.linalg.norm(B-A)
        return bond_length

    def update_bond_lengths(self):
        images = len(self.neb.neb_dirs)
        coordinates = self.neb.neb_positions
        image_coordinates = []
        bond_lengths = []
        co1 = self.indices[0]
        co2 = self.indices[1]
        o1 = self.indices[2]
        o2 = self.indices[3]

        for image in coordinates:
            image_coordinates.append(image[self.geo_slider.value()])
        for i in range(0, images-2): # loop for plotters
            coords = image_coordinates[i]
            co18o71 = self.find_bond_length(coords[co1], coords[o1])
            co25o72 = self.find_bond_length(coords[co2], coords[o2])
            o71o72 = self.find_bond_length(coords[o1], coords[o2])
            bond_lengths.append([co18o71, co25o72, o71o72])
        return bond_lengths

    def get_start_stop_bond_length(self):
        bond_lengths = []
        coordinates = self.neb.start_stop_positions
        co1 = self.indices[0]
        co2 = self.indices[1]
        o1 = self.indices[2]
        o2 = self.indices[3]
        for i in range(2):
            coords = coordinates[i]
            co18o71 = self.find_bond_length(coords[co1], coords[o1])
            co25o72 = self.find_bond_length(coords[co2], coords[o2])
            o71o72 = self.find_bond_length(coords[o1], coords[o2])
            bond_lengths.append([co18o71, co25o72, o71o72])
        return bond_lengths

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
    def set_Eakt_label(self):
        x, y = self.update_energy_data()
        start = y[0]
        stop = stop = y[-1]
        max = np.max(y)
        eakt_right = max - start
        eakt_left = max - stop
        self.Eakt_label.setText(
            f"Eakt --> : {eakt_right:.2f},  Eakt <-- : {eakt_left:.2f}"
        )
        my_font = QFont("Calibri", 18, QFont.Bold)
        self.Eakt_label.setFont(my_font)


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

