from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

font = QFont('Noto Serif', 9)


def makebutton(text):
    button = QPushButton()
    button.setFont(font)
    button.setFixedSize(60, 20)
    button.setText(text)
    return button


class Editor(QTextEdit):
    doubleClicked = pyqtSignal(QTextEdit)

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(font)
        self.setFixedHeight(20)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        self.show()
        self.textChanged.connect(self.autoResize)

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        self.doubleClicked.emit(self)

    def autoResize(self):
        self.document().setTextWidth(self.viewport().width())
        margins = self.contentsMargins()
        height = int(self.document().size().height() + margins.top() + margins.bottom())
        self.setFixedHeight(height)

    def resizeEvent(self, event):
        self.autoResize()


class textcell(QVBoxLayout):
    def __init__(self, text):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.label = QLabel(text)
        self.label.setFixedSize(80, 20)
        self.apply = makebutton('Apply')
        self.apply.hide()
        self.editor = Editor()
        self.editor.doubleClicked.connect(self.on_DoubleClick)
        self.hbox = QHBoxLayout()
        self.hbox.addStretch()
        self.hbox.addWidget(self.apply)
        self.addWidget(self.label)
        self.addWidget(self.editor)
        self.addLayout(self.hbox)
        self.apply.clicked.connect(self.on_ApplyClick)

    def on_DoubleClick(self):
        self.editor.setReadOnly(False)
        self.apply.show()

    def on_ApplyClick(self):
        self.editor.setReadOnly(True)
        self.apply.hide()


class songpage(QGroupBox):
    def __init__(self, texts):
        super().__init__()
        self.init(texts)
        self.setCheckable(True)
        self.setChecked(False)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def init(self, texts):
        self.vbox = QVBoxLayout()
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.vbox.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        artist = textcell('Artist')
        artist.editor.setText(texts[0])
        album = textcell('Album')
        album.editor.setText(texts[2])
        title = textcell('Title')
        title.editor.setText(texts[1])
        self.height = 120 + artist.editor.height() + album.editor.height() + title.editor.height()
        self.vbox.addLayout(artist)
        self.vbox.addLayout(album)
        self.vbox.addLayout(title)
        print(self.children())
        print(self.vbox.children())
        print(self.vbox.count())
        print(artist.count())
        print(artist.children())
        print(artist.contentsMargins().top())
        print(artist.contentsMargins().bottom())
        print(self.vbox.contentsMargins().top())
        print(self.vbox.contentsMargins().bottom())
        print(self.contentsMargins().top())
        print(self.contentsMargins().bottom())
        print(self.childrenRect().height())
        print(self.contentsRect().height())
        print(artist.apply.isHidden())
        print(artist.editor.isHidden())
        print(artist.label.isHidden())
        print(artist.label.isVisible())
        print(self.sizeHint().height())
        self.setLayout(self.vbox)
        self.setFixedHeight(self.height)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(405, 720)
        frame = self.frameGeometry()
        center = self.screen().availableGeometry().center()
        frame.moveCenter(center)
        self.move(frame.topLeft())
        self.centralwidget = QWidget(self)
        self.vbox = QVBoxLayout(self.centralwidget)
        self.scrollArea = QScrollArea(self.centralwidget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.verticalLayout = QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.scrollArea.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.add = makebutton('Add')
        self.vbox.addWidget(self.add)
        self.add.clicked.connect(lambda: adder.addItem())
        self.vbox.addWidget(self.scrollArea)
        self.setCentralWidget(self.centralwidget)


class Adder:
    def __init__(self):
        self.i = 0

    def addItem(self):
        window.verticalLayout.addWidget(songpage(items[self.i]))
        if self.i < len(items) - 1:
            self.i += 1


adder = Adder()

items = [('Herbert von Karajan',
          "Orphée aux enfers, 'Orpheus in the Underworld'\u2014Overture",
          '100 Best Karajan'),
         ('Herbert von Karajan', 'Radetzky March Op. 228', '100 Best Karajan'),
         ('Herbert von Karajan',
          'Symphony No. 1 in C, Op. 21\u2014I. Adagio molto \u2014 Allegro con brio',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 1 in C, Op. 21\u2014II. Andante cantabile con moto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 1 in C, Op. 21\u2014III. Menuetto (Allegro molto e vivace)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 1 in C, Op. 21\u2014IV. Finale (Adagio \u2014 Allegro molto e vivace)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 2 in D, Op. 36\u2014I. Adagio molto \u2014 Allegro con brio',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 2 in D, Op. 36\u2014II. Larghetto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 2 in D, Op. 36\u2014III. Scherzo (Allegro)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 2 in D, Op. 36\u2014IV. Allegro molto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 3 in E\u2014Flat, Op. 55 \u2014Eroica\u2014I. Allegro con brio',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 3 in E\u2014Flat, Op. 55 \u2014Eroica\u2014II. Marcia funebre (Adagio assai)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 3 in E\u2014Flat, Op. 55 \u2014Eroica\u2014III. Scherzo (Allegro vivace)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 3 in E\u2014Flat, Op. 55 \u2014Eroica\u2014IV. Finale (Allegro molto)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 4 in B\u2014Flat, Op. 60\u2014I. Adagio \u2014 Allegro vivace',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 4 in B\u2014Flat, Op. 60\u2014II. Adagio',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 4 in B\u2014Flat, Op. 60\u2014III. Allegro vivace',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 4 in B\u2014Flat, Op. 60\u2014IV. Allegro ma non troppo',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 5 in C Minor, Op. 67\u2014I. Allegro con brio',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 5 in C Minor, Op. 67\u2014II. Andante con moto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 5 in C Minor, Op. 67\u2014III. Allegro',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 5 in C Minor, Op. 67\u2014IV. Allegro',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 7 in A, Op. 92\u2014I. Poco sostenuto \u2014 Vivace',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 7 in A, Op. 92\u2014II. Allegretto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 7 in A, Op. 92\u2014III. Presto \u2014 Assai meno presto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 7 in A, Op. 92\u2014IV. Allegro con brio',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 8 in F, Op. 93\u2014I. Allegro vivace e con brio',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 8 in F, Op. 93\u2014II. Allegretto scherzando',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 8 in F, Op. 93\u2014III. Tempo di menuetto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 8 in F, Op. 93\u2014IV. Allegro vivace',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 9 in D Minor, Op. 125 \u2014 Choral\u2014I. Allegro ma non troppo, un poco maestoso',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 9 in D Minor, Op. 125 \u2014 Choral\u2014II. Molto vivace',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 9 in D Minor, Op. 125 \u2014 Choral\u2014III. Adagio molto e cantabile',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 9 in D Minor, Op. 125 \u2014 Choral\u2014IV. Presto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No. 9 in D Minor, Op. 125 \u2014 Choral\u2014V. Presto\u2014 O Freunde, nicht diese T\u2014ne!\u2014Allegro assai',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No.6 in F, Op.68 \u2014Pastoral\u2014I. Erwachen heiterer Empfindungen bei der Ankunft auf dem Lande\u2014 Allegro ma non troppo',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No.6 in F, Op.68 \u2014Pastoral\u2014II. Szene am Bach\u2014 (Andante molto mosso)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No.6 in F, Op.68 \u2014Pastoral\u2014III. Lustiges Zusammensein der Landleute (Allegro)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No.6 in F, Op.68 \u2014Pastoral\u2014IV. Gewitter, Sturm (Allegro)',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Symphony No.6 in F, Op.68 \u2014Pastoral\u2014V. Hirtengesang. Frohe und dankbare Gefühle nach dem Sturm\u2014 Allegretto',
          'Beethoven\u2014 The 9 Symphonies'),
         ('Herbert von Karajan',
          'Cancan (Orpheus in the Underworld)',
          'Best of the Millennium\u2014 Top 40 Classical Hits'),
         ('Herbert von Karajan',
          'Hungarian Dance No. 5 in G Minor, WoO 1 No. 5',
          'Complete Recordings on Deutsche Grammophon')]

app = QApplication([])
window = Window()
window.show()
app.exec()