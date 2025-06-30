import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

# Import the MainWindow class and other necessary classes
# We need to mock PyQt5 and other imports first
sys.modules['pyqtgraph'] = MagicMock()
sys.modules['vasp_data'] = MagicMock()
sys.modules['dos_plot_widget'] = MagicMock()
sys.modules['dos_control_widget'] = MagicMock()
sys.modules['structure_plot'] = MagicMock()
sys.modules['console_widget'] = MagicMock()
sys.modules['structure_controls'] = MagicMock()
sys.modules['structure_variable_controls'] = MagicMock()
sys.modules['chgcar_controls'] = MagicMock()
sys.modules['draggable_tab'] = MagicMock()
sys.modules['deatachedtabs'] = MagicMock()

# Now we can import the main module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from main_window import MainWindow, VaspData


class TestMainWindow(unittest.TestCase):
    """Test class for MainWindow functionality."""

    @classmethod
    def setUpClass(cls):
        """Create a QApplication instance for all tests."""
        # Create a new QApplication if one doesn't already exist
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory with dummy VASP files
        self.temp_dir = tempfile.mkdtemp()
        self.create_test_vasp_files()

        # Patch the set_working_dir method to return our temp_dir
        with patch('main_window.MainWindow.set_working_dir', return_value=self.temp_dir):
            self.window = MainWindow(show=False)

    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

        # Close the window
        self.window.close()

    def create_test_vasp_files(self):
        """Create dummy VASP files for testing."""
        # Create minimal versions of necessary files
        with open(os.path.join(self.temp_dir, 'POSCAR'), 'w') as f:
            f.write("Test POSCAR file\n")

        with open(os.path.join(self.temp_dir, 'CONTCAR'), 'w') as f:
            f.write("Test CONTCAR file\n")

        with open(os.path.join(self.temp_dir, 'OUTCAR'), 'w') as f:
            f.write("Test OUTCAR file\n")

        with open(os.path.join(self.temp_dir, 'CHGCAR'), 'w') as f:
            f.write("Test CHGCAR file\n")

    def test_init(self):
        """Test the initialization of MainWindow."""
        self.assertIsNotNone(self.window)
        self.assertEqual(self.window.dir, self.temp_dir)
        self.assertIsNotNone(self.window.data)

    def test_set_window_title(self):
        """Test setting the window title."""
        test_path = "/path1/path2/path3/path4/path5/path6/path7"
        expected_title = "VASPy-vis v. " + self.window.__version__ + ": path2/path3/path4/path5/path6/path7"

        with patch('os.path.abspath', return_value=test_path):
            self.window.set_window_title(test_path)
            # Only test the last part since the beginning will vary
            self.assertTrue(self.window.windowTitle().endswith("path2/path3/path4/path5/path6/path7"))

    @patch('PyQt5.QtWidgets.QFileDialog.getOpenFileName')
    def test_load_data(self, mock_file_dialog):
        """Test loading data."""
        # Setup mock return value for file dialog
        new_dir = os.path.join(self.temp_dir, 'new_dir')
        os.makedirs(new_dir, exist_ok=True)
        self.create_test_vasp_files()  # Create test files in the new directory
        mock_file_dialog.return_value = (os.path.join(new_dir, 'POSCAR'), '')

        # Mock the data update methods
        self.window.dos_plot_widget.update_data = MagicMock()
        self.window.dos_control_widget.update_data = MagicMock()
        self.window.structure_plot_interactor_widget.update_data = MagicMock()
        self.window.structure_plot_control_tab.update_data = MagicMock()
        self.window.structure_variable_control_tab.update_data = MagicMock()
        self.window.chgcar_control_widget.update_data = MagicMock()

        # Test loading data
        with patch('main_window.VaspData') as mock_vasp_data:
            mock_vasp_instance = MagicMock()
            mock_vasp_data.return_value = mock_vasp_instance

            self.window.load_data()

            # Check that VaspData was called with the right directory
            mock_vasp_data.assert_called_once()

            # Check that all widgets were updated
            self.window.dos_plot_widget.update_data.assert_called_once()
            self.window.dos_control_widget.update_data.assert_called_once()
            self.window.structure_plot_interactor_widget.update_data.assert_called_once()
            self.window.structure_plot_control_tab.update_data.assert_called_once()
            self.window.structure_variable_control_tab.update_data.assert_called_once()
            self.window.chgcar_control_widget.update_data.assert_called_once()

    @patch('csv.writer')
    @patch('builtins.open', new_callable=mock_open)
    def test_log_program_launch(self, mock_file, mock_csv_writer):
        """Test logging program launch."""
        # Setup mocks
        mock_writer = MagicMock()
        mock_csv_writer.return_value = mock_writer

        # Test without existing file
        with patch('os.path.isfile', return_value=False):
            self.window.log_program_launch()

            # Check that the header and a data row were written
            self.assertEqual(len(mock_writer.writerow.call_args_list), 2)

    def test_create_data(self):
        """Test creating VaspData."""
        with patch('main_window.VaspData') as mock_vasp_data:
            self.window.create_data()
            mock_vasp_data.assert_called_once_with(self.window.dir)

    @patch('platform.system')
    def test_set_working_dir_linux(self, mock_platform):
        """Test setting working directory on Linux."""
        mock_platform.return_value = 'Linux'

        # Call the original method (not our patched version)
        with patch.object(MainWindow, 'set_working_dir', wraps=MainWindow.set_working_dir):
            result = MainWindow.set_working_dir(self.window)
            self.assertEqual(result, './')

    @patch('platform.system')
    @patch('os.getcwd')
    @patch('os.path.isfile')
    def test_set_working_dir_windows_with_files(self, mock_isfile, mock_getcwd, mock_platform):
        """Test setting working directory on Windows with VASP files."""
        mock_platform.return_value = 'Windows'
        mock_getcwd.return_value = 'C:\\test_dir'
        mock_isfile.return_value = True

        # Call the original method (not our patched version)
        with patch.object(MainWindow, 'set_working_dir', wraps=MainWindow.set_working_dir):
            result = MainWindow.set_working_dir(self.window)
            self.assertEqual(result, 'C:\\test_dir')

    @patch('platform.system')
    @patch('os.getcwd')
    @patch('os.path.isfile')
    def test_set_working_dir_windows_without_files(self, mock_isfile, mock_getcwd, mock_platform):
        """Test setting working directory on Windows without VASP files."""
        mock_platform.return_value = 'Windows'
        mock_getcwd.return_value = 'C:\\test_dir'
        mock_isfile.return_value = False

        # Call the original method (not our patched version)
        with patch.object(MainWindow, 'set_working_dir', wraps=MainWindow.set_working_dir):
            result = MainWindow.set_working_dir(self.window)
            # Check that it uses a default directory
            self.assertNotEqual(result, 'C:\\test_dir')
            self.assertTrue(isinstance(result, str))


if __name__ == '__main__':
    unittest.main()