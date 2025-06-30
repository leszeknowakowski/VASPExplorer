import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QTextEdit, QMenuBar, QAction, QDialog, QSplitter)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QFont


class HelpDialog(QDialog):
    """Dedicated help window with web content"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Guide")
        self.setGeometry(200, 200, 1000, 700)

        # Create main layout
        main_layout = QHBoxLayout()

        # Create left sidebar for navigation
        sidebar = QWidget()
        sidebar.setMaximumWidth(250)
        sidebar.setStyleSheet("background-color: #f0f0f0; border-right: 1px solid #ccc;")
        sidebar_layout = QVBoxLayout(sidebar)

        # Search box
        search_label = QLabel("Search:")
        search_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search documentation...")
        self.search_input.textChanged.connect(self.search_content)
        sidebar_layout.addWidget(search_label)
        sidebar_layout.addWidget(self.search_input)

        # Navigation menu
        nav_label = QLabel("Navigation:")
        nav_label.setFont(QFont("Arial", 9, QFont.Bold))
        nav_label.setStyleSheet("margin-top: 15px;")
        sidebar_layout.addWidget(nav_label)

        # Menu buttons
        self.menu_buttons = []
        menu_items = [
            ("🏠 Overview", "overview"),
            ("🚀 Getting Started", "getting-started"),
            ("✨ Features", "features"),
            ("⌨️ Shortcuts", "shortcuts"),
            ("🔧 How to Use", "how-to-use"),
            ("💡 Tips & Tricks", "tips"),
            ("🆘 Troubleshooting", "troubleshooting")
        ]

        for text, section_id in menu_items:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px 12px;
                    border: none;
                    background: transparent;
                    color: #333;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                    border-radius: 4px;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
            """)
            btn.clicked.connect(lambda checked, sid=section_id: self.navigate_to_section(sid))
            sidebar_layout.addWidget(btn)
            self.menu_buttons.append(btn)

        # Add stretch to push everything to top
        sidebar_layout.addStretch()

        # Create right content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # Create web view for help content
        self.web_view = QWebEngineView()

        # Load help content
        help_html = self.create_help_content()
        self.web_view.setHtml(help_html)

        content_layout.addWidget(self.web_view)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        content_layout.addWidget(close_btn)

        # Add widgets to main layout
        main_layout.addWidget(sidebar)
        main_layout.addWidget(content_widget)

        self.setLayout(main_layout)

    def navigate_to_section(self, section_id):
        """Navigate to a specific section"""
        script = f"document.getElementById('{section_id}').scrollIntoView({{behavior: 'smooth'}});"
        self.web_view.page().runJavaScript(script)

    def search_content(self, search_text):
        """Search and highlight content"""
        if search_text.strip():
            # Clear previous highlights
            self.web_view.page().runJavaScript("window.find('');")
            # Search for new text
            script = f"""
                if (window.find) {{
                    window.find('{search_text}', false, false, true);
                }}
            """
            self.web_view.page().runJavaScript(script)
        else:
            # Clear highlights when search is empty
            self.web_view.page().runJavaScript("window.find('');")

    def create_help_content(self):
        """Create HTML help content with navigation anchors"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Simple Text Editor - User Guide</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    line-height: 1.6;
                    background-color: #f9f9f9;
                }
                .container {
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                }
                h2 {
                    color: #34495e;
                    margin-top: 30px;
                    scroll-margin-top: 20px;
                }
                .feature {
                    background: #ecf0f1;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 5px;
                    border-left: 4px solid #3498db;
                }
                .shortcut {
                    background: #e8f4f8;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-family: monospace;
                    font-weight: bold;
                }
                ul {
                    padding-left: 20px;
                }
                li {
                    margin: 5px 0;
                }
                .warning {
                    background: #fff3cd;
                    border: 1px solid #ffeaa7;
                    padding: 10px;
                    border-radius: 4px;
                    margin: 10px 0;
                }
                .search-highlight {
                    background-color: yellow;
                    padding: 2px;
                    border-radius: 2px;
                }
                .section {
                    margin-bottom: 40px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <section id="overview" class="section">
                    <h1>📝 Simple Text Editor - User Guide</h1>
                    <p>Welcome to Simple Text Editor! This comprehensive guide will help you master all the features and capabilities of this powerful yet simple text editing application.</p>
                </section>

                <section id="getting-started" class="section">
                    <h2>🚀 Getting Started</h2>
                    <p>Welcome to Simple Text Editor! This application provides basic text editing functionality with a clean, easy-to-use interface.</p>
                    <p>To start using the application:</p>
                    <ol>
                        <li>Launch the application</li>
                        <li>Click in the main text area</li>
                        <li>Start typing your content</li>
                        <li>Use the quick note feature for additional thoughts</li>
                    </ol>
                </section>

                <section id="features" class="section">
                    <h2>✨ Main Features</h2>

                    <div class="feature">
                        <h3>Text Editor</h3>
                        <p>The main text area supports:</p>
                        <ul>
                            <li>Rich text editing with multiple formatting options</li>
                            <li>Copy, cut, and paste operations</li>
                            <li>Unlimited undo/redo functionality</li>
                            <li>Text formatting and styling</li>
                            <li>Context menu with additional options</li>
                        </ul>
                    </div>

                    <div class="feature">
                        <h3>Quick Notes</h3>
                        <p>Use the note input field to quickly jot down ideas. Click "Add Note" to append them to your main document with automatic timestamps.</p>
                    </div>

                    <div class="feature">
                        <h3>Character Counter</h3>
                        <p>The status bar shows the current character count of your document in real-time, perfect for social media posts or length-limited content.</p>
                    </div>

                    <div class="feature">
                        <h3>Help System</h3>
                        <p>Integrated help documentation with search functionality and easy navigation. Access via F1 key or Help menu.</p>
                    </div>
                </section>

                <section id="shortcuts" class="section">
                    <h2>⌨️ Keyboard Shortcuts</h2>
                    <p>Master these keyboard shortcuts to boost your productivity:</p>
                    <ul>
                        <li><span class="shortcut">Ctrl+C</span> - Copy selected text</li>
                        <li><span class="shortcut">Ctrl+V</span> - Paste text from clipboard</li>
                        <li><span class="shortcut">Ctrl+X</span> - Cut selected text</li>
                        <li><span class="shortcut">Ctrl+Z</span> - Undo last action</li>
                        <li><span class="shortcut">Ctrl+Y</span> - Redo last action</li>
                        <li><span class="shortcut">Ctrl+A</span> - Select all text</li>
                        <li><span class="shortcut">F1</span> - Open this help guide</li>
                        <li><span class="shortcut">Enter</span> - Add quick note (when in note field)</li>
                    </ul>
                </section>

                <section id="how-to-use" class="section">
                    <h2>🔧 How to Use</h2>

                    <h3>Writing Text</h3>
                    <p>Simply click in the main text area and start typing. Your text will appear immediately and the character count will update automatically in the status bar.</p>

                    <h3>Adding Quick Notes</h3>
                    <ol>
                        <li>Type your note in the "Quick Note" field at the bottom</li>
                        <li>Click the "Add Note" button or press Enter</li>
                        <li>Your note will be added to the main text area with a timestamp</li>
                        <li>The note field will clear automatically for the next entry</li>
                    </ol>

                    <h3>Clearing Content</h3>
                    <p>Click the "Clear All" button to remove all text from the editor. A confirmation dialog will appear to prevent accidental deletion.</p>

                    <h3>Using the Help System</h3>
                    <p>Access help by pressing F1 or selecting Help → User Guide from the menu. Use the search box to find specific topics quickly.</p>

                    <div class="warning">
                        <strong>⚠️ Note:</strong> This application doesn't automatically save your work. Make sure to copy important text to another application or document before closing.
                    </div>
                </section>

                <section id="tips" class="section">
                    <h2>💡 Tips & Tricks</h2>
                    <ul>
                        <li>Use the character counter to keep track of text length for social media posts</li>
                        <li>The quick note feature is perfect for brainstorming sessions and meeting notes</li>
                        <li>You can resize the window to fit your workflow and screen setup</li>
                        <li>Right-click in the text area for context menu options</li>
                        <li>Use the search function in help to quickly find specific information</li>
                        <li>The navigation menu in help allows quick jumping between sections</li>
                        <li>Keep the help window open while working for quick reference</li>
                        <li>Timestamps in quick notes help track when ideas were added</li>
                    </ul>
                </section>

                <section id="troubleshooting" class="section">
                    <h2>🆘 Troubleshooting</h2>

                    <h3>Application Won't Start</h3>
                    <p>Make sure you have all required packages installed:</p>
                    <ul>
                        <li><span class="shortcut">pip install PyQt5</span></li>
                        <li><span class="shortcut">pip install PyQtWebEngine</span></li>
                    </ul>

                    <h3>Text Disappears</h3>
                    <p>Check if you accidentally clicked "Clear All". Unfortunately, this action cannot be undone, but you should have received a confirmation dialog first.</p>

                    <h3>Help Window Won't Open</h3>
                    <p>Ensure PyQtWebEngine is installed: <span class="shortcut">pip install PyQtWebEngine</span></p>

                    <h3>Search Not Working</h3>
                    <p>The search function requires PyQtWebEngine. Make sure it's properly installed and try restarting the application.</p>

                    <h3>Performance Issues</h3>
                    <p>If the application runs slowly, try:</p>
                    <ul>
                        <li>Closing other applications to free up memory</li>
                        <li>Reducing the amount of text in the editor</li>
                        <li>Restarting the application</li>
                    </ul>

                    <h3>Menu Not Responding</h3>
                    <p>Try clicking on different menu items or pressing F1 to open help. If the issue persists, restart the application.</p>
                </section>

                <hr style="margin: 30px 0;">
                <p style="text-align: center; color: #7f8c8d;">
                    <small>Simple Text Editor v1.0 | Built with PyQt5 | Enhanced Help System</small>
                </p>
            </div>
        </body>
        </html>
        """


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Text Editor")
        self.setGeometry(100, 100, 600, 500)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create menu bar
        self.create_menu_bar()

        # Main text editor
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Start typing your text here...")
        self.text_editor.textChanged.connect(self.update_char_count)
        layout.addWidget(self.text_editor)

        # Bottom section with quick note input
        bottom_layout = QHBoxLayout()

        # Quick note input
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Quick note...")
        self.note_input.returnPressed.connect(self.add_note)
        bottom_layout.addWidget(QLabel("Quick Note:"))
        bottom_layout.addWidget(self.note_input)

        # Buttons
        add_note_btn = QPushButton("Add Note")
        add_note_btn.clicked.connect(self.add_note)
        bottom_layout.addWidget(add_note_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all)
        bottom_layout.addWidget(clear_btn)

        layout.addLayout(bottom_layout)

        # Status bar
        self.status_bar = self.statusBar()
        self.char_count_label = QLabel("Characters: 0")
        self.status_bar.addWidget(self.char_count_label)

        # Help dialog instance
        self.help_dialog = None

    def create_menu_bar(self):
        """Create menu bar with help option"""
        menubar = self.menuBar()

        # Help menu
        help_menu = menubar.addMenu('Help')

        # Help action
        help_action = QAction('User Guide', self)
        help_action.setShortcut('F1')
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

        # About action
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_help(self):
        """Show help dialog with web content"""
        if self.help_dialog is None:
            self.help_dialog = HelpDialog(self)
        self.help_dialog.show()
        self.help_dialog.raise_()
        self.help_dialog.activateWindow()

    def show_about(self):
        """Show simple about dialog"""
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.about(self, "About Simple Text Editor",
                          "Simple Text Editor v1.0\n\n"
                          "A basic text editor with integrated help system.\n"
                          "Built with PyQt5 and QWebEngineView.\n\n"
                          "Press F1 for the complete user guide.")

    def add_note(self):
        """Add quick note to main text area"""
        note_text = self.note_input.text().strip()
        if note_text:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_note = f"\n[{timestamp}] {note_text}\n"
            self.text_editor.append(formatted_note)
            self.note_input.clear()

    def clear_all(self):
        """Clear all text from editor"""
        from PyQt5.QtWidgets import QMessageBox

        reply = QMessageBox.question(self, 'Clear All',
                                     'Are you sure you want to clear all text?',
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.text_editor.clear()

    def update_char_count(self):
        """Update character count in status bar"""
        char_count = len(self.text_editor.toPlainText())
        self.char_count_label.setText(f"Characters: {char_count}")


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Simple Text Editor")
    app.setApplicationVersion("1.0")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Start event loop
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()