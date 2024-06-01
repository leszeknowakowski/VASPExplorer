import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, QPlainTextEdit
from PyQt5 import QtCore
import pyqtgraph as pg
from vasp_data import VaspData
from dos_plot_widget import DosPlotWidget
from parameter_widget import ParameterWidget
from console_widget import ConsoleWidget
import platform
import os

pg.setConfigOptions(antialias=True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.create_data()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('DOSWave v.0.0.0')
        self.resize(1400, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        splitter = QSplitter()
        main_layout.addWidget(splitter)

        # Left tabs for plots
        left_tab_widget = QTabWidget()
        self.dos_plot_widget = DosPlotWidget(self.data)
        left_tab_widget.addTab(self.dos_plot_widget, "DOS")
        left_tab_widget.addTab(QWidget(), "Structure")  # Placeholder for future widget
        left_tab_widget.addTab(QWidget(), "PARCHG/CHGCAR")  # Placeholder for future widget
        splitter.addWidget(left_tab_widget)

        # Right tabs for GUI
        right_tab_widget = QTabWidget()
        self.parameter_widget = ParameterWidget(self.data, self.dos_plot_widget)
        right_tab_widget.addTab(self.parameter_widget, "Parameters")
        right_tab_widget.addTab(QWidget(), "Structure list")  # Placeholder for future widget
        splitter.addWidget(right_tab_widget)

        self.console_widget = ConsoleWidget()
        main_layout.addWidget(self.console_widget)
        self.console_widget.setFixedHeight(100)

    def create_data(self):
        if platform.system() == 'Linux':
            dir = './'
        elif platform.system() == 'Windows':
            path = "F:\\syncme\\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98"
            if os.path.isdir(path):
                dir = path
            else:
                dir = ("D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98")

            #self.data = VaspData("D:\\OneDrive - Uniwersytet Jagielloński\\modelowanie DFT\\czasteczki\\O2")
            #self.data = VaspData("D:\\OneDrive - Uniwersytet Jagielloński\\modelowanie DFT\\co3o4_new_new\\2.ROS\\1.large_slab\\1.old_random_mag\\6.CoO-O_CoO-O\\antiferro\\HSE\\DOS_new")
        else:
            print("can't resolve operating system. Please Leszek, write your code only on Windows or Linux")
        self.data = VaspData(dir)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
