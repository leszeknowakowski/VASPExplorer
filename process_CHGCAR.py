#########################################################################
# python script to reduce PARCHG points grid  and save chopped		#
# files with different outup, eg. total or spin density			#
# and alfa or beta channel partial density.				#
#									#
# Created by Leszek Nowakowski, Cracow 2023				#
# initial version: 30.05.2023						#
# switching to Python: 3.10.2023					#
# adding total/spin/alfa/beta channel functionality: 07.01.2024		#
# adding user input file range: 22.02.2024				#
# switching to ASE: 24.06.2025                          #
#									#
# usage:								#
# python3 /path/to/script chopping-factor output-type			#
# run script in directory when You want the files to be			#
# converted and add arguments -  chopping factor (how many times array	#
# of points should be donwgraded) and output file type (total, spin,	#
# alfa or beta partial electron density).				#
# You can use multiple type output, eg. "alfa" "beta"			#
# As input you can specify an array of files, eg. 1-10 or 1,4,10		#
#									#
#########################################################################

import time
import sys
import os
import re
from PyQt5.QtCore import pyqtSignal, QThread, QObject
try:
    from memory_profiler import profile
except ImportError:
    pass
from VASPparser import PoscarParser as _PoscarParser

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

class CHGCARParser(QThread):
    """class to parse VASP CHG files
    Parameters
    ------------------
    filename: str
        CHGCAR filename
    chop_number: int
        how many times CHGCAR grid should be shrinked (helps to save memory)
    """
    progress = pyqtSignal(int)
    change_label = pyqtSignal(str)

    def __init__(self, filename, chop_number):
        super().__init__()
        self.filename = filename
        self.chop_number = int(chop_number)
        self._unit_cell_vectors = None
        self._grid = None
        self.alfa = None
        self.beta = None

    #@profile
    def run(self):
        """ runs new thread (if class object is run with start() method) and
        reads the CHGCAR file content"""
        self.chgcar = VaspChargeDensity(self.filename, initialize=False)
        self.chgcar.progress.connect(self.update_progress)
        self.chgcar.change_label.connect(self.update_label)
        self.chgcar.run()
        common_divisors = self.common_divisors(*self.chgcar._grid)
        self.all_numbers = [self.chop(self.chgcar.chg[0], self.chop_number), self.chop(self.chgcar.chgdiff[0], self.chop_number)]
        self.atoms = self.chgcar.atoms[0]
        self.aug = self.chgcar.aug
        self.aug_diff = self.chgcar.augdiff


    def update_progress(self, progress):
        self.progress.emit(progress)

    def update_label(self, text):
        self.change_label.emit(text)

    def calc_alfa_beta(self):
        """calculate alfa and beta density
        Returns:
            np.array
                with alfa charge density
            np.array
                with beta density
        """
        if self.alfa is None:
            [total_density, spin_density] = self.all_numbers
            sum_total = 2 * total_density
            sum_spin = 2 * spin_density
            alfa_density = (sum_total + sum_spin) / 4
            beta_density = (sum_total - sum_spin) / 4
            self.alfa = alfa_density
            self.beta = beta_density
            return alfa_density, beta_density

    def voxel_size(self):
        vecs = self.atoms.cell.cellpar()[:3]
        grid = self.chgcar._grid

        voxel_size = vecs / grid

        return voxel_size

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

    def chop(self, grid, chop_number):
        z = grid.shape[2]
        y = grid.shape[0]
        x = grid.shape[1]
        divisors = self.common_divisors(z, y, x)
        if chop_number in divisors:
            return grid[:x:chop_number, :y:chop_number, :z:chop_number]

    def read_augmentation(self, aug):
        lines = aug.split("\n")

        # Parsed results and leftovers storage
        atoms = {}
        leftovers = []
        j = 0  # Initialize the line index

        while j < len(lines):
            line = lines[j].strip()
            if line.startswith("augmentation"):
                # Extract atom number and number of occupancies
                parts = line.split()
                atom_number = int(parts[2])
                num_occupancies = int(parts[3])
                occupancies = []

                # Read as many numbers as needed for occupancies
                j += 1
                while len(occupancies) < num_occupancies and j < len(lines):
                    numbers = list(map(float, lines[j].split()))
                    occupancies.extend(numbers)
                    j += 1

                # Store the data for the current atom
                atoms[atom_number] = occupancies[:num_occupancies]
            else:
                # Collect leftovers (numbers associated with the last atom)
                leftovers.extend(list(map(float, lines[j].split())))
                j += 1
        return atoms, leftovers

    def tile_dict_and_list(self, d, lst, times):
        if lst is None:
            lst = []

        if not isinstance(lst, list):
            raise TypeError("Second argument must be a list or None.")

        if len(lst) != 0 and len(lst) != len(d):
            raise ValueError("List must be either empty or the same length as the dictionary.")

        new_dict = {}
        new_list = []
        key_counter = 1

        for i, value in enumerate(d.values()):
            for _ in range(times):
                new_dict[key_counter] = value.copy()
                if lst:
                    new_list.append(lst[i])
                key_counter += 1

        return new_dict, new_list

    def format_numbers(self, numbers, format, per_line=5):
        """Format a list of numbers into a string with a specified number per line."""
        lines = []
        for i in range(0, len(numbers), per_line):
            if format == "aug":
                line = " ".join(f"{num: .7E}" for num in numbers[i:i + per_line])
            elif format == "leftovers":
                line = " ".join(f"{num: .12E}" for num in numbers[i:i + per_line])
            lines.append(" "+line)
        return "\n".join(lines)

    def rebuild_string(self, atoms, leftovers):
        """Rebuild the original string with updated atoms and leftovers."""
        result = []

        # Write occupancies for each atom
        for atom_key in sorted(atoms.keys()):
            occupancies = atoms[atom_key]
            result.append(f"augmentation occupancies   {atom_key} {len(occupancies)}")
            result.append(self.format_numbers(occupancies, "aug"))

        # Write leftovers at the end
        if leftovers:
            result.append(self.format_numbers(leftovers, "leftovers"))

        return "\n".join(result)

class VaspChargeDensity(QObject):
    """Class for representing VASP charge density.

    Filename is normally CHG."""
    # Can the filename be CHGCAR?  There's a povray tutorial
    # in doc/tutorials where it's CHGCAR as of January 2021.  --askhl
    progress = pyqtSignal(int)
    change_label = pyqtSignal(str)

    def __init__(self, filename, initialize=True):
        super().__init__()
        self.change_label.emit("initializing...")
        # Instance variables
        self.filename = filename
        self.atoms = []  # List of Atoms objects
        self.chg = []  # Charge density
        self.chgdiff = []  # Charge density difference, if spin polarized
        self.aug = ''  # Augmentation charges, not parsed just a big string
        self.augdiff = ''  # Augmentation charge differece, is spin polarized

        # Note that the augmentation charge is not a list, since they
        # are needed only for CHGCAR files which store only a single
        # image.
        if initialize:
            self.run()

    def run(self):
        if self.filename is not None:
            self.read(self.filename)

    def is_spin_polarized(self):
        if len(self.chgdiff) > 0:
            return True
        return False

    def _read_chg(self, fobj, chg, volume, spin=False, debug=False):
        """Read charge from file object

        Utility method for reading the actual charge density (or
        charge density difference) from a file object. On input, the
        file object must be at the beginning of the charge block, on
        output the file position will be left at the end of the
        block. The chg array must be of the correct dimensions.

        """
        # VASP writes charge density as
        # WRITE(IU,FORM) (((C(NX,NY,NZ),NX=1,NGXC),NY=1,NGYZ),NZ=1,NGZC)
        # Fortran nested implied do loops; innermost index fastest
        # First, just read it in
        max_z = chg.shape[2]
        sig_interval = max(1, max_z // 100)  # avoid division by zero

        for i, zz in enumerate(range(max_z)):
            if i % sig_interval == 0:
                # Calculate percentage for this half (0 to 50 or 50 to 100)
                progress_half = int((i / max_z) * 50)
                if not spin:
                    self.progress.emit(progress_half + 1)  # from 1 to 50
                else:
                    self.progress.emit(progress_half + 51)  # from 51 to 100

            for j, yy in enumerate(range(chg.shape[1])):
                chg[:, yy, zz] = np.fromfile(fobj, count=chg.shape[0], sep=' ')

        chg /= volume

    def read(self, filename, debug=False):
        """Read CHG or CHGCAR file.

        If CHG contains charge density from multiple steps all the
        steps are read and stored in the object. By default VASP
        writes out the charge density every 10 steps.

        chgdiff is the difference between the spin up charge density
        and the spin down charge density and is thus only read for a
        spin-polarized calculation.

        aug is the PAW augmentation charges found in CHGCAR. These are
        not parsed, they are just stored as a string so that they can
        be written again to a CHGCAR format file.

        """
        DEBUG = False
        import ase.io.vasp as aiv
        with open(filename) as fd:
            self.atoms = []
            self.chg = []
            self.chgdiff = []
            self.aug = ''
            self.augdiff = ''
            while True:
                try:
                    self.change_label.emit("reading positions...")
                    atoms = aiv.read_vasp_configuration(fd)
                except (KeyError, RuntimeError, ValueError):
                    # Probably an empty line, or we tried to read the
                    # augmentation occupancies in CHGCAR
                    break

                # Note: We continue reading from the same file, and
                # this relies on read_vasp() to read no more lines
                # than it currently does.
                fd.readline()

                ngr = fd.readline().split()
                ng = (int(ngr[0]), int(ngr[1]), int(ngr[2]))
                self._grid = ng
                self.voxel_size = atoms.cell.cellpar()[:3] / self._grid
                self.change_label.emit("Initializing matrices...")
                chg = np.empty(ng)
                self.change_label.emit("reading total density...")
                tic = time.time()
                self._read_chg(fd, chg, atoms.get_volume(), spin=False, debug=DEBUG)
                toc = time.time()
                print(f'reading total denisity: {toc - tic} s')
                self.chg.append(chg)
                self.atoms.append(atoms)
                # Check if the file has a spin-polarized charge density part,
                # and if so, read it in.
                fl = fd.tell()
                # First check if the file has an augmentation charge part
                # (CHGCAR file.)
                line1 = fd.readline()
                if line1 == '':
                    break
                elif line1.find('augmentation') != -1:
                    augs = [line1]
                    while True:
                        line2 = fd.readline()
                        if line2.split() == ngr:
                            self.aug = ''.join(augs)
                            augs = []
                            self.change_label.emit("Initializing matrices...")
                            chgdiff = np.empty(ng)
                            self.change_label.emit("reading spin density...")
                            self._read_chg(fd, chgdiff, atoms.get_volume(), spin=True, debug=DEBUG)
                            self.chgdiff.append(chgdiff)
                        elif line2 == '':
                            break
                        else:
                            augs.append(line2)
                    if len(self.aug) == 0:
                        self.aug = ''.join(augs)
                        augs = []
                    else:
                        self.augdiff = ''.join(augs)
                        augs = []
                elif line1.split() == ngr:
                    self.change_label.emit("Initializing matrices...")
                    chgdiff = np.empty(ng)
                    self.change_label.emit("reading spin density...")
                    self._read_chg(fd, chgdiff, atoms.get_volume(), spin=True, debug=DEBUG)
                    self.chgdiff.append(chgdiff)
                else:
                    fd.seek(fl)

    def _write_chg(self, fobj, chg, volume, format='chg'):
        """Write charge density

        Utility function similar to _read_chg but for writing.

        """
        # Make a 1D copy of chg, must take transpose to get ordering right
        chgtmp = chg.T.ravel()
        # Multiply by volume
        chgtmp = chgtmp * volume
        # Must be a tuple to pass to string conversion
        chgtmp = tuple(chgtmp)
        # CHG format - 10 columns
        if format.lower() == 'chg':
            # Write all but the last row
            for ii in range((len(chgtmp) - 1) // 10):
                fobj.write(' %#11.5G %#11.5G %#11.5G %#11.5G %#11.5G\
 %#11.5G %#11.5G %#11.5G %#11.5G %#11.5G\n' % chgtmp[ii * 10:(ii + 1) * 10])
            # If the last row contains 10 values then write them without a
            # newline
            if len(chgtmp) % 10 == 0:
                fobj.write(' %#11.5G %#11.5G %#11.5G %#11.5G %#11.5G'
                           ' %#11.5G %#11.5G %#11.5G %#11.5G %#11.5G' %
                           chgtmp[len(chgtmp) - 10:len(chgtmp)])
            # Otherwise write fewer columns without a newline
            else:
                for ii in range(len(chgtmp) % 10):
                    fobj.write((' %#11.5G') %
                               chgtmp[len(chgtmp) - len(chgtmp) % 10 + ii])
        # Other formats - 5 columns
        else:
            # Write all but the last row
            for ii in range((len(chgtmp) - 1) // 5):
                fobj.write(' %17.10E %17.10E %17.10E %17.10E %17.10E\n' %
                           chgtmp[ii * 5:(ii + 1) * 5])
            # If the last row contains 5 values then write them without a
            # newline
            if len(chgtmp) % 5 == 0:
                fobj.write(' %17.10E %17.10E %17.10E %17.10E %17.10E' %
                           chgtmp[len(chgtmp) - 5:len(chgtmp)])
            # Otherwise write fewer columns without a newline
            else:
                for ii in range(len(chgtmp) % 5):
                    fobj.write((' %17.10E') %
                               chgtmp[len(chgtmp) - len(chgtmp) % 5 + ii])
        # Write a newline whatever format it is
        fobj.write('\n')

    def write(self, filename, format=None):
        """Write VASP charge density in CHG format.

        filename: str
            Name of file to write to.
        format: str
            String specifying whether to write in CHGCAR or CHG
            format.

        """
        import ase.io.vasp as aiv
        if format is None:
            if filename.lower().find('chgcar') != -1:
                format = 'chgcar'
            elif filename.lower().find('chg') != -1:
                format = 'chg'
            elif len(self.chg) == 1:
                format = 'chgcar'
            else:
                format = 'chg'
        with open(filename, 'w') as fd:
            for ii, chg in enumerate(self.chg):
                if format == 'chgcar' and ii != len(self.chg) - 1:
                    continue  # Write only the last image for CHGCAR
                aiv.write_vasp(fd,
                               self.atoms[ii],
                               direct=True)
                fd.write('\n')
                for dim in chg.shape:
                    fd.write(' %4i' % dim)
                fd.write('\n')
                vol = self.atoms[ii].get_volume()
                self._write_chg(fd, chg, vol, format)
                if format == 'chgcar':
                    fd.write(self.aug)
                if self.is_spin_polarized():
                    if format == 'chg':
                        fd.write('\n')
                    for dim in chg.shape:
                        fd.write(' %4i' % dim)
                    fd.write('\n')  # a new line after dim is required
                    self._write_chg(fd, self.chgdiff[ii], vol, format)
                    if format == 'chgcar':
                        # a new line is always provided self._write_chg
                        fd.write(self.augdiff)
                if format == 'chg' and len(self.chg) > 1:
                    fd.write('\n')


if __name__ == '__main__':
    chgcar = CHGCARParser(r"D:\syncme\modelowanie DFT\CeO2\1.CeO2(100)\CeO2_100_half_Ce\2.large slab\1.1x1x1\1.HSE\CHGCAR", 1)
    chgcar.run()