import time

import sys
import platform
import os

from console_widget import PythonConsole

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'third_party'))

from config import AppConfig
AppConfig.load()
tic = time.perf_counter()
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget, \
    QToolBar, QAction, QFileDialog, QMenu, QSplashScreen, QLabel, QStyleFactory, QDialog
from PyQt5.QtGui import QIcon, QPixmap, QFont, QPalette, QColor
from PyQt5.QtCore import Qt, QTimer, QEvent
from STYLE_SHEET import *

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
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_counter = 0
        self.shift_pressed = False
        self.initUI()

    def initUI(self):
        """ initialize all GUI widgets, sets titles, toolbars, layouts, actions """
        self.splash.showMessage("loading modules", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
        tic = time.perf_counter()
        import pyqtgraph as pg
        toc = time.perf_counter()
        pg.setConfigOptions(antialias=True)
        print(f'import pyqtgraph in main: {toc - tic:0.4f}')

        self.splash.showMessage("Initializing UI", Qt.AlignBottom| Qt.AlignCenter, Qt.black)
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons", "logo_small.png")))
        self.resize(1400, 1000)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.horizontal_splitter = QSplitter(Qt.Vertical)
        self.horizontal_splitter.setStretchFactor(0, 2)
        self.horizontal_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self.horizontal_splitter)

        self.create_main_layout(self.horizontal_splitter)
        self.create_toolbar()
        self.create_menubar()
        self.create_python_console()
        self.create_status_bar()
        self.set_styles()

        # add geometry buttons and slider to toolbar
        self.toolbar.addWidget(self.structure_plot_control_tab.start_geometry_button)
        self.toolbar.addWidget(self.structure_plot_control_tab.back_geometry_button)
        self.toolbar.addWidget(self.structure_plot_control_tab.next_geometry_button)
        self.toolbar.addWidget(self.structure_plot_control_tab.end_geometry_button)
        self.toolbar.addWidget(self.structure_plot_control_tab.geometry_slider)


    def set_styles(self):
        self.styles = styles
        self.console_font_colors = console_font_colors
        self.plotter_colors = plotter_colors
        self.brush_colors = brush_colors
        self.pen_colors = pen_colors
        self.current_style = 0
        self.apply_style(self.current_style)

    def create_toolbar(self):
        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        # Toolbar Actions
        icon_path = os.path.join(self.exec_dir, 'icons')

        right_action = QAction(QIcon(os.path.join(icon_path, "right_arrow.png")), "Move atoms to the right", self)
        left_action = QAction(QIcon(os.path.join(icon_path, "left-arrow.png")), "Move atoms to the left", self)
        down_action = QAction(QIcon(os.path.join(icon_path, "down-arrow.png")), "Move atoms down", self)
        up_action = QAction(QIcon(os.path.join(icon_path, "up-arrow.png")), "Move atoms up", self)
        in_action = QAction(QIcon(os.path.join(icon_path, "in-plane.png")), "Move atoms towards screen", self)
        out_action = QAction(QIcon(os.path.join(icon_path, "out-of-plane.png")), "Move atoms away from screen", self)
        delete_action = QAction(QIcon(os.path.join(icon_path, "delete.png")), "delete atoms", self)
        add_action = QAction(QIcon(os.path.join(icon_path, "add.png")), "add atoms", self)
        render_bond_distance_action = QAction(QIcon(os.path.join(icon_path, "add_bond.png")), "Bond distance", self)

        right_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='right'))
        left_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='left'))
        down_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='down'))
        up_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction='up'))
        in_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction="out"))
        out_action.triggered.connect(lambda: self.structure_variable_control_tab.translate_object(direction="in"))
        delete_action.triggered.connect(self.structure_variable_control_tab.delete_atoms)
        add_action.triggered.connect(self.structure_variable_control_tab.add_atom)
        render_bond_distance_action.triggered.connect(self.structure_variable_control_tab.add_bond_length)

        # Add action to toolbar
        actions = [right_action, left_action, down_action, up_action, in_action, out_action, delete_action, add_action, render_bond_distance_action]
        self.toolbar.addActions(actions)

    def create_menubar(self):
        # menu bar
        menubar = self.menuBar()
        icon_path = os.path.join(self.exec_dir, 'icons')
        new_action = QAction(QIcon(os.path.join(icon_path, "new.png")), "New", self)
        new_action.setShortcut('Ctrl+N')
        open_action = QAction(QIcon(os.path.join(icon_path, "open.png")), "Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(lambda: self.load_data(self.choose_dir()))

        save_action = QAction(QIcon(os.path.join(icon_path, "save.png")), "Save", self)
        save_action.setShortcut("Ctrl+S")

        save_gif_action = QAction("Save gif", self)
        save_gif_action.triggered.connect(self.structure_plot_control_tab.save_gif)
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")

        copy_action = QAction(QIcon(os.path.join(icon_path, "copy.png")), "Copy", self)
        # copy_action.setShortcut('Ctrl+C')
        cut_action = QAction(QIcon(os.path.join(icon_path, "cut.png")), "Cut", self)
        cut_action.setShortcut("Ctrl+X")
        paste_action = QAction(QIcon(os.path.join(icon_path, "paste.png")), "Paste", self)
        paste_action.setShortcut("Ctrl+V")

        modify_constraints_action = QAction("Modify Constraints", self)
        move_atoms_window = QAction("Move atoms", self)
        clear_bonds_menu_action = QAction("Clear Bonds", self)
        view_cameras_action = QAction("View Cameras", self)
        view_convex_hull_action = QAction("View Convex Hull", self)

        save_action.triggered.connect(self.structure_variable_control_tab.save_poscar)
        copy_action.triggered.connect(self.structure_variable_control_tab.tableWidget.copy_table)
        modify_constraints_action.triggered.connect(self.structure_variable_control_tab.modify_constraints)
        move_atoms_window.triggered.connect(self.structure_variable_control_tab.move_atoms_widget)
        clear_bonds_menu_action.triggered.connect(self.structure_variable_control_tab.remove_bond_lengths)
        view_cameras_action.triggered.connect(self.structure_plot_interactor_widget.show_camera_menu)
        view_convex_hull_action.triggered.connect(self.structure_variable_control_tab.view_convex_hull)

        # Create menu items
        file_menu = menubar.addMenu('File')

        file_menu.addAction(open_action)
        file_menu.addAction(save_gif_action)
        # install later
        #file_menu.addAction(new_action)
        #file_menu.addAction(save_action)
        #file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu('Edit')

        edit_menu.addAction(copy_action)
        # install later
        #edit_menu.addAction(cut_action)
        #edit_menu.addAction(paste_action)

        modify_menu = menubar.addMenu('Modify')
        modify_menu.addAction(modify_constraints_action)
        modify_menu.addAction(move_atoms_window)

        view_menu = menubar.addMenu('View')
        actors_menu = QMenu("Actors", self)
        camera_menu = QMenu("Camera", self)
        view_menu.addMenu(actors_menu)
        view_menu.addMenu(camera_menu)
        view_menu.addAction(view_convex_hull_action)

        camera_menu.addAction(view_cameras_action)

        actors_menu.addAction(clear_bonds_menu_action)

        styles_menu = menubar.addMenu('Styles')
        change_styles_action = QAction("Change styles", self)
        styles_menu.addAction(change_styles_action)
        change_styles_action.triggered.connect(self.open_style_dialog)

    def create_python_console(self):
        self.console = PythonConsole(local_vars={'main_window': self})
        self.horizontal_splitter.addWidget(self.console)

    def create_main_layout(self, main_layout):
        from dos_plot_widget import DosPlotWidget
        from dos_control_widget import DosControlWidget
        from structure_plot import StructureViewer
        from console_widget import PythonConsole
        from structure_controls import StructureControlsWidget
        from structure_variable_controls import StructureVariableControls
        from kpoints_create import  Kpoints_tab
        from potcar import Potcar_tab
        from chgcar_controls import ChgcarVis
        from deatachedtabs import DetachableTabWidget

        # main layout
        splitter = QFloatingSplitter()
        splitter.setStretchFactor(0,2)
        splitter.setStretchFactor(1,1)
        main_layout.addWidget(splitter)

        # Left tabs for plots
        left_tab_widget = DetachableTabWidget()

        # widget for Density of States plot
        self.dos_plot_widget = DosPlotWidget(self.data)

        # widget for renderer interactor for plotting the structure
        self.structure_plot_interactor_widget = StructureViewer(self.data, self)
        self.structure_plot_interactor_widget.plotter.installEventFilter(self)

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
        self.structure_plot_control_tab = StructureControlsWidget(self.structure_plot_interactor_widget, self)
        structure_tabs.addTab(self.structure_plot_control_tab, "Structure plot control")

        # tab for controlling the crystal structure - position and properties of atoms
        self.structure_variable_control_tab = StructureVariableControls(self.structure_plot_control_tab, self)
        structure_tabs.addTab(self.structure_variable_control_tab, "structure variables control")

        # tab for controlling the charge density plots
        self.chgcar_control_widget = ChgcarVis(self.structure_variable_control_tab)
        self.chgcar_control_widget.chg_file_path = os.path.join(self.dir, "CHGCAR")
        self.chgcar_control_widget.load_data.connect(self.load_data)
        structure_tabs.addTab(self.chgcar_control_widget, "PARCHG/CHGCAR")

        right_tab_widget.addTab(structure_tabs, "Crystal structure")
        structure_tabs.setCurrentIndex(1)

        # tab for controlling the input parameters
        input_tab = QTabWidget()
        right_tab_widget.addTab(input_tab, "Input")

        kpoint_tab = Kpoints_tab(self.structure_plot_interactor_widget)
        input_tab.addTab(kpoint_tab, "Kpoints")

        potcar_tab = Potcar_tab(self.structure_variable_control_tab)
        input_tab.addTab(potcar_tab, "Potcar")

        right_tab_widget.setCurrentIndex(1)

        splitter.addWidget(right_tab_widget)
        splitter.setStretchFactor(0,1)
        splitter.setStretchFactor(1,1)

        # connections
        self.dos_control_widget.statusMessage.connect(self.show_blinking_status)
        self.dos_control_widget.request_selected.connect(self.structure_variable_control_tab.handle_request_selected)
        self.structure_variable_control_tab.selected_actors_signal.connect(self.dos_control_widget.recieve_selected)

    def create_status_bar(self):
        self.status_bar = self.statusBar()

        self.blinking_label = QLabel()
        self.status_bar.addPermanentWidget(self.blinking_label)

    def show_blinking_status(self, message):
        self.blinking_label.setText(message)
        self.blinking_label.setStyleSheet("color: red; font-weight: bold;")
        self.blinking_label.show()

        self.blink_counter = 0
        self.blink_timer.start(500)  # Blink every 500ms

    def toggle_blink(self):
        if self.blink_counter >= 10:  # 500ms * 10 = 5s
            self.blink_timer.stop()
            self.blinking_label.clear()
            return

        # Toggle visibility
        self.blinking_label.setVisible(not self.blinking_label.isVisible())
        self.blink_counter += 1


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

    def set_window_title(self, path):
        abs_path = os.path.abspath(path)
        parts = abs_path.strip(os.sep).split(os.sep)
        # Join the last 6 components
        last_6_dirs = os.sep.join(parts[-6:])
        self.setWindowTitle("VASPUI v. " + self.__version__ + ": " + last_6_dirs)

    def choose_dir(self):
        """Open a directory and reload all VASP data from it, updating the GUI."""

        default_dir = self.dir
        selected_file = QFileDialog.getOpenFileName(self,
                                                        "Select file in directory with VASP Files",
                                                        default_dir)
        selected_dir = os.path.dirname(selected_file[0])
        if not selected_dir:
            return  # user cancelled
        return selected_dir

    def load_data(self, selected_dir):
        from vasp_data import VaspData
        #try:
        if True:
            # Load new data
            self.data = VaspData(selected_dir)

            # Update widgets
            self.dos_plot_widget.update_data(self.data)
            self.dos_control_widget.update_data(self.data)
            self.structure_plot_interactor_widget.update_data(self.data)
            self.structure_plot_control_tab.update_data()
            self.structure_variable_control_tab.update_data()
            self.chgcar_control_widget.update_data(self.data)
            self.chgcar_control_widget.chg_file_path = os.path.join(selected_dir, "CHGCAR")

            self.dir = selected_dir
            self.set_window_title(self.dir)
            AppConfig.dir = selected_dir

        #except Exception as e:
        #QMessageBox.critical(self, "Error Loading Data", str(e))
        #print(e)

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Shift:
                self.shift_pressed = True
        elif event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Shift:
                self.shift_pressed = False
        return super().eventFilter(source, event)

    def open_style_dialog(self):
        dialog = StyleChooserDialog(self.styles, self.apply_style, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_index is not None:
            self.current_style = dialog.selected_index
        else:
            # Revert to original style if cancelled
            self.apply_style(self.current_style)

    def apply_style(self, index):
        """Apply style by index."""
        self.setStyleSheet(self.styles[index][1])
        self.structure_plot_interactor_widget.plotter.set_background(self.plotter_colors[index][1])
        self.console.setBackground(self.plotter_colors[index][1], self.console_font_colors[index][1])
        self.structure_plot_control_tab.energy_plot_widget.setBackground(self.plotter_colors[index][1])
        self.dos_plot_widget.full_range_plot.setBackground(self.plotter_colors[index][1])
        self.dos_plot_widget.bounded_plot.setBackground(self.plotter_colors[index][1])
        self.dos_plot_widget.region.setBrush(self.brush_colors[index][1])
        self.dos_plot_widget.region.setHoverBrush(self.brush_colors[index][1])
        self.dos_control_widget.checkboxes_widget.setStyleSheet(f"background: {self.plotter_colors[index][1]}")
        self.dos_control_widget.scroll_right_widget.setStyleSheet(f"background: {self.plotter_colors[index][1]}")

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
                #dir = ("D:\\syncme\\modelowanie DFT\\CeO2\\1.CeO2(100)\\CeO2_100_CeO4-t\\1.symmetric_small\\2.HSE large\\1.geo_opt")
                dir = "D:\\syncme\\test_for_doswizard\\9.CHGCAR\\5.chgdiff\\3.full"
                #dir = r"D:\syncme\modelowanie DFT\1.interface\2.interface_3x3\34.co3o4_3x3_ceria_mlff"
                #dir = r'D:\syncme\modelowanie DFT\2.all_from_lumi\6.interface\2.interface\1.Co3O4_3x3\4.co3o4_3x3_ceria_mlff\1.cluster_separate\1.first\1.bader'
                #dir = r'D:\syncme\test_for_doswizard\999.fast_atoms'
                #dir = r"D:\syncme\test_for_doswizard\colorful_atoms"
                #dir = r'D:\syncme\test_for_doswizard\5.only_POSCAR' # poscar with D1, D2, Ce1 etc.
                #dir = r"D:\syncme\modelowanie DFT\2.all_from_lumi\6.interface\1.precursors_and_clusters\5.larger_513"

            #print("can't resolve operating system")
            self.dir = dir
        AppConfig.dir = dir
        return dir


if __name__ == '__main__':
    tic = time.perf_counter()
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    if "PYCHARM_HOSTED" in os.environ and platform.system() == 'Linux':
        os.chdir("/net/scratch/hscra/plgrid/plglnowakowski/1.tests/2.VASPUI/1.trigonal_chgcar")
        #os.chdir("/net/scratch/hscra/plgrid/plglnowakowski/3.LUMI/6.interface/2.interface/1.Co3O4_3x3/5.After_MLFF/1.spinel_3x3_ceria_mlff/4.vacancy/1.vacancy_ceria/1.V0/2.RB/4.diff_CHGCAR/1.spinel")
    window = MainWindow()

    window.log_program_launch()
    window.set_window_title(window.dir)
    window.console.locals['app'] = app
    toc = time.perf_counter()
    print(f'Execution time: {toc - tic:0.4f} seconds')
    window.splash.close()
    window.show()
    sys.exit(app.exec_())
