import time

import sys
import platform
import os

from console_widget import PythonConsole

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'third_party'))

from config import AppConfig
AppConfig.load()
tic = time.perf_counter()
from PyQt5.QtWidgets import (
    QDockWidget, QMainWindow, QSplitter,
    QToolBar, QAction, QFileDialog, QMenu, QSplashScreen, QStyleFactory, QLabel,

)
from PyQt5.QtGui import QIcon, QPixmap, QFont
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
        self.dir = self.set_working_dir()
        self._full_data_loaded = False
        self.create_data(parse_doscar=False, parse_outcar=False)
        self.qmainwindow = QMainWindow()
        self.exec_dir = os.path.dirname(os.path.abspath(__file__))
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_counter = 0
        self.shift_pressed = False
        self.dock_widgets = []
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
        central_widget.setObjectName("centralWorkspace")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QMainWindow.AllowNestedDocks |
            QMainWindow.AllowTabbedDocks |
            QMainWindow.AnimatedDocks |
            QMainWindow.GroupedDragging
        )

        self.create_main_layout(main_layout)
        self.create_python_console()
        self.create_toolbar()
        self.create_menubar()
        self.create_status_bar()
        self.set_styles()
        self.resizeDocks([self.controls_dock], [430], Qt.Horizontal)
        self.resizeDocks([self.console_dock], [220], Qt.Vertical)
        QTimer.singleShot(0, self.load_full_data_after_startup)

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
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setMovable(True)
        self.toolbar.setFloatable(True)
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
        view_menu.addSeparator()
        panels_menu = QMenu("Panels", self)
        view_menu.addMenu(panels_menu)
        for dock_widget in self.dock_widgets:
            panels_menu.addAction(dock_widget.toggleViewAction())

        camera_menu.addAction(view_cameras_action)

        actors_menu.addAction(clear_bonds_menu_action)

        styles_menu = menubar.addMenu('Styles')
        change_styles_action = QAction("Change styles", self)
        styles_menu.addAction(change_styles_action)
        change_styles_action.triggered.connect(self.open_style_dialog)

        lobster_menu = menubar.addMenu("Lobster")

        mo_action = QAction("MO Diagram", self)
        mo_action.triggered.connect(self.open_mo_diagram)

        lcfo_doscar_action = QAction("LCFO Doscar", self)
        lcfo_doscar_action.triggered.connect(self.open_lcfo_doscar)

        flow_chart_action = QAction("Flow Chart", self)
        flow_chart_action.triggered.connect(self.open_flow_chart)

        icohp_matrix_action = QAction("ICOHP Matrix Viewer", self)
        icohp_matrix_action.triggered.connect(self.open_icohp_matrix_viewer)

        cohpcar_action = QAction("COHPCAR Viewer", self)
        cohpcar_action.triggered.connect(self.open_cohpcar_viewer)

        lobster_menu.addAction(mo_action)
        lobster_menu.addAction(lcfo_doscar_action)
        lobster_menu.addAction(flow_chart_action)
        lobster_menu.addAction(icohp_matrix_action)
        lobster_menu.addAction(cohpcar_action)

    def open_mo_diagram(self):
        from lobster.mo_diagram import MODiagramView, MODiagramViewModel

        vm = MODiagramViewModel()
        self.mo_diagram_window = MODiagramView(vm)

        if self.dir:
            for file in os.listdir(self.dir):
                if "MO_Diagram" in file:
                    mo_file = os.path.join(self.dir, file)

        self.mo_diagram_window.vm.load_file(mo_file)
        self.mo_diagram_window.show()
        self.mo_diagram_window.raise_()
        self.mo_diagram_window.activateWindow()

    def open_lcfo_doscar(self):
        from lobster.LCFODOS import DosWindow
        from pathlib import Path

        self.lcfo_dos_window = DosWindow(parent=self)
        file = "DOSCAR.LCFO.lobster"
        if file in [file.name for file in Path.cwd().iterdir()]:
            self.lcfo_dos_window.load_file(file)
        self.lcfo_dos_window.resize(1200, 800)
        self.lcfo_dos_window.show()

    def open_flow_chart(self):
        from lobster.flow_chart import FlowChart

        self.flow_chart_window = FlowChart(directory=self.dir, parent=self)
        self.flow_chart_window.resize(1400, 800)
        self.flow_chart_window.show()
        self.flow_chart_window.raise_()
        self.flow_chart_window.activateWindow()

    def open_icohp_matrix_viewer(self):
        from lobster.icohp_matrix_viewer import IcohpMatrixViewer

        self.icohp_matrix_viewer_window = IcohpMatrixViewer(default_dir=self.dir, main_window=self)
        icohplist_file = os.path.join(self.dir, "ICOHPLIST.lobster")

        if os.path.isfile(icohplist_file):
            self.icohp_matrix_viewer_window.load_file(icohplist_file)

        self.icohp_matrix_viewer_window.show()
        self.icohp_matrix_viewer_window.raise_()
        self.icohp_matrix_viewer_window.activateWindow()

    def open_cohpcar_viewer(self):
        from lobster.cohpcar_viewer import open_cohpcar_window

        self.cohpcar_viewer_window = open_cohpcar_window(default_dir=self.dir)
        self.cohpcar_viewer_window.show()
        self.cohpcar_viewer_window.raise_()
        self.cohpcar_viewer_window.activateWindow()

    def create_python_console(self):
        self.console = PythonConsole(local_vars={'main_window': self})
        self.console_dock = self.create_dock_widget("Python Console", self.console, Qt.BottomDockWidgetArea)

    def create_dock_widget(self, title, widget, area):
        dock_widget = QDockWidget(title, self)
        dock_widget.setObjectName(f"{title.replace(' ', '')}Dock")
        dock_widget.setWidget(widget)
        dock_widget.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock_widget.setFeatures(
            QDockWidget.DockWidgetClosable |
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable
        )
        self.addDockWidget(area, dock_widget)
        self.dock_widgets.append(dock_widget)
        return dock_widget

    def create_main_layout(self, main_layout):
        from dos_plot_widget import DosPlotWidget
        from dos_control_widget import DosControlWidget
        from structure_plot import StructureViewer
        from structure_controls import StructureControlsWidget
        from structure_variable_controls import StructureVariableControls
        from kpoints_create import  Kpoints_tab
        from potcar import Potcar_tab
        from chgcar_controls import ChgcarVis
        from deatachedtabs import DetachableTabWidget

        # Left tabs for plots
        self.left_tab_widget = DetachableTabWidget()
        self.left_tab_widget.setObjectName("plotTabs")

        # widget for Density of States plot
        self.dos_plot_widget = DosPlotWidget(self.data)

        # widget for renderer interactor for plotting the structure
        self.structure_plot_interactor_widget = StructureViewer(self.data, self)
        self.structure_plot_interactor_widget.plotter.installEventFilter(self)

        self.left_tab_widget.addTab(self.dos_plot_widget, "DOS")
        self.left_tab_widget.addTab(self.structure_plot_interactor_widget, "Structure")
        self.left_tab_widget.setCurrentIndex(1)
        main_layout.addWidget(self.left_tab_widget)

        # Right tabs for GUI
        self.controls_tab_widget = DetachableTabWidget()
        self.controls_tab_widget.setObjectName("controlTabs")

        # widget for controling the DOS plot
        self.dos_control_widget = DosControlWidget(self.data, self.dos_plot_widget)
        self.controls_tab_widget.addTab(self.dos_control_widget, "DOS Parameters")

        # topmost tab widget for all structure plot manipulations
        self.structure_tabs = DetachableTabWidget()
        self.structure_tabs.setObjectName("structureControlTabs")

        #tab for controlling the rendering structure plot
        self.structure_plot_control_tab = StructureControlsWidget(self.structure_plot_interactor_widget, self)
        self.structure_tabs.addTab(self.structure_plot_control_tab, "Structure plot control")

        # tab for controlling the crystal structure - position and properties of atoms
        self.structure_variable_control_tab = StructureVariableControls(self.structure_plot_control_tab, self)
        self.structure_tabs.addTab(self.structure_variable_control_tab, "structure variables control")

        # tab for controlling the charge density plots
        self.chgcar_control_widget = ChgcarVis(self.structure_variable_control_tab)
        self.chgcar_control_widget.chg_file_path = os.path.join(self.dir, "CHGCAR")
        self.chgcar_control_widget.load_data.connect(self.load_data)
        self.structure_tabs.addTab(self.chgcar_control_widget, "PARCHG/CHGCAR")

        self.controls_tab_widget.addTab(self.structure_tabs, "Crystal structure")
        self.structure_tabs.setCurrentIndex(1)

        # tab for controlling the input parameters
        self.input_tab = DetachableTabWidget()
        self.input_tab.setObjectName("inputTabs")
        self.controls_tab_widget.addTab(self.input_tab, "Input")

        kpoint_tab = Kpoints_tab(self.structure_plot_interactor_widget)
        self.input_tab.addTab(kpoint_tab, "Kpoints")

        potcar_tab = Potcar_tab(self.structure_variable_control_tab)
        self.input_tab.addTab(potcar_tab, "Potcar")

        self.controls_tab_widget.setCurrentIndex(1)

        self.controls_dock = self.create_dock_widget("Controls", self.controls_tab_widget, Qt.RightDockWidgetArea)

        # connections
        self.dos_control_widget.statusMessage.connect(self.show_blinking_status)
        self.dos_control_widget.request_selected.connect(self.structure_variable_control_tab.handle_request_selected)
        self.structure_variable_control_tab.selected_actors_signal.connect(self.dos_control_widget.recieve_selected)

    def create_status_bar(self):
        self.status_bar = self.statusBar()

        self.geometry_status_label = QLabel()
        self.geometry_status_label.setObjectName("geometryStatusLabel")
        self.status_bar.addWidget(self.geometry_status_label, 1)

        self.blinking_label = QLabel()
        self.status_bar.addPermanentWidget(self.blinking_label)

        self.structure_plot_control_tab.geometry_status_changed.connect(self.update_geometry_status_label)
        self.structure_plot_control_tab.update_geometry_status()

    def update_geometry_status_label(self, message):
        self.geometry_status_label.setText(message)

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

    def create_data(self, parse_doscar=True, parse_outcar=True):
        self.splash.showMessage("loading data...",Qt.AlignBottom | Qt.AlignCenter, Qt.black)
        from vasp_data import VaspData
        dir = self.set_working_dir()
        self.data = VaspData(dir, parse_doscar=parse_doscar, parse_outcar=parse_outcar)

    def load_full_data_after_startup(self):
        """
        Parse full DOS/OUTCAR data after initial paint to improve perceived startup.
        """
        if self._full_data_loaded:
            return
        self.splash.showMessage("Loading full data...", Qt.AlignBottom | Qt.AlignCenter, Qt.black)
        self.load_data(self.dir, parse_doscar=True, parse_outcar=True)
        self._full_data_loaded = True

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

    def load_data(self, selected_dir, parse_doscar=True, parse_outcar=True):
        from vasp_data import VaspData
        #try:
        if True:
            # Load new data
            self.data = VaspData(selected_dir, parse_doscar=parse_doscar, parse_outcar=parse_outcar)

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
        style_sheet = self.styles[index][1]
        self.setStyleSheet(style_sheet)
        self.apply_style_to_detached_tabs(style_sheet)
        self.structure_plot_interactor_widget.plotter.set_background(self.plotter_colors[index][1])
        self.console.setBackground(self.plotter_colors[index][1], self.console_font_colors[index][1])
        self.structure_plot_control_tab.energy_plot_widget.setBackground(self.plotter_colors[index][1])
        self.dos_plot_widget.full_range_plot.setBackground(self.plotter_colors[index][1])
        self.dos_plot_widget.bounded_plot.setBackground(self.plotter_colors[index][1])
        self.dos_plot_widget.region.setBrush(self.brush_colors[index][1])
        self.dos_plot_widget.region.setHoverBrush(self.brush_colors[index][1])
        self.dos_control_widget.checkboxes_widget.setStyleSheet(f"background: {self.plotter_colors[index][1]}")
        self.dos_control_widget.scroll_right_widget.setStyleSheet(f"background: {self.plotter_colors[index][1]}")

    def apply_style_to_detached_tabs(self, style_sheet):
        detachable_tabs = (
            self.left_tab_widget,
            self.controls_tab_widget,
            self.structure_tabs,
            self.input_tab,
        )
        for tab_widget in detachable_tabs:
            tab_widget.setDetachedTabsStyleSheet(style_sheet)

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
                #dir = "D:\\syncme\\test_for_doswizard\\9.CHGCAR\\5.chgdiff\\3.full"
                #dir = r"D:\syncme\modelowanie DFT\2.all_from_lumi\3.Co3O4\2.deep_reduction\4.3rd_4th_electron_transfer\2.acidic\1.without_spectator\1.1H\2.HSE\4.Bader_DOS\00"
                dir = r"D:\syncme\test_for_doswizard\9999.many_atoms_lobster"

            self.dir = dir
        AppConfig.dir = dir
        return dir


if __name__ == '__main__':
    tic = time.perf_counter()
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    if "PYCHARM_HOSTED" in os.environ and platform.system() == 'Linux':
        os.chdir("/net/scratch/hscra/plgrid/plglnowakowski/1.tests/2.VASPUI/4.lobster")

    window = MainWindow()

    window.log_program_launch()
    window.set_window_title(window.dir)
    window.console.locals['app'] = app
    toc = time.perf_counter()
    print(f'Execution time: {toc - tic:0.4f} seconds')
    window.splash.close()
    window.show()
    sys.exit(app.exec_())
