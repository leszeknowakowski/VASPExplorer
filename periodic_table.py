import sys
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal

class PeriodicTable(QWidget):
    element_selected = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        # Create the table widget
        self.table = QTableWidget(self)

        # Set the number of rows and columns
        self.table.setRowCount(9)
        self.table.setColumnCount(18)  # 18 columns to fit all elements in first two rows

        # List of first two rows of elements
        elements = [
            ["H", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "He"],
            ["Li", "Be", "", "", "", "", "", "", "", "", "", "", "B", "C", "N", "O", "F", "Ne"],
            ["Na", "Mg", "", "", "", "", "", "", "", "", "", "", "Al", "Si", "P", "S", "Cl", "Ar"],
            ["K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr"],
            ["Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe"],
            ["Cs", "Ba", "",  "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "T", "l", "Pb", "Bi", "Po", "At",
            "Rn"], ["Fr", "Ra", "", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts",
            "Og"],
            ["", "", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er",
            "Tm", "Yb", "Lu"],
            ["", "", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
            "Md", "No", "Lr"]]

        # Insert the elements into the table
        for row in range(len(elements)):
            for col in range(len(elements[row])):
                if elements[row][col]:  # Only place items that are not empty
                    self.table.setItem(row, col, QTableWidgetItem(elements[row][col]))

        # Resize the cells to make them smaller
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

        # Manually set cell size to make them compact
        self.table.setColumnWidth(0, 40)
        self.table.setRowHeight(0, 40)

        # Adjust each column size to be uniform
        for col in range(18):
            self.table.setColumnWidth(col, 40)

        for row in range(2):
            self.table.setRowHeight(row, 40)

        self.table.cellClicked.connect(self.cell_was_clicked)

        # Set the layout for the main widget
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)

        # Set window title and size
        self.setWindowTitle("Periodic Table")
        self.resize(880, 420)  # Adjusted size to make sure everything fits

    def cell_was_clicked(self, row, col):
        # Get the clicked element
        item = self.table.item(row, col)
        if item:
            element_name = item.text()
            self.element_selected.emit(element_name)
            self.close()  # Close the window after clicking
def main():
    app = QApplication(sys.argv)
    window = PeriodicTable()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
