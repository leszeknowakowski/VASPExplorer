import time
import os

class OutcarParser:
    """Class to parse a OUTCAR file"""

    def __init__(self, dir, filename):
        """parse OUTCAR and find positions of atoms and energy at each geometry"""
        self.filename = os.path.join(dir, filename)
        self.data = []
        self.energies = []
        self.positions = []
        self.forces = []
        self.magnetizations = []
        self.total_magnetizations = []
        self.scf_energies = []
        self.section_scf_energies = []
        current_geom_step = None
        current_energy_list = []
        current_total_mags_list = []

        if os.path.exists(os.path.join(dir, 'POSCAR')):
            poscar = 'POSCAR'
        else:
            poscar = 'CONTCAR'
        self.poscar = PoscarParser(os.path.join(dir, poscar))
        self.atom_count = self.poscar.number_of_atoms()
        self.section_position = []
        self.magmoms = []
        ml_counter = 0
        mlff = False
        try:
            with open(self.filename, 'r') as file:
                lines = file.readlines()
                text = True
                binary = False
        except:
            with open(self.filename, 'rb') as file:
                lines = file.readlines()
                binary = True
                text = False
        if text:
            position = "POSITION"
            free_energy = 'FREE ENERGIE'
            ml_free_energy = 'ML FREE ENERGIE'
            magnetization = 'magnetization (x)'
            total_magnetization = 'number of electron  '
            voluntary = 'Voluntary context switches:'
            position_of_ions = 'position of ions in cartesian'
            magmom = 'MAGMOM'
            ml = '(ML)'
            iteration = "Iteration"
            electronic_energy = "free energy    TOTEN"
        if binary:
            position = b"POSITION"
            free_energy = b'FREE ENERGIE'
            ml_free_energy = b'ML FREE ENERGIE'
            magnetization = b'magnetization (x)'
            total_magnetization = b'number of electron  '
            voluntary = b'Voluntary context switches:'
            position_of_ions = b'position of ions in cartesian'
            magmom = b'magmom'
            ml = b"(ML)"
            iteration = b'Iteration'
            electronic_energy = b'free energy    TOTEN'
        lenght = len(lines)
        for i in range(lenght):
            progress_interval = max(1, lenght // 1000)

            if i % int(progress_interval) == 0 or i == lenght:
                print('\r', f"Reading OUTCAR, Progress: {i / lenght * 100:.1f}%", end='')
            line = lines[i].strip()

            if line.startswith(position) and line.endswith(ml):
                mlff = True
                self.section_position = []
                self.section_forces = []
                i += 2
                current_i = i
                for i in range(current_i, current_i + self.atom_count):
                    line = lines[i]
                    position_data = line.split()
                    atom_data = [float(x) for x in position_data[:3]]
                    force_data = [float(x) for x in position_data[3:]]
                    self.section_position.append(atom_data)
                    self.section_forces.append(force_data)
                self.positions.append(self.section_position)
                self.forces.append(self.section_forces)

            elif line.startswith(position) and mlff == False:
                self.section_position = []
                self.section_forces = []
                i += 2
                current_i = i
                for i in range(current_i, current_i + self.atom_count):
                    line = lines[i]
                    position_data = line.split()
                    atom_data = [float(x) for x in position_data[:3]]
                    force_data = [float(x) for x in position_data[3:]]
                    self.section_position.append(atom_data)
                    self.section_forces.append(force_data)
                self.positions.append(self.section_position)
                self.forces.append(self.section_forces)

            elif line.startswith(ml_free_energy):
                mlff = True
                ml_counter += 1
                i += 2
                energy_data = float(lines[i].strip().split()[5])
                self.energies.append(float(energy_data))

            elif line.startswith(free_energy):
                if mlff == True:
                    pass
                else:
                    i += 2
                    energy_data = lines[i].strip().split()[4]
                    self.energies.append(float(energy_data))

            elif line.startswith(magnetization):
                section_magnetization = []
                i += 4
                current_i = i
                for i in range(current_i, current_i + self.atom_count):
                    line = lines[i]
                    magnetization_data = line.split()
                    atom_mag = float(magnetization_data[-1])
                    section_magnetization.append(atom_mag)
                self.magnetizations.append(section_magnetization)

            elif line.startswith(total_magnetization):
                mag = line.split()[-1]
                current_total_mags_list.append(mag)

            elif line.startswith(magmom):
                magmom_splitted = line.split("=")[1].split()
                magmom_section = []
                for chunk in magmom_splitted:
                    if "*" in chunk:
                        chunk_splitted = chunk.split("*")
                        magmom_section.extend([float(chunk_splitted[1])]*int(chunk_splitted[0]))
                    else:
                        magmom_section.append(float(chunk))

                self.magmoms = magmom_section

            elif iteration in line:
                geom_step = int(line.strip().split()[2][:-1])
                electronic_step = int(line.strip().split()[3][:-1])

                if current_geom_step is None:
                    current_geom_step = geom_step
                if geom_step != current_geom_step:
                    # Save the completed geometry step's energies and total magnetization
                    self.scf_energies.append(current_energy_list)
                    self.total_magnetizations.append(current_total_mags_list[-1])
                    current_energy_list = []
                    current_total_mags_list = []
                    current_geom_step = geom_step

            elif electronic_energy in line:
                    # Extract energy value
                    if binary:
                        splitter = b"="
                    elif text:
                        splitter = "="
                    energy_str = line.split(splitter)[-1].split()[0]
                    current_energy_list.append(float(energy_str))

            if line.startswith(voluntary):
                if len(self.magnetizations) > 0:
                    self.magnetizations.pop()

        if self.section_position == []:
            for i in range(lenght):
                line = lines[i].strip()
                if line.startswith(position_of_ions):
                    i += 1
                    current_i = i
                    for i in range(current_i, current_i + self.atom_count):
                        line = lines[i]
                        position_data = line.split()
                        atom_data = [float(x) for x in position_data[:3]]
                        self.section_position.append(atom_data)
                    self.positions.append(self.section_position)
            # self.magnetizations = [["N/A" for atom in self.atom_count]]

        if current_energy_list:
            self.scf_energies.append(current_energy_list)

        if self.energies == []:
            print(
                "run didn't calculated energy (eg. PARCHG file generation or other postprocessing. Energy is set to 0.")
            self.energies = [0]
        else:
            first_non_zero = next((x for x in self.energies if x != 0.0), None)
            self.energies = [first_non_zero if x == 0.0 else x for x in self.energies]
        if self.magmoms == []:
            self.magmoms = self.atom_count * ["0"]
        print('\n')

    def find_coordinates(self):
        """returns coordinates of each electronically converged calculation step"""
        return self.positions

    def find_energy(self):
        """returns converged energy in eV"""
        return self.energies

    def find_forces(self):
        """returns forces of each converged calculation geometric step"""
        return self.forces

    def find_magnetization(self):
        search_string = 'magnetization'
        with open(self.filename, 'r') as file:
            file.seek(0, 2)
            file.seek(file.tell() - 16500, 0)
            file.readline()
            lines = file.readlines()
            file.seek(file.tell() - 16500, 0)
            file.readline()
            i = 0
            while i < len(lines):
                i += 1
                line = file.readline()
                if search_string in line:
                    j = 0
                    while j < 10:
                        j += 1
                        line = file.readline()
                        line = line.strip()
                        if line.startswith('1'):
                            lines_mag = file.readlines()
                            lines_mag = [line.strip() for line in lines_mag]
                            break
                    break
        lines_mag.insert(0, line)
        lines_mag = [el.split() for el in lines_mag]
        lines_mag = lines_mag[:self.poscar.number_of_atoms()]
        mag_values = [lst[-1] for lst in lines_mag]
        return mag_values

    def find_scf_energies(self):
        return self.scf_energies

class PoscarParser:
    """class to parse POSCAR / CONTCAR files"""

    def __init__(self, source):
        from io import StringIO, TextIOBase
        self.filename = source
        self.atom_symbols_exists = None
        self.dynamic_exists = None
        self.total_atoms = 0

        if isinstance(source, str):
            with open(source, 'r') as file:
                self.lines = file.readlines()
        elif isinstance(source, (StringIO, TextIOBase)):
            source.seek(0)  # Rewind the buffer to the beginning
            self.lines = source.readlines()
        else:
            raise ValueError("Input must be a filename or a file-like object (e.g., io.StringIO)")
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
            unit_cell_vectors.append([float(value) * self.scale_factor() for value in line.split()])
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
            potcar_path = os.path.join(os.path.dirname(self.filename),'POTCAR')
            potcar_dir = os.path.dirname(potcar_path)
            potcar_parent_dir = os.path.dirname(potcar_dir)
            if os.path.exists(potcar_path):
                potcar = potcar_path
            elif os.path.exists(os.path.join(potcar_parent_dir,'POTCAR')):
                potcar = os.path.join(potcar_parent_dir,'POTCAR')
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
            atom_symbols = [atom.rstrip('/') for atom in atom_symbols]

        def extract_letters(input_string):
            return ''.join([char for char in input_string if char.isalpha()])

        #return [extract_letters(s) for s in atom_symbols]
        return  atom_symbols

    def mendelev_symbols(self, list):
        """
        returns a list of atomic symbols, one for each atom, without any numbers or suffixes
        """
        import re
        mendelev_symbols = [re.sub(r'[\d_].*', '', s) for s in list]
        return mendelev_symbols

    def atom_lines_as_in_poscar(self, list):
        """
        counts consecutive atomic symbols in data and returns symbols and counts
        as in POSCAR file, in line with symbols and atom counts
        list:
            a list of atomic symbols, one for each atom
        """
        atoms = list
        names = []
        counts = []

        current = atoms[0]
        count = 1

        for atom in atoms[1:]:
            if atom == current:
                count += 1
            else:
                names.append(current)
                counts.append(count)
                current = atom
                count = 1

        # Append the last group
        names.append(current)
        counts.append(count)

        return names, counts

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

    def symbol_underline_number(self):
        sym_num_list = []
        for symbol, number in zip(self.list_atomic_symbols(), range(1, self.number_of_atoms() + 1)):
            sym_num_list.append(str(symbol) + "_" + str(number))
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
        all_constrains = []
        self.end_coords_line_number = start_line + self.number_of_atoms()
        for line in self.lines[start_line:start_line + self.number_of_atoms()]:
            values = line.split()
            coordinates.append([float(value) for value in values[:3]])
            if len(values) == 6:
                constrain.append(values[3])
                all_constrains.append(values[3:])
            else:
                constrain.append('n/a')
                all_constrains.append(['n/a', 'n/a', 'n/a'])
        if self.coordinate_type() == "Direct":  # convert from direct to cartesian
            coords_cart = []
            for coor in coordinates:
                x = coor[0] * self.unit_cell_vectors()[0][0]
                y = coor[1] * self.unit_cell_vectors()[1][1]
                z = coor[2] * self.unit_cell_vectors()[2][2]
                coords_cart.append([x, y, z])
            return coords_cart, constrain, all_constrains
        else:
            return coordinates, constrain, all_constrains

    def coordinates(self):
        return self.parse_coordinates()[0]

    def constrains(self):
        constrain = self.parse_coordinates()[1]
        if len(constrain[0]) == 0:
            return ['n/a'] * self.total_atoms
        else:
            return self.parse_coordinates()[1]

    def all_constrains(self):
        return self.parse_coordinates()[2]


class DOSCARparser:

    def __init__(self, file):
        self.dataset_up = []
        self.small_dataset_up = []
        self.dataset_down = []
        self.small_dataset_down = []
        if os.path.exists(file):
            if os.path.getsize(file) != 0:
                with open(file, 'r') as file:
                    lines = file.readlines()
                    self.number_of_atoms = int(lines[0].strip().split()[0])

                    try:
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
                            self.orbital_types = [["s"], ["py", "pz", "px"]]
                        elif len(self.dos_parts[0][0]) == 32:
                            self.element_block = 'f'
                            self.orbitals = ["s", "py", "pz", "px", "dxy", "dyz", "dz", "dxz", "dx2y2", "fy(3x2-y2)",
                                             "fxyz", "fyz2",
                                             "fz3", "fxz2", "fz(x2-y2)", "fx(x2-3y2)"]
                            self.orbital_types = [["s"], ["py", "pz", "px"], ["dxy", "dyz", "dz", "dxz", "dx2y2"],
                                                  ["fy(3x2-y2)", "fxyz", "fyz2",
                                                   "fz3", "fxz2", "fz(x2-y2)", "fx(x2-3y2)"]]
                        elif len(self.dos_parts[0][0]) == 2:
                            self.element_block = 's'
                            self.orbitals = ["s"]
                            self.orbital_types = [["s"]]
                        else:
                            '''raise error'''
                            pass

                        for i in range(self.number_of_atoms):
                            for j in range(0, 2 * len(self.orbitals), 2):
                                self.small_dataset_up.append(list(map(lambda sublist: sublist[j], self.dos_parts[i])))
                            self.dataset_up.append(self.small_dataset_up)
                            self.small_dataset_up = []
                        for i in range(self.number_of_atoms):
                            for j in range(1, 2 * len(self.orbitals) + 1, 2):
                                self.small_dataset_down.append(list(map(lambda sublist: sublist[j], self.dos_parts[i])))
                            self.dataset_down.append(self.small_dataset_down)
                            self.small_dataset_down = []
                    except:
                        print("DOSCAR file is invalid. It will not be proccesed")
                        for i in range(self.number_of_atoms):
                            self.small_dataset_up.append([0])
                            self.small_dataset_down.append([0])
                            self.total_dos_alfa = [0]
                            self.total_dos_beta = [0]
                            self.total_dos_energy = [0]
                        self.orbitals = ["none"]
                        self.orbital_types = ["none"]
                        self.nedos = 0
                        self.efermi = 0
            else:
                print('DOSCAR file is empty')
                self.make_empty_DOS_data()
        else:
            print('no DOSCAR found!')
            self.make_empty_DOS_data()

    def make_empty_DOS_data(self):
        for i in range(1):
            self.small_dataset_up.append([0])
            self.small_dataset_down.append([0])
            self.total_dos_alfa = [0]
            self.total_dos_beta = [0]
            self.total_dos_energy = [0]
        self.orbitals = ["none"]
        self.orbital_types = ["none"]
        self.nedos = 0
        self.efermi = 0

    def splitter(self, list, size):
        for i in range(0, len(list), size):
            yield list[i:i + size - 1]

class BaderParser:
    def __init__(self, file):
        pass



if __name__ == "__main__":
    doscar = DOSCARparser("D:\\syncme-from-c120\\modelowanie DFT\\czasteczki\\O2\\DOSCAR")
    poscar = PoscarParser("D:\\syncme-from-c120\\modelowanie DFT\\czasteczki\\O2\\POSCAR")
    outcar = OutcarParser("D:\\syncme-from-c120\\modelowanie DFT\\czasteczki\\O2","OUTCAR")
    print(doscar.number_of_atoms == poscar.number_of_atoms())
    print(doscar.element_block)