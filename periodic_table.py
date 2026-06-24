import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)


BG = "#1e1e2e"
BG2 = "#252538"
FG = "#cdd6f4"
FG2 = "#a9b1d6"
ACCENT = "#7aa2f7"

GROUP_COLORS = {
    "alkali": "#e06c75",
    "alkaline": "#e0af68",
    "transition": "#61afef",
    "post": "#56b6c2",
    "metalloid": "#98c379",
    "nonmetal": "#c678dd",
    "halogen": "#e5c07b",
    "noble": "#abb2bf",
    "lanthanide": "#7aa2f7",
    "actinide": "#bb9af7",
}

PERIODIC_TABLE = [
    ("H", 1, 1, "nonmetal"), ("He", 18, 1, "noble"),
    ("Li", 1, 2, "alkali"), ("Be", 2, 2, "alkaline"),
    ("B", 13, 2, "metalloid"), ("C", 14, 2, "nonmetal"),
    ("N", 15, 2, "nonmetal"), ("O", 16, 2, "nonmetal"),
    ("F", 17, 2, "halogen"), ("Ne", 18, 2, "noble"),
    ("Na", 1, 3, "alkali"), ("Mg", 2, 3, "alkaline"),
    ("Al", 13, 3, "post"), ("Si", 14, 3, "metalloid"),
    ("P", 15, 3, "nonmetal"), ("S", 16, 3, "nonmetal"),
    ("Cl", 17, 3, "halogen"), ("Ar", 18, 3, "noble"),
    ("K", 1, 4, "alkali"), ("Ca", 2, 4, "alkaline"),
    ("Sc", 3, 4, "transition"), ("Ti", 4, 4, "transition"),
    ("V", 5, 4, "transition"), ("Cr", 6, 4, "transition"),
    ("Mn", 7, 4, "transition"), ("Fe", 8, 4, "transition"),
    ("Co", 9, 4, "transition"), ("Ni", 10, 4, "transition"),
    ("Cu", 11, 4, "transition"), ("Zn", 12, 4, "transition"),
    ("Ga", 13, 4, "post"), ("Ge", 14, 4, "metalloid"),
    ("As", 15, 4, "metalloid"), ("Se", 16, 4, "nonmetal"),
    ("Br", 17, 4, "halogen"), ("Kr", 18, 4, "noble"),
    ("Rb", 1, 5, "alkali"), ("Sr", 2, 5, "alkaline"),
    ("Y", 3, 5, "transition"), ("Zr", 4, 5, "transition"),
    ("Nb", 5, 5, "transition"), ("Mo", 6, 5, "transition"),
    ("Tc", 7, 5, "transition"), ("Ru", 8, 5, "transition"),
    ("Rh", 9, 5, "transition"), ("Pd", 10, 5, "transition"),
    ("Ag", 11, 5, "transition"), ("Cd", 12, 5, "transition"),
    ("In", 13, 5, "post"), ("Sn", 14, 5, "post"),
    ("Sb", 15, 5, "metalloid"), ("Te", 16, 5, "metalloid"),
    ("I", 17, 5, "halogen"), ("Xe", 18, 5, "noble"),
    ("Cs", 1, 6, "alkali"), ("Ba", 2, 6, "alkaline"),
    ("La", 3, 6, "lanthanide"),
    ("Hf", 4, 6, "transition"), ("Ta", 5, 6, "transition"),
    ("W", 6, 6, "transition"), ("Re", 7, 6, "transition"),
    ("Os", 8, 6, "transition"), ("Ir", 9, 6, "transition"),
    ("Pt", 10, 6, "transition"), ("Au", 11, 6, "transition"),
    ("Hg", 12, 6, "transition"), ("Tl", 13, 6, "post"),
    ("Pb", 14, 6, "post"), ("Bi", 15, 6, "post"),
    ("Po", 16, 6, "metalloid"), ("At", 17, 6, "halogen"),
    ("Rn", 18, 6, "noble"),
    ("Fr", 1, 7, "alkali"), ("Ra", 2, 7, "alkaline"),
    ("Ac", 3, 7, "actinide"),
    ("Rf", 4, 7, "transition"), ("Db", 5, 7, "transition"),
    ("Sg", 6, 7, "transition"), ("Bh", 7, 7, "transition"),
    ("Hs", 8, 7, "transition"), ("Mt", 9, 7, "transition"),
    ("Ds", 10, 7, "transition"), ("Rg", 11, 7, "transition"),
    ("Cn", 12, 7, "transition"), ("Nh", 13, 7, "post"),
    ("Fl", 14, 7, "post"), ("Mc", 15, 7, "post"),
    ("Lv", 16, 7, "post"), ("Ts", 17, 7, "halogen"),
    ("Og", 18, 7, "noble"),
    ("Ce", 4, 9, "lanthanide"), ("Pr", 5, 9, "lanthanide"),
    ("Nd", 6, 9, "lanthanide"), ("Pm", 7, 9, "lanthanide"),
    ("Sm", 8, 9, "lanthanide"), ("Eu", 9, 9, "lanthanide"),
    ("Gd", 10, 9, "lanthanide"), ("Tb", 11, 9, "lanthanide"),
    ("Dy", 12, 9, "lanthanide"), ("Ho", 13, 9, "lanthanide"),
    ("Er", 14, 9, "lanthanide"), ("Tm", 15, 9, "lanthanide"),
    ("Yb", 16, 9, "lanthanide"), ("Lu", 17, 9, "lanthanide"),
    ("Th", 4, 10, "actinide"), ("Pa", 5, 10, "actinide"),
    ("U", 6, 10, "actinide"), ("Np", 7, 10, "actinide"),
    ("Pu", 8, 10, "actinide"), ("Am", 9, 10, "actinide"),
    ("Cm", 10, 10, "actinide"), ("Bk", 11, 10, "actinide"),
    ("Cf", 12, 10, "actinide"), ("Es", 13, 10, "actinide"),
    ("Fm", 14, 10, "actinide"), ("Md", 15, 10, "actinide"),
    ("No", 16, 10, "actinide"), ("Lr", 17, 10, "actinide"),
]

ATOMIC_SYMBOLS = [
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
    "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni",
    "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr",
    "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd",
    "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe",
    "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd",
    "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu",
    "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn",
    "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm",
    "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr",
    "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn",
    "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
]
ATOMIC_NUMBERS = {symbol: index + 1 for index, symbol in enumerate(ATOMIC_SYMBOLS)}

COLS = 18
ROWS = 10
GAP = 2


def cell_style(group, selected=False):
    bg = "#ffffff" if selected else GROUP_COLORS.get(group, "#555")
    fg = BG if selected else FG
    border = ACCENT if selected else BG2
    border_width = 2 if selected else 1
    return (
        f"background:{bg}; color:{fg};"
        f"border:{border_width}px solid {border};"
        "border-radius:3px; font-weight:bold; padding:0px;"
    )


class ElementButton(QPushButton):
    def __init__(self, symbol, group, parent=None):
        super().__init__(symbol, parent)
        self.symbol = symbol
        self.group = group
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{symbol} (Z={ATOMIC_NUMBERS.get(symbol, 0)})")
        self.setStyleSheet(cell_style(group))

    def enterEvent(self, event):
        self.setStyleSheet(cell_style(self.group, selected=True))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(cell_style(self.group))
        super().leaveEvent(event)

    def set_cell_font(self, size_pt):
        font = QFont("Segoe UI", max(6, size_pt))
        font.setBold(True)
        self.setFont(font)


class PeriodicGrid(QWidget):
    def __init__(self, buttons_by_position, parent=None):
        super().__init__(parent)
        self.buttons_by_position = buttons_by_position
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(360, 210)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = event.size().width()
        height = event.size().height()

        cell_w = (width - (COLS - 1) * GAP) / COLS
        cell_h = (height - (ROWS - 1) * GAP) / ROWS
        cell = max(18, int(min(cell_w, cell_h)))

        grid_w = cell * COLS + (COLS - 1) * GAP
        grid_h = cell * ROWS + (ROWS - 1) * GAP
        x0 = (width - grid_w) // 2
        y0 = (height - grid_h) // 2
        font_pt = max(6, int(cell * 0.35))

        for (row, col), button in self.buttons_by_position.items():
            x = x0 + col * (cell + GAP)
            y = y0 + row * (cell + GAP)
            button.setGeometry(x, y, cell, cell)
            button.set_cell_font(font_pt)


class PeriodicTable(QWidget):
    element_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("periodicTableWindow")
        self.buttons = {}
        self.setWindowTitle("Periodic Table")
        self.resize(910, 500)
        self._build()
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG};
                color: {FG};
            }}
            QWidget#periodicTableWindow {{
                background-color: {BG};
                color: {FG};
            }}
            QLabel {{
                color: {FG2};
                background: transparent;
            }}
        """)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("Choose an element")
        header.setStyleSheet(f"color:{ACCENT}; font-weight:bold;")
        layout.addWidget(header)

        buttons_by_position = {}
        for symbol, col, row, group in PERIODIC_TABLE:
            button = ElementButton(symbol, group)
            button.clicked.connect(lambda _, sym=symbol: self.select_element(sym))
            self.buttons[symbol] = button
            buttons_by_position[(row - 1, col - 1)] = button

        self.grid = PeriodicGrid(buttons_by_position, self)
        for button in self.buttons.values():
            button.setParent(self.grid)
        layout.addWidget(self.grid, stretch=1)

        legend = QHBoxLayout()
        legend.setSpacing(5)
        for group, label in [
                ("alkali", "Alk"), ("alkaline", "AEar"),
                ("transition", "Trans"), ("post", "Post"),
                ("metalloid", "Mtld"), ("nonmetal", "NMet"),
                ("halogen", "Hal"), ("noble", "Nob"),
                ("lanthanide", "Ln"), ("actinide", "An")]:
            chip = QLabel(f" {label} ")
            chip.setStyleSheet(
                f"background:{GROUP_COLORS[group]}; color:{FG};"
                "border-radius:2px; padding:1px 3px;"
            )
            legend.addWidget(chip)
        legend.addStretch(1)
        layout.addLayout(legend)

    def select_element(self, symbol):
        self.element_selected.emit(symbol)
        self.close()


def main():
    app = QApplication(sys.argv)
    window = PeriodicTable()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
