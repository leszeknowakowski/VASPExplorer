import sys
import code
import traceback
import rlcompleter
import re
import keyword
from io import StringIO
from PyQt5.QtWidgets import QPlainTextEdit, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class PythonConsole(QPlainTextEdit):
    def __init__(self, local_vars=None, parent=None):
        super().__init__(parent)
        self.prompt = '>>> '
        self.continuation_prompt = '... '
        self.buffer = ''
        self.locals = local_vars if local_vars else {}
        self.console = code.InteractiveConsole(self.locals)
        self.completer = rlcompleter.Completer(self.locals)
        self.history = []
        self.history_index = -1
        self.in_multiline = False
        self.setStyleSheet("background-color: white; color: black; font-family: monospace;")
        self.highlighter = PythonHighlighter(self.document())
        self.setWordWrapMode(False)

        self.completion_popup = QListWidget(self)
        self.completion_popup.setWindowFlags(Qt.ToolTip)  # ✅ Fix for GUI blocking
        self.completion_popup.setMaximumHeight(150)
        self.completion_popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.completion_popup.itemClicked.connect(self.insertCompletion)
        self.completion_popup.hide()

        self.insertPrompt()

    def insertPrompt(self):
        prompt = self.continuation_prompt if self.in_multiline else self.prompt
        self.appendPlainText(prompt)

    def getCurrentLine(self):
        text = self.toPlainText().splitlines()
        if not text:
            return ''
        last_line = text[-1]
        prompt = self.continuation_prompt if self.in_multiline else self.prompt
        return last_line[len(prompt):] if last_line.startswith(prompt) else last_line

    def replaceCurrentLine(self, new_text):
        cursor = self.textCursor()
        cursor.select(cursor.LineUnderCursor)
        cursor.removeSelectedText()
        prompt = self.continuation_prompt if self.in_multiline else self.prompt
        cursor.insertText(prompt + new_text)

    def keyPressEvent(self, event):
        if self.completion_popup.isVisible():
            if event.key() in (Qt.Key_Up, Qt.Key_Down):
                self.completion_popup.setFocus()
                self.completion_popup.keyPressEvent(event)
                self.setFocus()
                return
            elif event.key() in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter):
                self.insertCompletion(self.completion_popup.currentItem())
                return
            elif event.key() == Qt.Key_Escape:
                self.completion_popup.hide()
                return

        if event.key() == Qt.Key_Return:
            cursor = self.textCursor()
            cursor.movePosition(cursor.End)
            self.setTextCursor(cursor)
            line = self.getCurrentLine()

            self.history.append(line)
            self.history_index = len(self.history)
            self.buffer += line + '\n'

            stdout_backup = sys.stdout
            stderr_backup = sys.stderr
            sys.stdout = sys.stderr = StringIO()

            try:
                more = self.console.push(line)
                output = sys.stdout.getvalue()
            except Exception:
                output = traceback.format_exc()
                more = False
            finally:
                sys.stdout = stdout_backup
                sys.stderr = stderr_backup

            if output.strip():
                self.appendPlainText(output)

            self.in_multiline = more
            if not more:
                self.buffer = ''

            self.insertPrompt()

        elif event.key() == Qt.Key_Backspace:
            cursor = self.textCursor()
            min_pos = len(self.continuation_prompt) if self.in_multiline else len(self.prompt)
            if cursor.positionInBlock() > min_pos:
                super().keyPressEvent(event)

        elif event.key() == Qt.Key_Up:
            if self.history:
                self.history_index = max(0, self.history_index - 1)
                self.replaceCurrentLine(self.history[self.history_index])

        elif event.key() == Qt.Key_Down:
            if self.history:
                self.history_index = min(len(self.history) - 1, self.history_index + 1)
                if self.history_index < len(self.history):
                    self.replaceCurrentLine(self.history[self.history_index])

        elif event.key() == Qt.Key_Tab:
            self.showCompletions()

        else:
            super().keyPressEvent(event)

    def showCompletions(self):
        line = self.getCurrentLine()
        match = re.search(r'([\w.]+)$', line)
        if not match:
            return

        prefix = match.group(1)
        completions = []
        i = 0
        while True:
            comp = self.completer.complete(prefix, i)
            if comp is None:
                break
            completions.append(comp)
            i += 1

        if not completions:
            return
        elif len(completions) == 1:
            new_line = line[:-len(prefix)] + completions[0]
            self.replaceCurrentLine(new_line)
            return

        # Multiple completions → show popup
        self.completion_popup.clear()
        for full in completions:
            label = full.split('.')[-1]  # ✅ Show only last segment
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, full)  # ✅ Store full completion
            self.completion_popup.addItem(item)

        cursor_rect = self.cursorRect()
        pos = self.mapToGlobal(cursor_rect.bottomRight())
        self.completion_popup.move(pos)
        self.completion_popup.setCurrentRow(0)
        self.completion_popup.show()

    def insertCompletion(self, item):
        if item is None:
            self.completion_popup.hide()
            return

        full_completion = item.data(Qt.UserRole)
        line = self.getCurrentLine()
        match = re.search(r'([\w.]+)$', line)
        if not match:
            return

        prefix = match.group(1)
        new_line = line[:-len(prefix)] + full_completion
        self.replaceCurrentLine(new_line)
        self.completion_popup.hide()


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.formats = {}

        def make_format(color, bold=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Bold)
            return fmt

        self.formats['keyword'] = make_format("blue", bold=True)
        self.formats['builtin'] = make_format("purple")
        self.formats['string'] = make_format("darkgreen")
        self.formats['comment'] = make_format("darkgray")
        self.formats['number'] = make_format("darkred")

        self.rules = []

        # Keywords
        keywords = keyword.kwlist
        self.rules += [(re.compile(r'\b%s\b' % w), self.formats['keyword']) for w in keywords]

        # Builtins
        builtins = dir(__builtins__)
        self.rules += [(re.compile(r'\b%s\b' % w), self.formats['builtin']) for w in builtins]

        # Strings
        self.rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), self.formats['string']))
        self.rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), self.formats['string']))

        # Comments
        self.rules.append((re.compile(r'#.*'), self.formats['comment']))

        # Numbers
        self.rules.append((re.compile(r'\b[0-9]+(\.[0-9]*)?\b'), self.formats['number']))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)