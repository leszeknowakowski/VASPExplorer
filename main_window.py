import time

import sys
import platform
import os

tic = time.perf_counter()
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, \
    QToolBar, QAction, QFileDialog, QMenu, QSplashScreen
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5.QtCore import Qt

toc = time.perf_counter()
print(f'import PyQt5 in main: {toc - tic:0.4f}')

def get_splash():
    exec_dir = os.path.dirname(os.path.abspath(__file__))
    pix_path = os.path.join(exec_dir, 'icons', "splash.png")
    splash_pix = QPixmap(pix_path)
    splash = QSplashScreen(splash_pix)
    splash.setMask(splash_pix.mask())
    splash.setFont(QFont("Arial", 18))
    splash.show()
    splash.showMessage("Initializing...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
    return splash

STYLE_SHEET = []
LOG_FILE = os.path.join(os.path.dirname(__file__), "launch_log.txt")

class QFloatingSplitter(QSplitter):
    def __init__(self):
        super().__init__()
        self.floating_windows = []

class MainWindow(QMainWindow):
    """
    This class initialize the PyQt5 main window - bars, icons, widgets and
    all of the GUI stuff

    """
    def __init__(self, parent=None, show=True):
        """ Initialize GUI """
        print("setting splash screen")
        self.splash = get_splash()
        QMainWindow.__init__(self, parent)
        super().__init__(parent)
        self.__version__ = "0.0.1"
        #self.setStyleSheet("QMainWindow {background-color:#1e1f22;}")
        self.dir = self.set_working_dir()
        self.create_data()
        self.qmainwindow = QMainWindow()
        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        self.initUI()

    def initUI(self):
        """ initialize all GUI widgets, sets titles, toolbars, layouts, actions """
        self.splash.showMessage("loading modules", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
        tic = time.perf_counter()
        import pyqtgraph as pg
        toc = time.perf_counter()
        pg.setConfigOptions(antialias=True)
        print(f'import pyqtgraph in main: {toc - tic:0.4f}')

        tic = time.perf_counter()
        from dos_plot_widget import DosPlotWidget
        from dos_control_widget import DosControlWidget
        from structure_plot import StructureViewer
        from console_widget import ConsoleWidget
        from structure_controls import StructureControlsWidget
        from structure_variable_controls import StructureVariableControls
        from kpoints_create import  Kpoints_tab
        from chgcar_controls import ChgcarVis
        from deatachedtabs import DetachableTabWidget
        toc = time.perf_counter()
        print(f'import local modules in main: {toc - tic:0.4f}')

        self.splash.showMessage("Initializing UI", Qt.AlignBottom| Qt.AlignCenter, Qt.black)
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
        open_action.triggered.connect(self.load_data)

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
        move_atoms_window = QAction("Move atoms", self)

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
        modify_menu.addAction(move_atoms_window)

        view_menu = menubar.addMenu('View')
        actors_menu = QMenu("Actors", self)
        view_menu.addMenu(actors_menu)
        clear_bonds_menu_action = QAction("Clear Bonds", self)
        actors_menu.addAction(clear_bonds_menu_action)

        # main layout
        splitter = QFloatingSplitter()
        main_layout.addWidget(splitter)

        # Left tabs for plots
        left_tab_widget = DetachableTabWidget()

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

        # tab for controlling the charge density plots
        self.chgcar_control_widget = ChgcarVis(self.structure_plot_control_tab.plotter)
        self.chgcar_control_widget.chg_file_path = os.path.join(self.dir, "CHGCAR")
        #self.chgcar_control_widget.chg_file_path = "D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\Vacancy\\CeO2_100_CeO4-t\\CeO2_100_CeO4-t_asymmetric\\2VOa"
        structure_tabs.addTab(self.chgcar_control_widget, "PARCHG/CHGCAR")

        right_tab_widget.addTab(structure_tabs, "Crystal structure")
        structure_tabs.setCurrentIndex(1)

        # tab for controlling the input parameters
        input_tab = QTabWidget()
        right_tab_widget.addTab(input_tab, "Input")

        kpoint_tab = Kpoints_tab(self.structure_plot_interactor_widget)
        input_tab.addTab(kpoint_tab, "Kpoints")



        right_tab_widget.setCurrentIndex(1)


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
        move_atoms_window.triggered.connect(self.structure_variable_control_tab.move_atoms_widget)
        clear_bonds_menu_action.triggered.connect(self.structure_plot_control_tab.clear_bond_labels)


        # self.console_widget = ConsoleWidget()
        # main_layout.addWidget(self.console_widget)
        # self.console_widget.setFixedHeight(100)

    def log_program_launch(self):
        import os
        import csv
        from datetime import datetime
        import getpass

        # Get current time and user
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = getpass.getuser()

        # Check if log file exists
        file_exists = os.path.isfile(LOG_FILE)

        # Open the file in append mode
        try:
            with open(LOG_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                # Write header if file is new
                if not file_exists:
                    writer.writerow(["Timestamp", "User"])
                # Log the launch
                writer.writerow([timestamp, user])

            # Optional: count total launches so far
            with open(LOG_FILE, "r") as f:
                total = sum(1 for line in f) - 1  # exclude header
                print(f"This program has been launched {total} times.")
        except Exception as e:
            print(f"Error logging launch: {e}")

    def create_data(self):
        self.splash.showMessage("loading data...",Qt.AlignBottom | Qt.AlignCenter, Qt.black)
        from vasp_data import VaspData
        dir = self.set_working_dir()
        self.data = VaspData(dir)

    def set_working_dir(self):
        """ gets the current working dir. Useful for building"""
        if platform.system() == 'Linux':
            dir = './'
        elif platform.system() == 'Windows':
            cwd = os.getcwd()
            files_to_check = ['CONTCAR', 'POSCAR', 'OUTCAR']

            if any(os.path.isfile(os.path.join(cwd, fname)) for fname in files_to_check):
                dir = cwd
            else:
                #dir = ("D:\\syncme\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98")
                dir = ("D:\\syncme\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt")
                #dir = "D:\\syncme\\test_for_doswizard\\9.CHGCAR\\1.spinel_spinupdown"
                #dir = r"D:\syncme\modelowanie DFT\lobster_tests\Si\Si"
                #dir = r"D:\syncme\test_for_doswizard\9.CHGCAR\1.spinel_spinupdown"
                #dir = r"D:\syncme\modelowanie DFT\1.interface\2.interface_3x3\34.co3o4_3x3_ceria_mlff"

                #dir = "C:\\Users\\lesze\\OneDrive\\Materials Studio Projects\\interfaceCo3O4_CeO2_Files\\Documents\\interface\\Co3o4 3x3\\v4_with_mlff_ceria\\spinel_3x3_supercell CASTEP Energy"
            #print("can't resolve operating system")
            self.dir = dir
        return dir

    def set_window_title(self, path):
        abs_path = os.path.abspath(path)
        parts = abs_path.strip(os.sep).split(os.sep)
        # Join the last 6 components
        last_6_dirs = os.sep.join(parts[-6:])
        self.setWindowTitle("VASPy-vis v. " + self.__version__ + ": " +last_6_dirs)

    def load_data(self):
        """Open a directory and reload all VASP data from it, updating the GUI."""
        from vasp_data import VaspData
        default_dir = self.dir
        #default_dir = r'D:\syncme\modelowanie DFT\co3o4_new_new\0.bulk\scale_0.9900'
        selected_file = QFileDialog.getOpenFileName(self,
                                                        "Select file in directory with VASP Files",
                                                        default_dir)
        selected_dir = os.path.dirname(selected_file[0])
        if not selected_dir:
            return  # user cancelled

        #try:
        if True:
            # Load new data
            self.data = VaspData(selected_dir)

            # Update plot widgets
            self.dos_plot_widget.update_data(self.data)
            self.dos_control_widget.update_data(self.data)
            self.structure_plot_interactor_widget.update_data(self.data)
            self.structure_plot_control_tab.update_data()
            self.structure_variable_control_tab.update_data()
            self.chgcar_control_widget.update_data(self.data)
            #self.chgcar_control_widget.chg_file_path = os.path.join(selected_dir, "CHGCAR")

            self.dir = selected_dir
            self.set_window_title(self.dir)

        #except Exception as e:
        #QMessageBox.critical(self, "Error Loading Data", str(e))
        #print(e)

if __name__ == '__main__':
    tic = time.perf_counter()
    app = QApplication(sys.argv)

    window = MainWindow()
    window.log_program_launch()
    window.set_window_title(window.dir)
    toc = time.perf_counter()
    print(f'Execution time: {toc - tic:0.4f} seconds')
    window.splash.close()
    window.show()
    sys.exit(app.exec_())
