from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QScrollArea, QFrame, QPushButton,QGridLayout, QPlainTextEdit
from PyQt5 import QtCore
from pyqtgraph.parametertree import Parameter, ParameterTree
import pyqtgraph as pg


class ParameterWidget(QWidget):
    def __init__(self, data, plot_widget):
        super().__init__()
        self.data = data
        self.plot_widget = plot_widget
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout(self)
        '''
        self.param = Parameter.create(name='params', type='group', children=[
            {'name': 'Middle Index', 'type': 'int', 'value': 0, 'limits': (0, 15)}
        ])
        self.param_tree = ParameterTree()
        self.param_tree.setParameters(self.param, showTop=True)
        self.param.sigTreeStateChanged.connect(self.parameter_changed)
        layout.addWidget(self.param_tree)
        '''
        self.init_dos_orbitals_atoms_tab(layout)

    def init_dos_orbitals_atoms_tab(self, layout):
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QHBoxLayout(self.scroll_area_widget)

        self.checkboxes_widget = QWidget()
        self.checkboxes_layout = QVBoxLayout(self.checkboxes_widget)
        self.checkboxes_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scroll_area_left = QScrollArea()
        self.scroll_area_left.setWidgetResizable(True)
        self.scroll_area_left.setWidget(self.checkboxes_widget)
        self.scroll_area_left.setFrameShape(QFrame.NoFrame)
        self.scroll_area_layout.addWidget(self.scroll_area_left)

        label = QLabel("atoms:")
        self.checkboxes_layout.addWidget(label)

        self.atom_checkboxes = []
        for i in range(self.data.number_of_atoms):
            checkbox = QCheckBox(self.data.atoms_symb_and_num[i])
            checkbox.stateChanged.connect(self.checkbox_changed)
            self.atom_checkboxes.append(checkbox)
            self.checkboxes_layout.addWidget(checkbox)

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

        self.orbital_checkboxes = []
        for i in range(len(self.data.orbitals)):
            checkbox = QCheckBox(self.data.orbitals[i])
            checkbox.stateChanged.connect(self.checkbox_changed)
            self.orbital_checkboxes.append(checkbox)
            self.scroll_right_layout.addWidget(checkbox)

        layout.addWidget(self.scroll_area_widget)

        all_btn_layout = QVBoxLayout()
        btn_orb_layout = QHBoxLayout()
        btn_atoms_layout = QHBoxLayout()
        all_btn_layout.addLayout(btn_orb_layout)
        all_btn_layout.addLayout(btn_atoms_layout)
        layout.addLayout(all_btn_layout)

        ####################### Select ORBITALS buttons#################################################
        select_layout = QVBoxLayout()
        for i, orbital_list in enumerate(self.data.orbital_types):
            orb_letter = orbital_list[0] if len(orbital_list) == 1 else orbital_list[0][0]
            btn = QPushButton(f"select {orb_letter}", self)
            btn.clicked.connect(lambda _, x=i: self.select_orbital(x))
            select_layout.addWidget(btn)

        select_all_btn = QPushButton("select all", self)
        select_all_btn.clicked.connect(self.select_all_orbitals)
        select_layout.addWidget(select_all_btn)

        btn_orb_layout.addLayout(select_layout)

        # Deselect buttons
        deselect_layout = QVBoxLayout()
        for i, orbital_list in enumerate(self.data.orbital_types):
            orb_letter = orbital_list[0] if len(orbital_list) == 1 else orbital_list[0][0]
            btn = QPushButton(f"deselect {orb_letter}", self)
            btn.clicked.connect(lambda _, x=i: self.deselect_orbital(x))
            deselect_layout.addWidget(btn)

        deselect_all_btn = QPushButton("Deselect all", self)
        deselect_all_btn.clicked.connect(self.deselect_all_orbitals)
        deselect_layout.addWidget(deselect_all_btn)

        btn_orb_layout.addLayout(deselect_layout)

        ############################################ ATOMS ##########################################
        select_atom_layout = QVBoxLayout()
        deselect_atom_layout = QVBoxLayout()

        for i, atom_list in enumerate(self.data.atomic_symbols):
            atom_letter = atom_list
            btn = QPushButton(f"select {atom_letter}", self)
            btn.clicked.connect(lambda _, x=i: self.select_atom(x))
            select_atom_layout.addWidget(btn)

        select_all_atoms_btn = QPushButton("Select all", self)
        select_all_atoms_btn.clicked.connect(self.select_all_atoms)
        select_atom_layout.addWidget(select_all_atoms_btn)

        for i, atom_list in enumerate(self.data.atomic_symbols):
            atom_letter = atom_list
            btn = QPushButton(f"Deselect {atom_letter}", self)
            btn.clicked.connect(lambda _, x=i: self.deselect_atom(x))
            deselect_atom_layout.addWidget(btn)

        deselect_all_atoms_btn = QPushButton("Deselect all", self)
        deselect_all_atoms_btn.clicked.connect(self.deselect_all_atoms)
        deselect_atom_layout.addWidget(deselect_all_atoms_btn)

        btn_atoms_layout.addLayout(select_atom_layout)
        btn_atoms_layout.addLayout(deselect_atom_layout)
        self.scroll_area_layout.addLayout(all_btn_layout)

        ########################################## additional buttons ##################################################
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

        all_btn_layout.addLayout(self.additional_button_layout)

        ###################################### tab 3 - atom selection ##################################################
        empty_widget = QWidget()  # An empty tab



        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFixedHeight(100)

    def update_checkboxes(self, orbitals, check):
        # Block signals to avoid multiple updates
        for checkbox in self.orbital_checkboxes:
            checkbox.blockSignals(True)
            if checkbox.text() in orbitals:
                checkbox.setChecked(check)
            checkbox.blockSignals(False)
        # Update orbital_up once after all changes
        self.checkbox_changed()

    def update_atom_checkboxes(self, atom, check):
        for checkbox in self.atom_checkboxes:
            checkbox.blockSignals(True)
            if checkbox.text() in atom:
                checkbox.setChecked(check)
            checkbox.blockSignals(False)
        self.checkbox_changed()

    def select_atom(self, index):
        self.update_atom_checkboxes(self.data.partitioned_lists[index], True)

    def deselect_atom(self, index):
        self.update_atom_checkboxes(self.data.partitioned_lists[index], False)

    def select_all_atoms(self):
        self.update_atom_checkboxes(self.data.atoms_symb_and_num, True)

    def deselect_all_atoms(self):
        self.update_atom_checkboxes(self.data.atoms_symb_and_num, False)

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
        self.selected_atoms = [i for i, cb in enumerate(self.atom_checkboxes) if cb.isChecked()]
        self.selected_orbitals = [i for i, cb in enumerate(self.orbital_checkboxes) if cb.isChecked()]

    def checkbox_changed(self):
        self.update_indexes()
        self.update_plot()
        self.orbital_up = [checkbox.text() for checkbox in self.orbital_checkboxes if checkbox.isChecked()]
        self.atoms_up = [checkbox for checkbox in self.atom_checkboxes if checkbox.isChecked()]

    def parameter_changed(self, param, changes):
        for param, change, data in changes:
            path = self.param.childPath(param)
            if path:
                child_name = '.'.join(path)
                print(f'{child_name}: {data}')
                # Update plot with new data based on changed parameters
                self.update_plot()

    def update_plot(self):
        self.plot_widget.update_plot(self.data, self.selected_atoms, self.selected_orbitals)

    def plot_merged(self):
        pass

    def plot_total_dos(self):
        dataset_up = self.data.total_alfa
        dataset_down = self.data.total_beta
        self.plot_widget.update_total_dos_plot(dataset_up, dataset_down, self.data.doscar.total_dos_energy)