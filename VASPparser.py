import time

tic = time.perf_counter()
import os
toc = time.perf_counter()
print(f' import os: {toc - tic:0.4f} seconds')
class OutcarParser:
    """Class to parse a OUTCAR file"""

    def __init__(self, filename):
        """parse OUTCAR and find positions of atoms and energy at each geometry"""
        self.filename = filename
        self.data = []
        self.energies = []
        self.positions = []
        self.poscar = PoscarParser('POSCAR')
        self.atom_count = self.poscar.number_of_atoms()

        with open(self.filename, 'r') as file:
            lines = file.readlines()
            lenght = len(lines)
            for i in range(lenght):
                if i % 10000 == 0:
                    print('reading OUTCAR file; line: ', i, f' out of {lenght}', end='\r')
                line = lines[i].strip()
                section_position = []
                if line.startswith('POSITION'):
                    i += 2
                    current_i = i
                    for i in range(current_i, current_i + self.atom_count):
                        line = lines[i]
                        position_data = line.split()
                        atom_data = [float(x) for x in position_data[:3]]
                        section_position.append(atom_data)
                    self.positions.append([section_position])
                elif line.startswith('FREE ENERGIE'):
                    i += 2
                    energy_data = lines[i].strip().split()[4]
                    self.energies.append(float(energy_data))
            if section_position==[]:
                for i in range(lenght):
                    line = lines[i].strip()
                    if line.startswith('position of ions in cartesian'):
                        i += 1
                        current_i = i
                        for i in range(current_i, current_i + self.atom_count):
                            line = lines[i]
                            position_data = line.split()
                            atom_data = [float(x) for x in position_data[:3]]
                            section_position.append(atom_data)
                        self.positions.append(section_position)

        print('\n')

    def find_coordinates(self):
        """returns coordinates of each electronically converged calculation step"""
        return self.positions

    def find_energy(self):
        """returns converged energy in eV"""
        return self.energies
        
    def find_magnetization(self):
        search_string = 'magnetization'
        with open(self.filename, 'r') as file:
            file.seek(0, 2)
            file.seek(file.tell() - 6500, 0)
            file.readline()
            lines = file.readlines()
            file.seek(file.tell() - 6500, 0)
            file.readline()
            i=0
            while i < len(lines):
                i+=1
                line = file.readline()
                if search_string in line:
                    j = 0
                    while j < 10:
                        j+=1
                        line=file.readline()
                        line=line.strip()
                        if line.startswith('1'):
                            lines_mag = file.readlines()
                            lines_mag=[line.strip() for line in lines_mag]
                            break
                    break
        lines_mag.insert(0,line)
        lines_mag=[el.split() for el in lines_mag]
        lines_mag=lines_mag[:self.poscar.number_of_atoms()]
        mag_values=[lst[-1] for lst in lines_mag]
        return mag_values


class PoscarParser:
    """class to parse POSCAR / CONTCAR files"""

    def __init__(self, filename):
        self.filename = filename
        self.atom_symbols_exists = None
        self.dynamic_exists = None
        self.total_atoms = 0
        with open(self.filename, 'r') as file:
            self.lines = file.readlines()
            self.scale = self.scale_factor()
            self.unit_cell_vectors()
            self.atomic_symbols()
            self.dynamics()

    def title(self):
        title = self.lines[0].strip()
        return title

    def scale_factor(self):
        scale_factor = float(self.lines[1].strip())
        return scale_factor

    def unit_cell_vectors(self):
        unit_cell_vectors = []
        for line in self.lines[2:5]:
            unit_cell_vectors.append([float(value)*self.scale_factor() for value in line.split()])
        return unit_cell_vectors

    @staticmethod
    def is_integer(string):
        try:
            int(string)
            return True
        except ValueError:
            return False

    def atomic_symbols(self):
        atom_symbols = []
        if PoscarParser.is_integer(self.lines[5].split()[0]):
            self.atom_symbols_exists = False
            if os.path.exists('POTCAR'):
                potcar = 'POTCAR'
            elif os.path.exists('../POTCAR'):
                potcar = '../POTCAR'
            else:
                raise FileNotFoundError('Error! No POTCAR file found!')
            with open(potcar, 'r') as file:
                lines = file.readlines()
                lenght = len(lines)
                first = lines[0].split()
                atom_symbols.append(first[1])

                for i in range(1, lenght - 10):
                    if lines[i].strip().startswith('End of Dataset'):
                        i += 1
                        method_line = lines[i].split()
                        atom_symbols.append(method_line[1])
        else:
            self.atom_symbols_exists = True
            atom_symbols = self.lines[5].split()
        return atom_symbols

    def list_atomic_symbols(self):
        symbol_list = [s for s, c in zip(self.atomic_symbols(), self.atom_counts()) for _ in range(c)]
        return symbol_list

    def atom_counts(self):
        if self.atom_symbols_exists:
            counts = [int(value) for value in self.lines[6].split()]
        else:
            counts = [int(value) for value in self.lines[5].split()]
        return counts

    def number_of_atoms(self):
        self.total_atoms = sum(self.atom_counts())
        return sum(self.atom_counts())

    def symbol_and_number(self):
        sym_num_list = []
        for symbol, number in zip(self.list_atomic_symbols(), range(1, self.number_of_atoms() + 1)):
            sym_num_list.append(str(symbol) + str(number))
        return sym_num_list

    def dynamics(self):
        if self.atom_symbols_exists and self.lines[7].strip()[0].lower() == "s":
            self.dynamic_exists = True
            return self.lines[7].strip()
        elif self.atom_symbols_exists is False and self.lines[6].strip()[0].lower() == "s":
            self.dynamic_exists = True
            return self.lines[6].strip()
        else:
            self.dynamic_exists = False
            return 'no dynamics'

    def coordinate_type(self):
        if self.atom_symbols_exists and self.dynamic_exists:
            return self.lines[8].strip()
        elif self.atom_symbols_exists and self.dynamic_exists is False:
            return self.lines[7].strip()
        elif self.atom_symbols_exists is False and self.dynamic_exists:
            return self.lines[7].strip()
        elif self.atom_symbols_exists is False and self.dynamic_exists is False:
            return self.lines[6].strip()

    def parse_coordinates(self):
        start_line = None
        if self.atom_symbols_exists and self.dynamic_exists:
            start_line = 9
        elif self.atom_symbols_exists and self.dynamic_exists is False:
            start_line = 8
        elif self.atom_symbols_exists is False and self.dynamic_exists:
            start_line = 8
        elif self.atom_symbols_exists is False and self.dynamic_exists is False:
            start_line = 7
        coordinates = []
        constrain = []
        for line in self.lines[start_line:start_line + self.number_of_atoms()]:
            values = line.split()
            coordinates.append([float(value) for value in values[:3]])
            if len(values) == 6:
                constrain.append(values[3])
            else: 
                constrain.append('n/a')
        if self.coordinate_type() == "Direct":  # convert from direct to cartesian
            coords_cart = []
            for coor in coordinates:
                x = coor[0] * self.unit_cell_vectors()[0][0]
                y = coor[1] * self.unit_cell_vectors()[1][1]
                z = coor[2] * self.unit_cell_vectors()[2][2]
                coords_cart.append([x, y, z])
            return coords_cart, constrain
        else:
            return coordinates, constrain

    def coordinates(self):
        return self.parse_coordinates()[0]

    def constrains(self):
        constrain = self.parse_coordinates()[1]
        if len(constrain[0]) == 0:
            return ['n/a']*self.total_atoms
        else:
            return self.parse_coordinates()[1]


class DOSCARparser:

    def __init__(self, file):
        with open(file, 'r') as file:
            lines = file.readlines()
            self.number_of_atoms = int(lines[0].strip().split()[0])
            info_line_full = lines[5]
            info_line = info_line_full.strip().split()
            stop_nrg, start_nrg, self.nedos, self.efermi = [info_line[i] for i in range(4)]
            self.nedos = int(self.nedos)
            dos_parts = list(self.splitter(lines[6:], self.nedos + 1))

            total_dos = [line.strip().split() for line in dos_parts[0]]
            self.total_dos_energy = [float(x) for x in list(map(lambda sublist: sublist[0], total_dos))]
            self.total_dos_alfa = [float(x) for x in list(map(lambda sublist: sublist[1], total_dos))]
            self.total_dos_beta = [float(x) for x in list(map(lambda sublist: sublist[2], total_dos))]
            dos_parts = [list for list in dos_parts[1:]]
            dos_parts = [[line.strip().split() for line in sublist] for sublist in dos_parts]
            self.dos_parts = [[[float(x) for x in list[1:]] for list in sublist] for sublist in dos_parts]
            del lines
            if len(self.dos_parts[0][0]) == 18:
                self.element_block = 'd'
                self.orbitals = ["s", "py", "pz", "px", "dxy", "dyz", "dz", "dxz", "dx2y2"]
                self.orbital_types = [["s"], ["py", "pz", "px"], ["dxy", "dyz", "dz", "dxz", "dx2y2"]]
            elif len(self.dos_parts[0][0]) == 8:
                self.element_block = 'p'
                self.orbitals = ["s", "py", "pz", "px"]
                self.orbital_types =[["s"], ["py", "pz", "px"]]
            elif len(self.dos_parts[0][0]) == 32:
                self.element_block = 'f'
                self.orbitals = ["s", "py", "pz", "px", "dxy", "dyz", "dz", "dxz", "dx2y2", "fy(3x2-y2)", "fxyz", "fyz2",
                            "fz3", "fxz2", "fz(x2-y2)", "fx(x2-3y2)"]
                self.orbital_types =[["s"], ["py", "pz", "px"], ["dxy", "dyz", "dz", "dxz", "dx2y2"], ["fy(3x2-y2)", "fxyz", "fyz2",
                            "fz3", "fxz2", "fz(x2-y2)", "fx(x2-3y2)"]]
            elif len(self.dos_parts[0][0]) == 2:
                self.element_block = 's'
                self.orbitals = ["s"]
                self.orbital_types = [["s"]]
            else:
                '''raise error'''
                pass
            self.dataset_up = []
            small_dataset_up = []
            self.dataset_down = []
            small_dataset_down = []
            for i in range(self.number_of_atoms):
                for j in range(0, 2 * len(self.orbitals), 2):
                    small_dataset_up.append(list(map(lambda sublist: sublist[j], self.dos_parts[i])))
                self.dataset_up.append(small_dataset_up)
                small_dataset_up = []
            for i in range(self.number_of_atoms):
                for j in range(1, 2 * len(self.orbitals) + 1, 2):
                    small_dataset_down.append(list(map(lambda sublist: sublist[j], self.dos_parts[i])))
                self.dataset_down.append(small_dataset_down)
                small_dataset_down = []

    def splitter(self, list, size):
        for i in range(0, len(list), size):
            yield list[i:i + size - 1]


if __name__ == "__main__":
    doscar = DOSCARparser("D:\\OneDrive - Uniwersytet Jagielloński\\modelowanie DFT\\czasteczki\\O2\\DOSCAR")
    poscar = PoscarParser("D:\\OneDrive - Uniwersytet Jagielloński\\modelowanie DFT\\czasteczki\\O2\\POSCAR")
    print(doscar.number_of_atoms == poscar.number_of_atoms())
    print(doscar.element_block)