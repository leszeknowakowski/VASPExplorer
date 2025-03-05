from PyQt5.QtWidgets import QTabBar, QTabWidget, QMainWindow, QApplication
from PyQt5.QtGui import QCloseEvent, QIcon,QMouseEvent
from PyQt5.QtCore import Qt

class DraggableTabBar(QTabBar):
    """Custom TabBar to enable drag & drop of tabs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.drag_start_pos = None

    def mousePressEvent(self, event: QMouseEvent):
        """Detect when a tab is clicked."""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Start dragging if mouse moves beyond a threshold."""
        if event.buttons() == Qt.LeftButton and self.drag_start_pos:
            distance = (event.pos() - self.drag_start_pos).manhattanLength()
            if distance > QApplication.startDragDistance():
                self.drag_start_pos = None  # Prevent multiple drag starts
                self.detachTab(self.tabAt(event.pos()))
        super().mouseMoveEvent(event)

    def detachTab(self, index):
        """Detach the tab at the given index into a new window."""
        if index == -1:
            return

        tab_widget = self.parent()  # The QTabWidget this bar belongs to
        tab_content = tab_widget.widget(index)
        tab_name = tab_widget.tabText(index)

        if not tab_content:
            return

        # Remove tab from main window
        tab_widget.removeTab(index)

        # Create a new detached window
        new_window = FloatingWindow(tab_name, tab_content, tab_widget)
        tab_widget.parent().floating_windows.append(new_window)  # Keep reference
        new_window.show()


class DraggableTabWidget(QTabWidget):
    """Custom TabWidget that uses our draggable tab bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(DraggableTabBar(self))
        self.setTabsClosable(False)  # No close button for now


class FloatingWindow(QMainWindow):
    """Floating window that holds a detached tab."""

    def __init__(self, title, content_widget, parent_tab_widget):
        super().__init__()
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 400, 300)

        # Store reference to original tab widget for reattachment
        self.parent_tab_widget = parent_tab_widget

        # Set the central widget
        self.setCentralWidget(content_widget)
        content_widget.show()

    def closeEvent(self, event):
        """Reattach the tab when the window is closed."""
        self.parent_tab_widget.addTab(self.centralWidget(), self.windowTitle())
        event.accept()