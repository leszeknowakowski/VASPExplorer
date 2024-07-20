import time

if True:  # noqa: E402
    tic = time.perf_counter()
    import sys
    toc = time.perf_counter()
    print(f'import sys in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, QPlainTextEdit
    from PyQt5.QtGui import QCloseEvent
    toc = time.perf_counter()
    print(f'import PyQt5.QtWidgets in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from PyQt5 import QtCore
    toc = time.perf_counter()
    print(f'import PyQt5.QtCore in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import pyqtgraph as pg
    toc = time.perf_counter()
    print(f'import pyqtgraph in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from vasp_data import VaspData
    toc = time.perf_counter()
    print(f'import vasp_data in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from dos_plot_widget import DosPlotWidget
    toc = time.perf_counter()
    print(f'import dos_plot_widget in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from dos_control_widget import DosControlWidget
    from structure_plot import StructureViewer
    from console_widget import ConsoleWidget
    from structure_controls import StructureControlsWidget
    from structure_variable_controls import StructureVariableControls
    toc = time.perf_counter()
    print(f'import local modules in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import platform
    toc = time.perf_counter()
    print(f'import platform in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import os
    toc = time.perf_counter()
    print(f'import os in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from pyvistaqt import QtInteractor, MainWindow
    toc = time.perf_counter()
    print(f'importing pyqt from Structure, time: {toc - tic}')

    from functools import partial
pg.setConfigOptions(antialias=True)

STYLE_SHEET = """

    
QTableView {
    selection-background-color: #FFFFFF;
	background-color:#1e1f22;
	color: #cbcdd2;
	padding:20;
	border:none;
}

QFrame {
    background-color: #1e1f22;
}
    
QHeaderView::section
{
	background-color:#1e1f22;
	color: #cbcdd2;
	border-style:none;
	font-family: 'Montserrat', sans-serif;
}

QScrollBar:vertical {
    border:none;
    background: #2b2d30;
    width: 20px;
}

QScrollBar::handle:vertical {
    background: #393b40;
    min-height: 20px;
	border-radius:5;
}

QTableWidget::item {
	border-bottom:1px dashed white;
	font-family: 'Roboto', sans-serif;
}

QScrollArea{
	background-color:#1e1f22;
	color: #cbcdd2;
	border-style:none;
	font-family: 'Montserrat', sans-serif;
	border:none;
}

QScrollBar::add-line:vertical {
    border:none;
    background: #2b2d30;
    height: 0px;
    subcontrol-position: bottom;
    subcontrol-origin: margin;
}

QScrollBar::sub-line:vertical {
    border:none;
    background: #2b2d30;
    height: 0px;
    subcontrol-position: top;
    subcontrol-origin: margin;
}

QScrollBar::add-page:vertical {
	background: #2b2d30;
}

QScrollBar::sub-page:vertical {
	background: #2b2d30;
}

QTableView::item::selected {
	border-top: 1px solid #FFFFFF;
	border-bottom: 1px solid #FFFFFF;
	color: #cbcdd2;
	background-color:#393b40;
}

QTabWidget::pane {
  border: none;
  color: #cbcdd2;
  top:-1px; 
  background: #1e1f22;
} 

QTabBar::tab {
  background: #1e1f22; 
  color: #cbcdd2;
  border: none; 
  padding: 10px;
} 

QTabBar::tab:selected { 
  background: #393b40; 
  color: #cbcdd2;
  margin-bottom: -1px; 
}

"""


class MainWindow(MainWindow):
    '''main window class'''
    def __init__(self, parent=None, show=True):
        QMainWindow.__init__(self, parent)
        super().__init__(parent)
        self.setStyleSheet("QMainWindow {background-color:#1e1f22;}")
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
        self.structure_plot_interactor_widget = StructureViewer(self.data)
        left_tab_widget.addTab(self.dos_plot_widget, "DOS")
        left_tab_widget.addTab(self.structure_plot_interactor_widget, "Structure")  # Placeholder for future widget
        left_tab_widget.addTab(QWidget(), "PARCHG/CHGCAR")  # Placeholder for future widget
        splitter.addWidget(left_tab_widget)
        left_tab_widget.setCurrentIndex(0)

        # Right tabs for GUI
        right_tab_widget = QTabWidget()
        self.dos_control_widget = DosControlWidget(self.data, self.dos_plot_widget)
        right_tab_widget.addTab(self.dos_control_widget, "DOS Parameters")

        structure_tabs = QTabWidget()
        self.structure_plot_control_tab = StructureControlsWidget(self.structure_plot_interactor_widget)
        structure_tabs.addTab(self.structure_plot_control_tab, "Structure plot control")

        self.structure_variable_control_tab = StructureVariableControls(self.structure_plot_control_tab)
        structure_tabs.addTab(self.structure_variable_control_tab, "structure variables control")

        right_tab_widget.addTab(structure_tabs, "Crystal structure")  # Placeholder for future widget
        right_tab_widget.setCurrentIndex(0)

        splitter.addWidget(right_tab_widget)
        splitter.setStretchFactor(0,5)
        splitter.setStretchFactor(1,10)

        # self.console_widget = ConsoleWidget()
        # main_layout.addWidget(self.console_widget)
        # self.console_widget.setFixedHeight(100)

    def closeEvent(self, QCloseEvent):
        super().closeEvent(QCloseEvent)
        self.structure_plot_interactor_widget
        self.structure_variable_control_tab.close()


    def create_data(self):
        if platform.system() == 'Linux':
            dir = './'
        elif platform.system() == 'Windows':
            #path = "F:\\syncme\\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98"
            #path = "F:\\syncme\\modelowanie DFT\\CeO2\\Adsorption\\CeO2_100_CeO4-t\\CO\\O1_site"
            # tests for incomplete/missing files
            path = "F:\\OneDrive - Uniwersytet Jagielloński\\Studia\\python\\vasp_geo\\project_geo\\inputs"

            if os.path.isdir(path):
                dir = path
            else:
                #dir = ("D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98")
                #dir = ("D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt")
                dir = "D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\Adsorption\\CeO2_100_CeO4-t\\CO\\O1_site"
            #self.data = VaspData("D:\\OneDrive - Uniwersytet Jagielloński\\modelowanie DFT\\czasteczki\\O2")
            #self.data = VaspData("D:\\OneDrive - Uniwersytet Jagielloński\\modelowanie DFT\\co3o4_new_new\\2.ROS\\1.large_slab\\1.old_random_mag\\6.CoO-O_CoO-O\\antiferro\\HSE\\DOS_new")
        else:
            print("can't resolve operating system. lol, Please Leszek, write your code only on Windows or Linux")
        self.data = VaspData(dir)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
    print("ended")
    print('wtf')
