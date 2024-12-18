import time

if True:  # noqa: E402
    import sys

    tic = time.perf_counter()
    from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, QPlainTextEdit, \
    QToolBar, QMenuBar, QAction
    from PyQt5.QtGui import QCloseEvent, QIcon
    from PyQt5 import QtCore
    toc = time.perf_counter()
    print(f'import PyQt5.QtWidgets in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    import pyqtgraph as pg
    toc = time.perf_counter()
    print(f'import pyqtgraph in main: {toc - tic:0.4f}')

    tic = time.perf_counter()
    from vasp_data import VaspData
    from dos_plot_widget import DosPlotWidget
    from dos_control_widget import DosControlWidget
    from structure_plot import StructureViewer
    from console_widget import ConsoleWidget
    from structure_controls import StructureControlsWidget
    from structure_variable_controls import StructureVariableControls
    from chgcar_controls import ChgcarVis
    toc = time.perf_counter()
    print(f'import local modules in main: {toc - tic:0.4f}')

    import platform
    import os
    from pyvistaqt import QtInteractor, MainWindow
    from functools import partial
pg.setConfigOptions(antialias=True)

STYLE_SHEET = []

class MainWindow(MainWindow):
    """
    This class initialize the PyQt5 main window - bars, icons, widgets and
    all of the GUI stuff

    """
    def __init__(self, parent=None, show=True):
        """ Initialize GUI """
        QMainWindow.__init__(self, parent)
        super().__init__(parent)
        #self.setStyleSheet("QMainWindow {background-color:#1e1f22;}")
        self.dir = self.set_working_dir()
        self.create_data()
        self.qmainwindow = QMainWindow()
        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        self.initUI()

    def initUI(self):
        """ initialize all GUI widgets, sets titles, toolbars, layouts, actions """
        self.setWindowTitle('DOSWave v.0.0.0')
        self.resize(1400, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Toolbar Actions
        icon_path = os.path.join(self.exec_dir, 'icons')
        new_action = QAction(QIcon(os.path.join(icon_path, "new.png")), "New", self)
        new_action.setShortcut('Ctrl+N')
        open_action = QAction(QIcon(os.path.join(icon_path, "open.png")), "Open", self)
        open_action.setShortcut("Ctrl+O")
        save_action = QAction(QIcon(os.path.join(icon_path, "save.png")), "Save", self)
        save_action.setShortcut("Ctrl+S")
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")

        copy_action = QAction(QIcon(os.path.join(icon_path, "copy.png")), "Copy", self)
        #copy_action.setShortcut('Ctrl+C')
        cut_action = QAction(QIcon(os.path.join(icon_path, "cut.png")), "Cut", self)
        cut_action.setShortcut("Ctrl+X")
        paste_action = QAction(QIcon(os.path.join(icon_path, "paste.png")), "Paste", self)
        paste_action.setShortcut("Ctrl+V")

        modify_constraints_action = QAction("Modify Constraints", self)

        right_action = QAction(QIcon(os.path.join(icon_path, "right_arrow.png")), "Move atoms to the right", self)
        left_action = QAction(QIcon(os.path.join(icon_path, "left-arrow.png")), "Move atoms to the left", self)
        down_action = QAction(QIcon(os.path.join(icon_path, "down-arrow.png")), "Move atoms down", self)
        up_action = QAction(QIcon(os.path.join(icon_path, "up-arrow.png")), "Move atoms up", self)
        in_action = QAction(QIcon(os.path.join(icon_path, "in-plane.png")), "Move atoms towards screen", self)
        out_action = QAction(QIcon(os.path.join(icon_path, "out-of-plane.png")), "Move atoms away from screen", self)
        delete_action = QAction(QIcon(os.path.join(icon_path, "delete.png")), "delete atoms", self)
        add_action = QAction(QIcon(os.path.join(icon_path, "add.png")), "add atoms", self)
        render_bond_distance_action = QAction(QIcon(os.path.join(icon_path, "add_bond.png")), "Bond distance", self)
        # Add action to toolbar
        actions = [new_action, open_action, save_action, right_action, left_action, down_action, up_action, in_action, out_action, delete_action, add_action, render_bond_distance_action]
        toolbar.addActions(actions)

        # menu bar
        menubar = self.menuBar()

        # Create menu items
        file_menu = menubar.addMenu('File')

        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu('Edit')

        edit_menu.addAction(copy_action)
        edit_menu.addAction(cut_action)
        edit_menu.addAction(paste_action)

        modify_menu = menubar.addMenu('Modify')
        modify_menu.addAction(modify_constraints_action)

        splitter = QSplitter()
        main_layout.addWidget(splitter)

        # Left tabs for plots
        left_tab_widget = QTabWidget()

        # widget for Density of States plot
        self.dos_plot_widget = DosPlotWidget(self.data)

        # widget for renderer interactor for plotting the structure
        self.structure_plot_interactor_widget = StructureViewer(self.data)

        left_tab_widget.addTab(self.dos_plot_widget, "DOS")
        left_tab_widget.addTab(self.structure_plot_interactor_widget, "Structure")  # Placeholder for future widget

        splitter.addWidget(left_tab_widget)
        left_tab_widget.setCurrentIndex(1)

        # Right tabs for GUI
        right_tab_widget = QTabWidget()

        # widget for controling the DOS plot
        self.dos_control_widget = DosControlWidget(self.data, self.dos_plot_widget)
        right_tab_widget.addTab(self.dos_control_widget, "DOS Parameters")

        # topmost tab widget for all structure plot manipulations
        structure_tabs = QTabWidget()

        #tab for controlling the rendering structure plot
        self.structure_plot_control_tab = StructureControlsWidget(self.structure_plot_interactor_widget)
        structure_tabs.addTab(self.structure_plot_control_tab, "Structure plot control")

        # tab for controlling the crystal structure - position and properties of atoms
        self.structure_variable_control_tab = StructureVariableControls(self.structure_plot_control_tab)
        structure_tabs.addTab(self.structure_variable_control_tab, "structure variables control")

        right_tab_widget.addTab(structure_tabs, "Crystal structure")
        right_tab_widget.setCurrentIndex(1)
        structure_tabs.setCurrentIndex(1)

        # tab for controlling the charge density plots
        self.chgcar_control_widget = ChgcarVis(self.structure_plot_control_tab)
        self.chgcar_control_widget.chg_file_path = self.dir
        structure_tabs.addTab(self.chgcar_control_widget, "PARCHG/CHGCAR")

        splitter.addWidget(right_tab_widget)
        splitter.setStretchFactor(0,5)
        splitter.setStretchFactor(1,10)

        save_action.triggered.connect(self.structure_variable_control_tab.save_poscar)
        copy_action.triggered.connect(self.structure_variable_control_tab.tableWidget.copy_table)

        right_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='right'))
        left_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='left'))
        down_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='down'))
        up_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='up'))
        in_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction="out"))
        out_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction="in"))
        delete_action.triggered.connect(self.structure_variable_control_tab.delete_atoms)
        add_action.triggered.connect(self.structure_variable_control_tab.add_atom)
        render_bond_distance_action.triggered.connect(self.structure_plot_control_tab.add_bond_length)

        modify_constraints_action.triggered.connect(self.structure_variable_control_tab.modify_constraints)

        # self.console_widget = ConsoleWidget()
        # main_layout.addWidget(self.console_widget)
        # self.console_widget.setFixedHeight(100)

    def set_working_dir(self):
        """ gets the current working dir. Useful for building"""
        if platform.system() == 'Linux':
            dir = './'
        elif platform.system() == 'Windows':
            path = "F:\\syncme\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt"
            if os.path.isdir(path):
                dir = path
            else:
                #dir = ("D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98")
                #dir = ("F:\\syncme-from-c120\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt")
                #dir = "D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\Adsorption\\CeO2_100_CeO4-t\\CO\\O1_site"
                #dir = "D:\\syncme-from-c120\\modelowanie DFT\\lobster_tests\\Mn"
                dir = "D:\\test_fir_doswizard\\4.strange_atom_definition"
            #print("can't resolve operating system")
        return dir

    def create_data(self):
        dir = self.set_working_dir()
        self.data = VaspData(dir)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
