import sys
import os

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, QFileDialog, QDockWidget
from PyQt5.QtCore import Qt  # Import Qt for DockWidget positioning
import pyqtgraph as pg
from pyvistaqt import MainWindow

from vasp_data import VaspData
from dos_plot_widget import DosPlotWidget
from dos_control_widget import DosControlWidget
from structure_plot import StructureViewer
from structure_controls import StructureControlsWidget
from structure_variable_controls import StructureVariableControls
from chgcar_controls import ChgcarVis

pg.setConfigOptions(antialias=True)


class MainWindow(QMainWindow):
    """
    This class initializes the PyQt5 main window - bars, icons, widgets, and
    all of the GUI components
    """
    def __init__(self, parent=None, show=True):
        """ Initialize GUI """
        super().__init__(parent)
        self.dir = self.set_working_dir()
        self.create_data(self.dir)  # Pass the working directory to create_data()
        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        self.initUI()

    def initUI(self):
        """ Initialize all GUI widgets, set titles, toolbars, layouts, actions """
        self.setWindowTitle('DOSWave v.0.0.0')
        self.resize(1400, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        splitter = QSplitter()
        main_layout.addWidget(splitter)

        # Left tabs for plots (using dockable widgets)
        left_tab_widget = QTabWidget()

        # Widget for Density of States plot
        self.dos_plot_widget = DosPlotWidget(self.data)
        self.dos_plot_dock = QDockWidget("DOS", self)
        self.dos_plot_dock.setWidget(self.dos_plot_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dos_plot_dock)

        # Widget for renderer interactor for plotting the structure
        self.structure_plot_interactor_widget = StructureViewer(self.data)
        self.structure_plot_dock = QDockWidget("Structure", self)
        self.structure_plot_dock.setWidget(self.structure_plot_interactor_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.structure_plot_dock)

        splitter.addWidget(left_tab_widget)
        left_tab_widget.setCurrentIndex(1)

        # Right tabs for GUI
        right_tab_widget = QTabWidget()

        # Widget for controlling the DOS plot
        self.dos_control_widget = DosControlWidget(self.data, self.dos_plot_widget)
        right_tab_widget.addTab(self.dos_control_widget, "DOS Parameters")

        # Topmost tab widget for all structure plot manipulations
        structure_tabs = QTabWidget()

        # Tab for controlling the rendering structure plot
        self.structure_plot_control_tab = StructureControlsWidget(self.structure_plot_interactor_widget)
        structure_tabs.addTab(self.structure_plot_control_tab, "Structure plot control")

        # Tab for controlling the crystal structure - position and properties of atoms
        self.structure_variable_control_tab = StructureVariableControls(self.structure_plot_control_tab)
        structure_tabs.addTab(self.structure_variable_control_tab, "Structure variables control")

        right_tab_widget.addTab(structure_tabs, "Crystal structure")
        right_tab_widget.setCurrentIndex(1)
        structure_tabs.setCurrentIndex(1)

        # Tab for controlling the charge density plots
        self.chgcar_control_widget = ChgcarVis(self.structure_plot_control_tab.plotter)
        self.chgcar_control_widget.chg_file_path = os.path.join(self.dir, "CHGCAR")
        structure_tabs.addTab(self.chgcar_control_widget, "PARCHG/CHGCAR")

        splitter.addWidget(right_tab_widget)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 10)

    def set_working_dir(self):
        """ Allow the user to select the working directory """
        return "D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt"

    def create_data(self, dir):
        """ Create data for VASP processing """
        self.data = VaspData(dir)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
