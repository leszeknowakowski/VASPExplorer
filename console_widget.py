from PyQt5.QtWidgets import QPlainTextEdit

class ConsoleWidget(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)

    def append_message(self, message):
        self.appendPlainText(message)
