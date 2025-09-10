import time

tic = time.perf_counter()
try:
    from ase.io import read, write
    toc = time.perf_counter()
    print(f'import ase in vaspdata: {toc - tic:0.4f}')
except:
    print("no ASE module")
import os
import sys
from VASPparser import *
import json
from exceptions import EmptyFile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'third_party'))
from pymatgen.io.lobster import Doscar

class VaspData():
    def __init__(self, dir, parse_doscar=True):
        outcar = self.parse_outcar(dir)
        poscar = self.parse_poscar(dir)
        if parse_doscar:
            doscar = self.parse_doscar(dir)
            self.process_doscar()
        self.process_poscar(poscar)
        self.parse_doscar_lobster(dir)

    def parse_outcar(self, dir):
        if not os.path.exists(os.path.join(dir, 'OUTCAR')):
            print('no OUTCAR found! importing CONTCAR or POSCAR')
            self.outcar_file = False
        else:
            self.outcar_file = True
            self.outcar_data = OutcarParser(dir, 'OUTCAR')
            self.outcar_coordinates = self.outcar_data.find_coordinates()
            self.outcar_energies = self.outcar_data.find_energy()
            self.magmoms = self.outcar_data.magmoms
            self.scf_energies = self.outcar_data.find_scf_energies()

    def parse_poscar(self, dir):
        if not os.path.exists(os.path.join(dir, 'CONTCAR')) and not os.path.exists(os.path.join(dir, 'POSCAR')):
            for file in os.listdir(dir):
                # Check if the file has a .cell extension
                if file.endswith(".cell"):
                    # Read the .cell file
                    structure = read(os.path.join(dir,file))
                    write(os.path.join(dir,"POSCAR"), structure, format="vasp")

        if not os.path.exists(os.path.join(dir, 'CONTCAR')):
            if not os.path.exists(os.path.join(dir, 'POSCAR')):
                p = input("eneter file name: ")
                if not os.path.exists(p):
                    raise FileNotFoundError('No important files found! Missing POSCAR')
                else:
                    self.poscar = PoscarParser(p)
                    self.coordinates = self.poscar.coordinates()
                    if not self.outcar_file:
                        self.outcar_coordinates = [self.poscar.coordinates()]
                        self.outcar_energies = [0]
                        self.magmoms = self.poscar.number_of_atoms() * [0]

            else:
                self.poscar = PoscarParser(os.path.join(dir, 'POSCAR'))
                self.coordinates = self.poscar.coordinates()
                if not self.outcar_file:
                    self.outcar_coordinates = [self.poscar.coordinates()]
                    self.outcar_energies = [0]
                    self.magmoms = self.poscar.number_of_atoms() * [0]
        else:
            if os.path.getsize(os.path.join(dir, 'CONTCAR')) > 0:
                self.poscar = PoscarParser(os.path.join(dir, 'CONTCAR'))
                self.coordinates = self.poscar.coordinates()
                if self.outcar_file == False:
                    self.outcar_coordinates = [self.poscar.coordinates()]
                    self.outcar_energies = [0]
                    self.magmoms = self.poscar.number_of_atoms() * [0]

            else:
                if not os.path.exists(os.path.join(dir, 'POSCAR')):
                    raise EmptyFile('CONTCAR is found but appears to be empty! POSCAR missing! Check your files')
                else:
                    self.poscar = PoscarParser(os.path.join(dir, 'POSCAR'))
                    self.coordinates = self.poscar.coordinates()
                    if not self.outcar_file or self.outcar_coordinates == []:
                        self.outcar_coordinates = [self.poscar.coordinates()]
                        self.outcar_energies = [0]
                        self.magmoms = self.poscar.number_of_atoms() * [0]
        
    def parse_doscar(self, dir):
        #self.doscar = DOSCARparser(os.path.join(dir, "DOSCAR"))
        doscar_path = os.path.join(dir, 'DOSCAR')
        if not os.path.exists(doscar_path):
            print('no DOSCAR found!')
            self.doscar = []
        elif not os.path.getsize(doscar_path) != 0:
            print('DOSCAR file is empty!')
            self.doscar = []
        else:
            self.doscar = Doscar(os.path.join(dir, "DOSCAR"), False, os.path.join(dir, 'POSCAR'))
            self.process_doscar()

    def parse_chgcar(self):
        pass

    def parse_parchg(self):
        pass

    def process_doscar(self):
        from pymatgen.electronic_structure.core import Orbital, Spin
        canonical_order = [
            "s",
            "px", "py", "pz",
            "dz2", "dx2-y2", "dxy", "dxz", "dyz",
            "fz3", "fxz2", "fyz2", "fzx2", "fx3", "fy3x", "fxyz"
        ]
        orbitals = set().union(*self.doscar.pdos)
        self.orbitals = [orb for orb in canonical_order if orb in orbitals]

        canonical_orb_types = ['s', 'p', 'd', 'f']
        orb_types = {o[0] for o in self.orbitals}
        self.orbital_types = [orb for orb in canonical_orb_types if orb in orb_types]

        self.e_fermi = self.doscar._efermi
        self.total_alfa = self.doscar._tdensities[Spin.up]
        self.total_beta = self.doscar._tdensities[Spin.down]
        self.nedos = int(self.doscar.nedos_str)

    def process_poscar(self, poscar):
        #self.poscar = PoscarParser(os.path.join(dir, "POSCAR"))
        self.atoms_symb_and_num = self.poscar.symbol_and_number()
        atoms_underline_number = self.poscar.symbol_underline_number()
        self.number_of_atoms = self.poscar.number_of_atoms()
        self.list_atomic_symbols = self.poscar.list_atomic_symbols()
        self.atomic_symbols = self.poscar.atomic_symbols()
        self.init_coordinates = self.poscar.coordinates()
        self.unit_cell_vectors = self.poscar.unit_cell_vectors()

        self.orb_types = [["s"], ["py", "pz", "px"], ["dxy", "dyz", "dz", "dxz", "dx2y2"],
                          ["fy(3x2-y2)", "fxyz", "fyz2", "fz3", "fxz2", "fz(x2-y2)", "fx(x2-3y2)"]]

        self.x = self.poscar.unit_cell_vectors()[0][0]
        self.y = self.poscar.unit_cell_vectors()[1][1]
        self.z = self.poscar.unit_cell_vectors()[2][2]
        self.number_of_atoms = len(self.coordinates)
        self.symbols = self.poscar.list_atomic_symbols()
        self.constrains = self.poscar.constrains()
        self.all_constrains = self.poscar.all_constrains()
        self.suffixes = ["" for _ in range(self.number_of_atoms)]

        self.partition_atoms(atoms_underline_number)
        self.end_coords_line_number = self.poscar.end_coords_line_number

    def partition_atoms(self, atom_underline_number):
        self.partitioned_lists = [[] for _ in range(len(self.atomic_symbols))]
        for item in atom_underline_number:
            for i, atom in enumerate(self.atomic_symbols): # TODO: doesn't work good, put C and Ce in same list
                splitted = item.split("_")
                if len(splitted)>2:
                    last = splitted[-1]
                    splitted = ["_".join(splitted[:-1])]
                    splitted.append(last)
                #if item.startswith(atom):
                if splitted[0] == atom:
                    self.partitioned_lists[i].append(item)
                    break  # Once found, no need to continue checking other atoms

    def parse_doscar_lobster(self, dir):
        path = os.path.join(dir, 'DOSCAR.lobster')
        if not os.path.exists(path):
            self.lobster_dos = None
        else:
            self.lobster_dos = Doscar(path, False, os.path.join(dir, 'POSCAR'))
