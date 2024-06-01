import os
from VASPparser import *

class VaspData():
    def __init__(self, dir):
        self.doscar = DOSCARparser(os.path.join(dir, "DOSCAR"))
        self.data_up = self.doscar.dataset_up
        self.data_down = self.doscar.dataset_down
        self.orbitals = self.doscar.orbitals
        self.orbital_types = self.doscar.orbital_types
        self.e_fermi = self.doscar.efermi
        self.total_alfa = self.doscar.total_dos_alfa
        self.total_beta = self.doscar.total_dos_beta
        self.nedos = self.doscar.nedos

        poscar = PoscarParser(os.path.join(dir, "POSCAR"))
        self.atoms_symb_and_num = poscar.symbol_and_number()
        self.number_of_atoms = poscar.number_of_atoms()
        self.list_atomic_symbols = poscar.list_atomic_symbols()
        self.atomic_symbols = poscar.atomic_symbols()

        self.orb_types = [["s"], ["py", "pz", "px"], ["dxy", "dyz", "dz", "dxz", "dx2y2"],
                          ["fy(3x2-y2)", "fxyz", "fyz2", "fz3", "fxz2", "fz(x2-y2)", "fx(x2-3y2)"]]

        self.partitioned_lists = [[] for _ in range(len(self.atomic_symbols))]

        # Partition the original list
        for item in self.atoms_symb_and_num:
            for i, atom in enumerate(self.atomic_symbols):
                if item.startswith(atom):
                    self.partitioned_lists[i].append(item)
                    break  # Once found, no need to continue checking other atoms
