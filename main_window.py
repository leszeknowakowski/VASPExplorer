import time

if True:  # noqa: E402
    tic = time.perf_counter()
    import sys
    toc = time.perf_counter()
    print(f'import sys in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, QPlainTextEdit
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
    toc = time.perf_counter()
    print(f'import neighbour widgets in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from console_widget import ConsoleWidget
    toc = time.perf_counter()
    print(f'import console_widget in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import platform
    toc = time.perf_counter()
    print(f'import platform in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import os
    toc = time.perf_counter()
    print(f'import os in main: {toc - tic:0.4f}')

pg.setConfigOptions(antialias=True)

class MainWindow(QMainWindow):
    '''main window class'''
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
        self.structure_plot_widget = StructureViewer(self.data)
        left_tab_widget.addTab(self.dos_plot_widget, "DOS")
        left_tab_widget.addTab(self.structure_plot_widget, "Structure")  # Placeholder for future widget
        left_tab_widget.addTab(QWidget(), "PARCHG/CHGCAR")  # Placeholder for future widget
        splitter.addWidget(left_tab_widget)

        # Right tabs for GUI
        right_tab_widget = QTabWidget()
        self.dos_control_widget = DosControlWidget(self.data, self.dos_plot_widget)
        right_tab_widget.addTab(self.dos_control_widget, "Parameters")
        right_tab_widget.addTab(QWidget(), "Structure list")  # Placeholder for future widget
        splitter.addWidget(right_tab_widget)
        splitter.setStretchFactor(0,5)
        splitter.setStretchFactor(1,10)

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
                #dir = ("D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98")
                dir = ("D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\Adsorption\\CeO2_100_CeO4-t\\CO\\O1_site")
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
    print("ended")
    print('wtf')
