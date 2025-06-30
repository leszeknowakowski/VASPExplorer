from PyQt5.QtWidgets import QApplication


class BaderParser:
    def __init__(self):
        self.atoms = []

    def parse(self, file):
        with open(file) as f:
            self.lines = f.readlines()
        header = self.lines[0]
        for line in self.lines[1:]:
            splitted = line.strip().split()
            if splitted[0].isdigit():
                number = splitted[0]
                x = splitted[1]
                y = splitted[2]
                z = splitted[3]
                charge = splitted[4]
                min_dist = splitted[5]
                atomic_vol = splitted[6]
                symbol = splitted[7]
                self.atoms.append([number, x, y, z, charge, symbol])
            if splitted[0] == "VACUUM":
                if splitted[1] == "CHARGE":
                    self.vacuum_charge = float(splitted[2])
                if splitted[1] == "VOLUME":
                    self.vacuum_volume = float(splitted[2])
            if splitted[0] == "NUMBER":
                self.number_of_electrons = float(splitted[3])
            if splitted[0] == "#total":
                self.total_charge = float(splitted[3])


if __name__ == "__main__":
    file = r'D:\syncme\modelowanie DFT\co3o4_new_new\2.ROS\1.large_slab\1.old_random_mag\8.NEB\HSE\02\DOS_new\ACF.dat-corrected'
    acf = BaderParser()
    acf.parse(file)
    print(acf.atoms)


