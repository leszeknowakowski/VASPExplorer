from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QScrollArea, QFrame, QPushButton, QGridLayout, QPlainTextEdit
from PyQt5 import QtCore
import pyqtgraph as pg
import numpy as np


class DosControlWidget(QWidget):
    """class for controlling the DOS plot
    Attributes:
    data:
        VaspData object
    plot_widget:
        DosPlotWidget object
    saved_plots:
        list of saved plots
    saved_labels:
        list of saved plot labels
    saved_colors
        list of saved plot colors
    """
    def __init__(self, data, plot_widget):
        """initialize"""
        super().__init__()
        self.plot_widget = plot_widget
        self.data = data
        self.reset_variables()

        self.initUI()

    def initUI(self):
        "initialize UI"
        layout = QHBoxLayout(self)
        self.init_dos_orbitals_atoms_tab(layout)

    def reset_variables(self):
        self.saved_plots = []
        self.saved_labels = []
        self.saved_colors = []
        self.atom_checkboxes = []
        self.orbital_checkboxes = []

    def update_data(self, data):
        """
        updates data when new file is opened
        """
        self.data = data
        self.reset_variables()

        self.create_checkboxes(self.data.atoms_symb_and_num, self.atom_checkboxes, self.scroll_left_layout)
        self.create_checkboxes(self.data.orbitals, self.orbital_checkboxes, self.scroll_right_layout)

        self.add_orbital_buttons()
        self.add_atom_buttons()

    def init_dos_orbitals_atoms_tab(self, layout):
        """
        Initialize dos orbitals tab
        Parameters:
        layout
            QHBoxLayout from initUI
        """
        self.atom_scroll_area(layout)
        self.create_checkboxes(self.data.atoms_symb_and_num, self.atom_checkboxes, self.scroll_left_layout)
        self.orbitals_scroll_area(layout)
        self.create_checkboxes(self.data.orbitals, self.orbital_checkboxes, self.scroll_right_layout)
        self.add_all_buttons()

    def atom_scroll_area(self, layout):
        """
        Initialize scroll area widget for atoms
        """
        #area widget
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QHBoxLayout(self.scroll_area_widget)

        # checkboxes
        self.checkboxes_widget = QWidget()
        self.scroll_left_layout = QVBoxLayout(self.checkboxes_widget)
        self.scroll_left_layout.setAlignment(QtCore.Qt.AlignTop)

        # scroll area for atoms
        self.scroll_area_left = QScrollArea()
        self.scroll_area_left.setWidgetResizable(True)
        self.scroll_area_left.setWidget(self.checkboxes_widget)
        self.scroll_area_left.setFrameShape(QFrame.NoFrame)
        self.scroll_area_layout.addWidget(self.scroll_area_left)

        label = QLabel("atoms:")
        self.scroll_left_layout.addWidget(label)

    def create_checkboxes(self, label_list, checkboxes_list, layout):
        """
        Create checkboxes widget

        Parameters:
        label_list
            list of labels for checkboxes label
        checkboxes_list
            list of all checkboxes widgets
        layout
            layout to add checkboxes widget to
        """
        checkboxes_list.clear()
        self.clearLayout(layout)
        # add appropiate number of checkboxes
        for i in range(len(label_list)):
            checkbox = QCheckBox(label_list[i])
            checkbox.stateChanged.connect(self.checkbox_changed)
            checkboxes_list.append(checkbox)
            layout.addWidget(checkbox)

    def orbitals_scroll_area(self, layout):
        """
        Initialize scroll area for orbitals
        """
        self.scroll_right_widget = QWidget()
        self.scroll_right_layout = QVBoxLayout(self.scroll_right_widget)
        self.scroll_right_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scroll_area_right = QScrollArea()
        self.scroll_area_right.setWidgetResizable(True)
        self.scroll_area_right.setWidget(self.scroll_right_widget)
        self.scroll_area_right.setFrameShape(QFrame.NoFrame)
        self.scroll_area_layout.addWidget(self.scroll_area_right)

        label = QLabel("orbitals:")
        self.scroll_right_layout.addWidget(label)

        layout.addWidget(self.scroll_area_widget)
        
    def add_buttons(self, layout, data, callout, type="orbital"):
        """
        Create a buttons for atoms and orbitals.
        Parameters:
        layout : PyQt5.QtWidgets.QLayout
            Layout to add buttons to
        data : list
            list of labels to create buttons for
        callout
            function called when button is clicked
        """
        self.clearLayout(layout)
        for i, list in enumerate(data):
            if type == "orbital":
                label = list[0] if len(list) == 1 else list[0][0]
            elif type == "atom":
                label = list
            btn = QPushButton(f"{callout.__name__.split("_")[0]} {label}", self)
            btn.clicked.connect(lambda _, x=i: callout(x))
            layout.addWidget(btn)
            
    def add_all_buttons(self):
        """
        Initialize all buttons connected to DOS plots
        """
        self.all_btns_layout = QVBoxLayout()
        self.scroll_area_layout.addLayout(self.all_btns_layout)

        self.btn_orb_layout = QHBoxLayout()
        self.btn_atoms_layout = QHBoxLayout()
        self.all_btns_layout.addLayout(self.btn_orb_layout)
        self.all_btns_layout.addLayout(self.btn_atoms_layout)

        self.select_orbital_layout = QVBoxLayout()
        self.deselect_orbital_layout = QVBoxLayout()
        self.select_atom_layout = QVBoxLayout()
        self.deselect_atom_layout = QVBoxLayout()

        self.add_orbital_buttons()
        self.add_atom_buttons()
        self.add_plotting_control_buttons()

    def add_orbital_buttons(self):
        """
        Add buttons for controlling orbitals selection
        """
        self.clearLayout(self.select_orbital_layout)
        self.clearLayout(self.deselect_orbital_layout)
        self.add_buttons(self.select_orbital_layout, self.data.orbital_types, self.select_orbital)
        self.add_buttons(self.deselect_orbital_layout, self.data.orbital_types, self.deselect_orbital)

        select_all_btn = QPushButton("select all", self)
        select_all_btn.clicked.connect(self.select_all_orbitals)
        self.select_orbital_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect all", self)
        deselect_all_btn.clicked.connect(self.deselect_all_orbitals)
        self.deselect_orbital_layout.addWidget(deselect_all_btn)

        self.btn_orb_layout.addLayout(self.select_orbital_layout)
        self.btn_orb_layout.addLayout(self.deselect_orbital_layout)

    def add_atom_buttons(self):
        """
        Add buttons for controlling atoms selection
        """
        self.add_buttons(self.select_atom_layout, self.data.atomic_symbols, self.select_atom, type="atom")
        self.add_buttons(self.deselect_atom_layout, self.data.atomic_symbols, self.deselect_atom, type="atom")

        select_all_atoms_btn = QPushButton("Select all", self)
        select_all_atoms_btn.clicked.connect(self.select_all_atoms)
        self.select_atom_layout.addWidget(select_all_atoms_btn)

        deselect_all_atoms_btn = QPushButton("Deselect all", self)
        deselect_all_atoms_btn.clicked.connect(self.deselect_all_atoms)
        self.deselect_atom_layout.addWidget(deselect_all_atoms_btn)

        self.btn_atoms_layout.addLayout(self.select_atom_layout)
        self.btn_atoms_layout.addLayout(self.deselect_atom_layout)
        self.scroll_area_layout.addLayout(self.all_btns_layout)

    def add_plotting_control_buttons(self):
        """
        Add buttons for plotting controls - add, remove, change color
        """
        self.additional_button_layout = QGridLayout()
        self.color_button = pg.ColorButton()
        self.color_button.setColor('r')
        self.additional_button_layout.addWidget(self.color_button, 0, 0)

        self.plot_merged_btn = QPushButton("Plot merged", self)
        self.additional_button_layout.addWidget(self.plot_merged_btn, 0, 1)
        self.plot_merged_btn.clicked.connect(self.plot_merged)

        self.plot_total_dos_btn = QPushButton("total DOS")
        self.additional_button_layout.addWidget(self.plot_total_dos_btn, 1, 0)
        self.plot_total_dos_btn.clicked.connect(self.plot_total_dos)

        self.save_plots_btn = QPushButton("Save plots")
        self.additional_button_layout.addWidget(self.save_plots_btn,1, 1)
        self.save_plots_btn.clicked.connect(self.save_merged_plot)

        self.show_saved_plot_btn = QPushButton("show saved plots")
        self.additional_button_layout.addWidget(self.show_saved_plot_btn,2,0)
        self.show_saved_plot_btn.clicked.connect(self.show_saved_plot)

        self.clear_merged_plot_btn = QPushButton("Clear plots")
        self.additional_button_layout.addWidget(self.clear_merged_plot_btn,2,1)
        self.clear_merged_plot_btn.clicked.connect(self.clear_merged_plot)

        self.all_btns_layout.addLayout(self.additional_button_layout)

    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget() is not None:
                    child.widget().deleteLater()
                elif child.layout() is not None:
                    clearLayout(child.layout())

    def update_checkboxes(self, orbitals, check):
        """update orbital checkboxes
        Parameters:
        orbitals
            type of orbital from data
        check
            signal of checking/unchecking
        """
        # Block signals to avoid multiple updates
        for checkbox in self.orbital_checkboxes:
            checkbox.blockSignals(True)
            if checkbox.text() in orbitals:
                checkbox.setChecked(check)
            checkbox.blockSignals(False)
        # Update orbital_up once after all changes
        self.checkbox_changed()

    def update_atom_checkboxes(self, atom, check):
        """update atom checkboxes
        Parameters:
        orbitals
            type of orbital from data
        check
            signal of checking/unchecking
        """
        # block signals

        for checkbox in self.atom_checkboxes:
            checkbox.blockSignals(True)
            checkbox_text = checkbox.text()
            for element in atom:
                splitted = element.split("_")
                length = len(splitted)
                if length > 2:
                    many_splitted = element.rsplit("_", length - 2)
                    many_joined = "".join(many_splitted)
                else:
                    many_joined = "".join(splitted)
                if checkbox_text in many_joined:
                    checkbox.setChecked(check)
            checkbox.blockSignals(False)
        # update atom_up
        self.checkbox_changed()

    def select_atom(self, index):
        self.update_atom_checkboxes(self.data.partitioned_lists[index], True)

    def deselect_atom(self, index):
        self.update_atom_checkboxes(self.data.partitioned_lists[index], False)

    def select_all_atoms(self):
        flatten = [element for sublist in self.data.partitioned_lists for element in sublist]
        self.update_atom_checkboxes(flatten, True)

    def deselect_all_atoms(self):
        flatten = [element for sublist in self.data.partitioned_lists for element in sublist]
        self.update_atom_checkboxes(flatten, False)

    def select_orbital(self, index):
        self.update_checkboxes(self.data.orb_types[index], True)
        print(f"Selected: {self.orbital_up}")

    def deselect_orbital(self, index):
        self.update_checkboxes(self.data.orb_types[index], False)
        print(f"Deselected: {self.orbital_up}")

    def select_all_orbitals(self):
        all_orbitals = [orb for sublist in self.data.orb_types for orb in sublist]
        self.update_checkboxes(all_orbitals, True)
        print(f"Selected All: {self.orbital_up}")

    def deselect_all_orbitals(self):
        all_orbitals = [orb for sublist in self.data.orb_types for orb in sublist]
        self.update_checkboxes(all_orbitals, False)
        print("Deselected All")

    def update_indexes(self):
        """store the indexes of selected atoms and orbitals"""
        self.selected_atoms = [i for i, cb in enumerate(self.atom_checkboxes) if cb.isChecked()]
        self.selected_orbitals = [i for i, cb in enumerate(self.orbital_checkboxes) if cb.isChecked()]

    def checkbox_changed(self):
        """function to update values when checkbox is checked/unchecked"""
        self.update_indexes()
        self.update_plot()
        self.orbital_up = [checkbox.text() for checkbox in self.orbital_checkboxes if checkbox.isChecked()]
        self.atoms_up = [checkbox.text() for checkbox in self.atom_checkboxes if checkbox.isChecked()]

    def parameter_changed(self, param, changes):
        for param, change, data in changes:
            path = self.param.childPath(param)
            if path:
                child_name = '.'.join(path)
                print(f'{child_name}: {data}')
                # Update plot with new data based on changed parameters
                self.update_plot()

    def update_plot(self):
        """update the DOS plot"""
        self.plot_widget.update_plot(self.data, self.selected_atoms, self.selected_orbitals)

    def plot_merged(self):
        """plot the merged DOS for all selected atoms and orbitals"""
        lbl = self.create_label()
        color = self.color_button.color()
        self.saved_labels.append(lbl)
        self.saved_colors.append(color)
        self.plot_widget.plot_merged(self.selected_atoms,
                                     self.selected_orbitals,
                                     self.data.doscar.total_dos_energy,
                                     self.saved_labels[-1],
                                     color)
        self.color_button.setColor(np.random.random(3)*255)


    def plot_total_dos(self):
        """plot total DOS"""
        dataset_up = self.data.total_alfa
        dataset_down = self.data.total_beta
        self.plot_widget.update_total_dos_plot(dataset_up, dataset_down, self.data.doscar.total_dos_energy)

    def create_label(self):
        """create label"""
        lbl = self.plot_widget.create_label(self.orbital_up, self.orbital_up, self.atoms_up, self.atoms_up)
        return lbl

    def save_merged_plot(self):
        """save merged plot to a save list"""
        plot_items = int(len(self.plot_widget.bounded_plot.plotItem.curves))
        data_up = self.plot_widget.bounded_plot.plotItem.curves[-2].getData()[0]
        data_down = self.plot_widget.bounded_plot.plotItem.curves[-1].getData()[0]
        lbl = self.saved_labels[-1]
        color = self.saved_colors[-1]
        self.saved_plots.append((data_up, data_down, lbl, color))

    def show_saved_plot(self):
        """show saved plots"""
        self.plot_widget.show_all_saved_plots(self.saved_plots, self.data.doscar.total_dos_energy)

    def clear_merged_plot(self):
        """clear all saved plots"""
        self.plot_widget.clear_merged_plot()
        self.saved_plots = []



