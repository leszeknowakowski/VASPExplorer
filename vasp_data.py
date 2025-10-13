import time

tic = time.perf_counter()
try:
    from ase.io import read, write
    toc = time.perf_counter()
    print(f'import ase in vaspdata: {toc - tic:0.4f}')
except:
    print("no ASE module")
import os
from VASPparser import *
import json
from exceptions import EmptyFile


class VaspData():
    def __init__(self, dir, parse_doscar=True):
        outcar = self.parse_outcar(dir)
        poscar = self.parse_poscar(dir)
        if parse_doscar:
            doscar = self.parse_doscar(dir)
            self.process_doscar(doscar)
        self.process_poscar(poscar)
        self.nums = list(range(1, self.number_of_atoms+1))



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
        import glob
        poscar_path = os.path.join(dir, 'POSCAR')
        contcar_path = os.path.join(dir, 'CONTCAR')
        xdatcar_path = os.path.join(dir, 'XDATCAR')
        xdatcar_ext = os.path.join(dir, '*.xdatcar')

        if not os.path.exists(poscar_path):
            self.poscar_file = False
        else:
            self.poscar_file = poscar_path

        if not os.path.exists(contcar_path):
            self.contcar_file = False
        else:
            self.contcar_file = contcar_path

        if not os.path.exists(xdatcar_path):
            self.xdatcar_file = False
            xdatcar_files = glob.glob(xdatcar_ext)
            if not xdatcar_files:
                self.xdatcar_file = False
            else:
                self.xdatcar_file = xdatcar_files[0]
        else:
            self.xdatcar_file = xdatcar_path




        if not self.contcar_file and not self.poscar_file and not self.xdatcar_file and not self.outcar_file:
            for file in os.listdir(dir):
                # Check if the file has a .cell extension
                if file.endswith(".cell"):
                    # Read the .cell file
                    structure = read(os.path.join(dir,file))
                    write(os.path.join(dir,"POSCAR"), structure, format="vasp")
                else:
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


        if self.contcar_file:
            if os.path.getsize(contcar_path) > 0:
                self.poscar = PoscarParser(self.contcar_file)
                self.coordinates = self.poscar.coordinates()
                if self.outcar_file == False:
                    self.outcar_coordinates = [self.poscar.coordinates()]
                    self.outcar_energies = [0]
                    self.magmoms = self.poscar.number_of_atoms() * [0]

            else: # if contcar size is 0
                if not os.path.exists(poscar_path):
                    raise EmptyFile('CONTCAR is found but appears to be empty! POSCAR missing! Check your files')
                else:
                    self.poscar = PoscarParser(self.poscar_file)
                    self.coordinates = self.poscar.coordinates()
                    if not self.outcar_file or self.outcar_coordinates == []:
                        self.outcar_coordinates = [self.poscar.coordinates()]
                        self.outcar_energies = [0]
                        self.magmoms = self.poscar.number_of_atoms() * [0]

        if self.xdatcar_file:
            self.xdatcar = self.parse_xdatcar(dir, self.xdatcar_file)
            self.xdatcar_file = self.xdatcar.xdatcar_file

        if self.xdatcar_file:
            if os.path.getsize(self.xdatcar_file) > 0:
                self.xdatcar = self.parse_xdatcar(dir, self.xdatcar_file)
                self.poscar = PoscarParser(self.xdatcar_file)
                self.coordinates = self.xdatcar.coordinates[0]
                self.outcar_coordinates = self.xdatcar.coordinates
                self.outcar_energies = [0 for step in self.outcar_coordinates]
                self.magmoms = [0 for atom in self.coordinates]

    def parse_doscar(self, dir):
        self.doscar = DOSCARparser(os.path.join(dir, "DOSCAR"))

    def parse_chgcar(self):
        pass

    def parse_parchg(self):
        pass

    def process_doscar(self, doscar):
        self.data_up = self.doscar.dataset_up
        self.data_down = self.doscar.dataset_down
        self.orbitals = self.doscar.orbitals
        self.orbital_types = self.doscar.orbital_types
        self.e_fermi = self.doscar.efermi
        self.total_alfa = self.doscar.total_dos_alfa
        self.total_beta = self.doscar.total_dos_beta
        self.nedos = self.doscar.nedos

    def process_poscar(self, poscar):
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

    def parse_xdatcar(self, dir, file):
        file = os.path.join(dir, file)
        if os.path.exists(file):
            xdatcar = XDATCARParser(os.path.join(dir, file))
            return xdatcar