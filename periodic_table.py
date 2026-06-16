import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QAbstractItemView, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)


ELEMENTS = [
    ["H", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "He"],
    ["Li", "Be", "", "", "", "", "", "", "", "", "", "", "B", "C", "N", "O", "F", "Ne"],
    ["Na", "Mg", "", "", "", "", "", "", "", "", "", "", "Al", "Si", "P", "S", "Cl", "Ar"],
    ["K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr"],
    ["Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe"],
    ["Cs", "Ba", "", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn"],
    ["Fr", "Ra", "", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og"],
    ["", "", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", ""],
    ["", "", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", ""],
]

CATEGORIES = {
    "alkali metal": {"Li", "Na", "K", "Rb", "Cs", "Fr"},
    "alkaline earth": {"Be", "Mg", "Ca", "Sr", "Ba", "Ra"},
    "transition metal": {
        "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
        "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
        "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
        "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn",
    },
    "post-transition metal": {"Al", "Ga", "In", "Sn", "Tl", "Pb", "Bi", "Nh", "Fl", "Mc", "Lv"},
    "metalloid": {"B", "Si", "Ge", "As", "Sb", "Te", "Po"},
    "reactive nonmetal": {"H", "C", "N", "O", "P", "S", "Se"},
    "halogen": {"F", "Cl", "Br", "I", "At", "Ts"},
    "noble gas": {"He", "Ne", "Ar", "Kr", "Xe", "Rn", "Og"},
    "lanthanide": {"La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu"},
    "actinide": {"Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr"},
}

CATEGORY_COLORS = {
    "alkali metal": "#9b5f3d",
    "alkaline earth": "#a37d3d",
    "transition metal": "#416a95",
    "post-transition metal": "#55705b",
    "metalloid": "#6c6a3f",
    "reactive nonmetal": "#34746d",
    "halogen": "#7d5b9a",
    "noble gas": "#586a86",
    "lanthanide": "#7b6144",
    "actinide": "#7d4f5c",
}


def element_category(symbol):
    for category, symbols in CATEGORIES.items():
        if symbol in symbols:
            return category
    return "element"


class PeriodicTable(QWidget):
    """
    Clickable periodic-table picker.

    Emits:
        element_selected(str): the selected element symbol.
    """

    element_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("periodicTableWindow")
        self.table = QTableWidget(self)
        self.table.setObjectName("periodicTable")
        self.table.setRowCount(len(ELEMENTS))
        self.table.setColumnCount(18)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().hide()
        self.table.verticalHeader().hide()
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setFocusPolicy(Qt.NoFocus)

        self.populate_table()

        for col in range(18):
            self.table.setColumnWidth(col, 48)
        for row in range(len(ELEMENTS)):
            self.table.setRowHeight(row, 46)

        self.table.cellClicked.connect(self.cell_was_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.table)

        self.setWindowTitle("Periodic Table")
        self.resize(910, 465)
        self.setStyleSheet("""
            QWidget#periodicTableWindow {
                background-color: #11161c;
                color: #dce5ee;
            }

            QTableWidget#periodicTable {
                background-color: #11161c;
                border: 1px solid #27313d;
                border-radius: 8px;
                padding: 8px;
                gridline-color: transparent;
            }

            QTableWidget#periodicTable::item {
                color: #f6f8fa;
                border: 1px solid #1c2631;
                border-radius: 7px;
                padding: 4px;
            }

            QTableWidget#periodicTable::item:hover {
                border: 2px solid #edf4fa;
            }

            QTableWidget#periodicTable::item:selected {
                color: #ffffff;
                border: 2px solid #d4a84f;
            }
        """)

    def populate_table(self):
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)

        for row, element_row in enumerate(ELEMENTS):
            for col, symbol in enumerate(element_row):
                if not symbol:
                    continue

                category = element_category(symbol)
                item = QTableWidgetItem(symbol)
                item.setData(Qt.UserRole, symbol)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(font)
                item.setForeground(QBrush(QColor("#f6f8fa")))
                item.setBackground(QBrush(QColor(CATEGORY_COLORS.get(category, "#405064"))))
                item.setToolTip(category.title())
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, col, item)

    def cell_was_clicked(self, row, col):
        item = self.table.item(row, col)
        if item:
            element_name = item.data(Qt.UserRole) or item.text()
            self.element_selected.emit(element_name)
            self.close()


def main():
    app = QApplication(sys.argv)
    window = PeriodicTable()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
