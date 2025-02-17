#########################################################################
# python script to reduce PARCHG points grid  and save chopped		#
# files with different outup, eg. total or spin density			#
# and alfa or beta channel partial density.				#
#									#
# Created by Leszek Nowakowski, Cracov 2023				#
# initial version: 30.05.2023						#
# switching to Python: 3.10.2023					#
# adding total/spin/alfa/beta channel functionality: 07.01.2024		#
# adding user input file range: 22.02.2024				#
#									#
# usage:								#
# python3 /path/to/script chopping-factor output-type			#
# run script in directory when You want the files to be			#
# converted and add arguments -  chopping factor (how many times array	# 
# of points should be donwgraded) and output file type (total, spin,	# 
# alfa or beta partial electron density.				#
# You can use multiple type output, eg. "alfa" "beta"			#
# As input you can specfy an array of files, eg. 1-10 or 1,4,10		#
#									#
#########################################################################

import time
import sys
import os
import re

total_tic = time.time()
import numpy as np


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


def print_colored_message(message, color):
    """helper function to print colorful terminal messages"""
    print(f"{color}{message}{Colors.RESET}")


class PoscarParser:
    """class to parse POSCAR / CONTCAR files
    Parameters
    ------------------
    filename: str
        CHGCAR filename
    chop_number: int
        how many times CHGCAR grid should be shrinked (helps to save memory
    """

    def __init__(self, filename, chop_number):
        self.filename = filename
        self.chop_number = int(chop_number)

        # read all file at once (not very efficient though...)
        with open(self.filename, 'r') as file:
            self.lines = file.readlines()

        # grid dimensions [x, y, z]
        self.grid_result = self.grid()

        # chopped grid of numbers
        self.all_numbers = self.change_numbers(self.chop_number)

        # calc alfa and beta density
        # TODO: execute this function only when alfa,beta density is chosen
        [self.alfa, self.beta] = self.calc_alfa_beta(self.chop_number)

        self.header = self.lines[:self.end_coords_line() + 1]

    def title(self):
        """title line of CHGCAR

        Returns:
        _____________
        str
            title of the CHGCAR file
        """
        return self.lines[0].strip()

    def scale_factor(self):
        """
        Returns:
        ______________________
        float
            unit cell scale factor
        """
        return float(self.lines[1].strip())

    def unit_cell_vectors(self):
        """
        Returns:
        _______________________
        list
            unit cell basis vectors as a list [[a1, a2, a3], [b1, b2, b3], [c1, c2, c3]]
        """
        unit_cell_vectors = []
        for line in self.lines[2:5]:
            unit_cell_vectors.append([float(value) for value in line.split()])
        return unit_cell_vectors

    def calculate_volume(self):
        """ Calculates volume of unit cell
        Returns:
        _____________________
        float
            unit cell volume in Angstroms
        """
        vectors = self.unit_cell_vectors()
        a_vec = np.array(vectors[0])
        b_vec = np.array(vectors[1])
        c_vec = np.array(vectors[2])

        volume = np.abs(np.dot(a_vec, np.cross(b_vec, c_vec)))

        return volume

    def calculate_grid_spacings(self):
        """ Calculates the spacing between grid points of chopped grid
        Returns:
        _____________________
        list
            spacings in all directions as a float list [sx, sy, sz]
        """
        vecs = [self.unit_cell_vectors()[i][i] for i in range(3)]
        spacings = [vecs[i]/self.grid_result[i] for i in range(3)]
        spacing_chopped = [spacings[i]*self.chop_number for i in range(3)]
        return spacing_chopped

    def atomic_symbols(self):
        """
        Returns:
        _____________________
        list
            list of strings of unique atoms, eg. ["Co", "Ce", "O"] as defined in CHGCAR
        """
        symbols = self.lines[5].split()
        return symbols

    def list_atomic_symbols(self):
        """
        Returns:
        _____________________
        list
            list of strings of every atom, multiplied by occurences,
            eg. ["Co", "Co", "Co", "Ce", "Ce", "O"] as defined in CHGCAR
        """
        symbol_list = [s for s, c in zip(self.atomic_symbols(), self.atom_counts()) for _ in range(c)]
        return symbol_list

    def atom_counts(self):
        """ get the number of uniqe atoms from CHGCAR file
        Returns:
        _____________________
        list
            list of integers, eg. [5, 10, 1]
        """
        counts = [int(value) for value in self.lines[6].split()]
        return counts

    def number_of_atoms(self):
        """ calculate total number of atoms
        Returns:
        _____________________
        int
        """
        return sum(self.atom_counts())

    def symbol_and_number(self):
        """creates a list of string of atoms with their ordinal numbers
        Returns:
        _____________________
        list
            list of strings of atoms and numbers,
            eg. ["Co1", "Co2", "Ce3", "O4"] as defined in CHGCAR
        """
        sym_num_list = []
        for symbol, number in zip(self.list_atomic_symbols(), range(1, self.number_of_atoms() + 1)):
            sym_num_list.append(str(symbol) + str(number))
        return sym_num_list

    def coordinate_type(self):
        """get the types of coordinates in CHGCAR structural part
        Returns:
        ----------------
        str
            "Direct" or "Cartesian"
        """
        return self.lines[7].strip()

    def parse_coordinates(self):
        """ atoms' coordinates parser
        Returns:
        _____________________
        list
            list of coordinates in cartesian for every atom
        list
            list of movement constrains for every atom
        int
            number of line at which structural part of CHGCAR has ended
        """
        coordinates = []
        constrain = []
        number_of_atoms = self.number_of_atoms()
        start_line = 8
        end_line = start_line + number_of_atoms
        vectors = self.unit_cell_vectors()
        for line in self.lines[start_line:end_line]:
            values = line.split()
            coordinates.append([float(value) for value in values[:3]])
            constrain.append(values[3:])
        if self.coordinate_type() == "Direct":  # convert from direct to cartesian
            coords_cart = []
            for coor in coordinates:
                x = coor[0] * vectors[0][0]
                y = coor[1] * vectors[1][1]
                z = coor[2] * vectors[2][2]
                coords_cart.append([x, y, z])
            return coords_cart, constrain, end_line
        else:
            return coordinates, constrain, end_line

    def coordinates(self):
        """
        Returns:
        _____________________
        list
            list of coordinates in cartesian for every atom
        """
        return self.parse_coordinates()[0]

    def constrains(self):
        """
        Returns:
        _____________________
        list
            list of constrains for every atom
        """
        return self.parse_coordinates()[1]

    def end_coords_line(self):
        """
        Returns:
        _____________________
        int
            number of line at which structural part of CHGCAR has ended
        """
        return self.parse_coordinates()[2]
        
    def grid_string(self):
        """get the line where grid numbers are defined
        Returns:
        _____________________
        string
            whole line straight from CHGCAR
        """
        grid_string = self.lines[self.end_coords_line() + 1]
        return grid_string
        
    def grid(self):
        """calculate the grid dimensions
        Returns:
        _____________________
        list
            list of int with grid points in each dimensions, eg. [10,10,20]
        """
        grid_list = [int(x) for x in self.grid_string().split()]
        global xgrid, ygrid, zgrid, grid_points
        xgrid, ygrid, zgrid = grid_list[0], grid_list[1], grid_list[2]
        grid_points = xgrid * ygrid * zgrid
        return grid_list

    def read_numbers(self):
        """get the whole rest of file after first grid dimensions line
        Returns:
        _____________________
        list
            list of string for every line up to the EOF
        """
        content = self.lines[self.end_coords_line() + 2:]
        return content
            
    def common_divisors(self, a, b, c):
        """calculate common divisors for dimensions of grid
        Returns:
        _____________________
        list
            list of all possible common divisors
        """
        divisors = []
        smallest = min(a, b, c)
        for i in range(1, smallest + 1):
            if a % i == 0 and b % 1 == 0 and c % i == 0:
                divisors.append(i)
        return divisors
        
    def split_grid(self):
        """ splits the grid into total and spin density
        Returns:
        _____________________
        list
            list of total density points
        list
             list of spin density points
        """
        content = self.read_numbers()
        search_grid_str=self.grid_string()[:10]
        chopping_index = next((i for i, s in enumerate(content) if search_grid_str in s), None)
        total=[num if '*' not in num else 0 for row in content[:chopping_index] for num in row.split()]
        total = [float(x) for x in total[:grid_points]]
        print("total density  expected points: ", grid_points, " read points: ", len(total))
        spin = [num if '*' not in num else 0 for row in content[1+chopping_index:] for num in row.split()]
        spin = [float(x) for x in spin[:grid_points]]
        print("spin density  expected points: ", grid_points, " read points: ", len(spin))
        return total,spin
        
    def change_numbers(self, chop_number):
        """chop and reshape the grid
        Returns:
        _____________________
        np.array
            numpy chopped matrix of total density
        np.array
            numpy chopped matrix of spin density
        """
        grid_list = self.grid_result
        divisors = self.common_divisors(*grid_list)
        totaldensity, spindensity = self.split_grid()
        
        print("grid: ", grid_list, "common divisors:", divisors)
        if chop_number not in divisors:
            raise ValueError("chooping factor is not a divisor of grid points")  
        # all_numbers store the whole rest of file beyond header, one by one as separete elements
        
        print("spin density expected points: ", grid_points, ", read points: ", len(spindensity))

        totalmatrix = np.array(totaldensity, dtype=float).reshape(zgrid, ygrid, xgrid)
        total_chopped_matrix = totalmatrix[:zgrid:chop_number, :ygrid:chop_number, :xgrid:chop_number]
        spinmatrix = np.array(spindensity, dtype=float).reshape(zgrid, ygrid, xgrid)
        spin_chopped_matrix = spinmatrix[:zgrid:chop_number, :ygrid:chop_number, :xgrid:chop_number]
        return total_chopped_matrix, spin_chopped_matrix

    def save_total_file(self, output_file_path, chop_number):
        """" save chopped file as CHGCAR-total-choppedx{chop_num}.vasp with total charge density """
        with open(output_file_path, 'w') as output_file:
            for list in self.header:
                output_file.write(list)
            output_file.write(" ".join([str(x // chop_number) for x in self.grid_result]) + "\n")

            for i, item in enumerate(self.all_numbers[0].flatten(), 1):
                formatted_item = format(item, ".3f")
                # formatted_item = format(item, ".3f")
                output_file.write(str(formatted_item))
                if i % 10 == 0:
                    output_file.write("\n")
                else:
                    output_file.write("\t")

    def save_all_file(self, output_file_path, chop_number):
        """" save chopped file as CHGCAR-all-choppedx{chop_num}.vasp with total charge density """
        with open(output_file_path, 'w') as output_file:
            for list in self.header:
                output_file.write(list)
            output_file.write(" ".join([str(x // chop_number) for x in self.grid_result]) + "\n")

            for i, item in enumerate(self.all_numbers[0].flatten(), 1):
                formatted_item = format(item, ".3f")
                # formatted_item = format(item, ".3f")
                output_file.write(str(formatted_item))
                if i % 10 == 0:
                    output_file.write("\n")
                else:
                    output_file.write("\t")

            output_file.write("\n")
            output_file.write("\n")
            output_file.write(" ".join([str(x // chop_number) for x in self.grid_result]) + "\n")
            for i, item in enumerate(self.all_numbers[1].flatten(), 1):
                formatted_item = format(item, ".3f")
                # formatted_item = format(item, ".3f")
                output_file.write(str(formatted_item))
                if i % 10 == 0:
                    output_file.write("\n")
                else:
                    output_file.write("\t")

    def save_spin_file(self, output_file_path, chop_number):
        """" save chopped file as CHGCAR-spin-choppedx{chop_num}.vasp with total charge density """
        with open(output_file_path, 'w') as output_file:
            for list in self.header:
                output_file.write(list)
            output_file.write(" ".join([str(x // chop_number) for x in self.grid_result]) + "\n")

            for i, item in enumerate(self.all_numbers[1].flatten(), 1):
                formatted_item = format(item, ".3f")
                # formatted_item = format(item, ".3f")
                output_file.write(str(formatted_item))
                if i % 10 == 0:
                    output_file.write("\n")
                else:
                    output_file.write("\t")

    def calc_alfa_beta(self, chop_number):
        """calculate alfa and beta density
        Returns:
            np.array
                with alfa charge density
            np.array
                with beta density
        """
        [total_density, spin_density] = self.all_numbers
        sum_total = 2 * total_density
        sum_spin = 2 * spin_density
        alfa_density = (sum_total + sum_spin) / 4
        beta_density = (sum_total - sum_spin) / 4
        return alfa_density, beta_density

    def save_alfa_file(self, output_file_path, chop_number):
        """" save chopped file as CHGCAR-alfa-choppedx{chop_num}.vasp with total charge density """
        alfa = self.alfa
        with open(output_file_path, 'w') as output_file:
            for list in self.header:
                output_file.write(list)
            output_file.write(" ".join([str(x // chop_number) for x in self.grid_result]) + "\n")

            for i, item in enumerate(alfa.flatten(), 1):
                formatted_item = format(item, ".3f")
                output_file.write(str(formatted_item))
                if i % 10 == 0:
                    output_file.write("\n")
                else:
                    output_file.write("\t")

    def save_beta_file(self, output_file_path, chop_number):
        """" save chopped file as CHGCAR-beta-choppedx{chop_num}.vasp with total charge density """
        beta = self.beta
        with open(output_file_path, 'w') as output_file:
            for list in self.header:
                output_file.write(list)
            output_file.write(" ".join([str(x // chop_number) for x in self.grid_result]) + "\n")

            for i, item in enumerate(beta.flatten(), 1):
                formatted_item = format(item, ".3f")
                output_file.write(str(formatted_item))
                if i % 10 == 0:
                    output_file.write("\n")
                else:
                    output_file.write("\t")

    def save_final_file(self, dens_type, file_path, chop):
        """wrapper to all 4 saving functions"""
        file_suffix = f"-{dens_type}-chopped-x{chop}.vasp"
        file_path = file_path + file_suffix
        method_name = f"save_{dens_type}_file"
        save_method = getattr(poscar, method_name, None)

        if save_method:
            save_method(file_path, int(chop))
        else:
            pass
            
def parse_file_range(file_range):
    """parse the range of files to be chopped
    Returns:
    ---------------------
        set
            set of numbers of files to be chopped"""
    result = set()
    ranges = file_range.split(',')

    for r in ranges:
        if '-' in r:
            start, end = map(int, r.split('-'))
            result.update(range(start, end + 1))
        else:
            result.add(int(r))

    return result

def find_files_in_range(directory, file_range):
    """find all files that are chosen to be chopped in a current directory
    Returns:
    --------------
    list
        list of files to be chopped
    """
    target_numbers = parse_file_range(file_range)
    file_pattern = re.compile(r'\d+')

    matching_files = []
    for filename in os.listdir(directory):
        match = file_pattern.search(filename)
        if match:
            file_number = int(match.group())
            if file_number in target_numbers:
                matching_files.append(filename)

    return matching_files
    
if __name__ == "__main__":
    # take argumens from user - chop number, density type, file range
    chop_number = sys.argv[1]
    dens_type = sys.argv[2:]
    user_input = input("Enter file range (eg. 0001-0050,83,85) or type all if you want to proceed all files in directory:")

    print(f'choping factor: {chop_number}')
    print(f'type of output file: {dens_type}')
    
    current_directory = os.getcwd()
    if user_input == "all":
        sorted_filenames = sorted(os.listdir(current_directory))
    elif user_input == "CHGCAR":
        sorted_filenames = ["CHGCAR"]
    elif user_input == "LOCPOT":
        sorted_filenames = ["LOCPOT"]
    else:
        matching_files = find_files_in_range(current_directory, user_input)
        sorted_filenames = sorted(matching_files)
        
    for filename in sorted_filenames:
        if filename.startswith("PARCHG") or filename.startswith("CHGCAR") or filename.startswith("LOCPOT"):
            tic = time.time()
            filepath = os.path.join(current_directory, filename)
            if os.path.isfile(filepath):
                print_colored_message(f'processing: {filename}', Colors.GREEN)
                poscar = PoscarParser(filepath, chop_number)
                for type in dens_type:
                    if type in ['alfa', 'beta', 'total', 'spin', 'all']:
                        print(f'saving {type}')
                        poscar.save_final_file(type, filepath, chop_number)
                    else:
                        print_colored_message(
                            'splitting method not included. check spelling! Acceptable types: alfa,beta,total,spin,all',
                            Colors.RED)
                toc = time.time()
                print_colored_message(f'file processed. Timing: {toc - tic} s', Colors.GREEN)
                print_colored_message(
                    "##################################################################################################################",
                    Colors.YELLOW)

    total_toc = time.time()
    print_colored_message(
        "##################################################################################################################",
        Colors.YELLOW)
    print("\n")
    print("Job finished. Total_time: ", total_toc - total_tic, " s")
