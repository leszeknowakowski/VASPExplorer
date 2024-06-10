import time

tic = time.perf_counter()
from PyQt5.QtWidgets import QPlainTextEdit
toc = time.perf_counter()
print(f'import QPlainTextEdit {toc-tic:0.4f}')

class ConsoleWidget(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)

    def append_message(self, message):
        self.appendPlainText(message)
