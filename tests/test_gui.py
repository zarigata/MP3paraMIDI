"""Tests for the MP3paraMIDI GUI components."""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from PyQt6.QtCore import Qt, QMimeData, QUrl
from PyQt6.QtWidgets import QApplication, QMessageBox, QMenu, QFileDialog

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from mp3paramidi.gui.main_window import MainWindow
from mp3paramidi.gui.widgets import FileDropWidget


# Fixture to create a QApplication instance
@pytest.fixture(scope="module")
def qapp():
    """Create a QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    app.quit()


# Fixture to create a MainWindow instance
@pytest.fixture
def main_window(qtbot):
    """Create and return a MainWindow instance for testing."""
    window = MainWindow()
    qtbot.addWidget(window)
    return window


# Fixture to create a FileDropWidget instance
@pytest.fixture
def file_drop_widget(qtbot):
    """Create and return a FileDropWidget instance for testing."""
    widget = FileDropWidget()
    qtbot.addWidget(widget)
    return widget


class TestMainWindow:
    """Test cases for the MainWindow class."""
    
    def test_window_initialization(self, main_window):
        """Test that the window initializes with the correct title and size."""
        assert main_window.windowTitle() == "MP3paraMIDI by Zarigata"
        assert main_window.minimumWidth() == 800
        assert main_window.minimumHeight() == 600
    
    def test_menu_structure(self, main_window):
        """Test that the menu bar has the correct structure."""
        menubar = main_window.menuBar()
        
        # Check File menu
        file_menu = menubar.findChild(QMenu, "file_menu")
        assert file_menu is not None
        
        file_actions = [action.text() for action in file_menu.actions() 
                       if not action.isSeparator()]
        assert "&Open Audio Files..." in file_actions
        assert "E&xit" in file_actions
        
        # Check Help menu
        help_menu = menubar.findChild(QMenu, "help_menu")
        assert help_menu is not None
        
        help_actions = [action.text() for action in help_menu.actions()]
        assert "&About MP3paraMIDI" in help_actions
        assert "About &Qt" in help_actions
    
    def test_status_bar_initialization(self, main_window):
        """Test that the status bar is initialized correctly."""
        status_bar = main_window.statusBar()
        assert status_bar is not None
        
        # Check that the status label exists
        status_label = main_window.status_label
        assert status_label is not None
        assert status_label.text() == "Ready"
        
        # Check that the progress bar exists and is hidden initially
        progress_bar = main_window.progress_bar
        assert progress_bar is not None
        assert not progress_bar.isVisible()
    
    def test_open_files_dialog(self, main_window, qtbot, monkeypatch):
        """Test that the file dialog is shown with correct filters."""
        # Setup test data
        test_urls = [
            QUrl.fromLocalFile("/path/to/test1.mp3"),
            QUrl.fromLocalFile("/path/to/test2.wav")
        ]
        
        # Create a mock for QFileDialog
        mock_dialog = MagicMock(spec=QFileDialog)
        mock_dialog.exec.return_value = QFileDialog.DialogCode.Accepted
        type(mock_dialog).selectedUrls = PropertyMock(return_value=test_urls)
        
        # Patch QFileDialog to return our mock
        monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog', MagicMock(return_value=mock_dialog))
        
        # Mock add_files to verify it's called with correct paths
        mock_add_files = MagicMock()
        main_window.drop_widget.add_files = mock_add_files
        
        # Trigger the file dialog
        main_window._open_files()
        
        # Verify the file dialog was configured correctly
        assert mock_dialog.fileMode() == QFileDialog.FileMode.ExistingFiles
        assert set(mock_dialog.mimeTypeFilters()) == {
            "audio/mpeg", 
            "audio/wav",
            "audio/x-wav"
        }
        
        # Verify files were added to the drop widget with correct paths
        expected_paths = [url.toLocalFile() for url in test_urls]
        mock_add_files.assert_called_once_with(expected_paths)
    
    @patch('PyQt6.QtWidgets.QMessageBox.information')
    def test_about_dialog(self, mock_message_box, main_window, qtbot):
        """Test that the about dialog shows the correct information."""
        # Mock the message box to avoid showing it during tests
        mock_message_box.return_value = QMessageBox.StandardButton.Ok
        
        # Trigger the about dialog
        main_window._show_about()
        
        # Check that the message box was shown with the correct title
        mock_message_box.assert_called_once()
        args, kwargs = mock_message_box.call_args
        assert "About MP3paraMIDI" in args[0]
        assert "Zarigata" in args[1]  # Check that the creator is mentioned


class TestFileDropWidget:
    """Test cases for the FileDropWidget class."""
    
    def test_initial_state(self, file_drop_widget):
        """Test that the widget initializes with the correct state."""
        assert file_drop_widget.file_list.count() == 0
        assert not file_drop_widget.convert_button.isEnabled()
        assert file_drop_widget.drop_label.text() == "🎵 Drag & Drop Audio Files Here\n(MP3, WAV supported)"
    
    def test_add_valid_files(self, file_drop_widget, qtbot):
        """Test adding valid audio files to the widget."""
        test_files = ["/path/to/test1.mp3", "/path/to/test2.wav"]
        
        with qtbot.waitSignal(file_drop_widget.filesChanged) as blocker:
            file_drop_widget.add_files(test_files)
        
        assert file_drop_widget.file_list.count() == 2
        assert file_drop_widget.convert_button.isEnabled()
        
        # Check that the files were added in order
        for i, file_path in enumerate(test_files):
            assert file_drop_widget.file_list.item(i).text() == file_path
    
    def test_add_invalid_files(self, file_drop_widget, qtbot):
        """Test that invalid files are not added to the widget."""
        test_files = ["/path/to/test1.txt", "/path/to/test2.pdf"]
        
        with qtbot.assertNotEmitted(file_drop_widget.filesChanged):
            file_drop_widget.add_files(test_files)
        
        assert file_drop_widget.file_list.count() == 0
        assert not file_drop_widget.convert_button.isEnabled()
    
    def test_clear_files(self, file_drop_widget, qtbot):
        """Test clearing files from the widget."""
        # First add some files
        test_files = ["/path/to/test1.mp3", "/path/to/test2.wav"]
        file_drop_widget.add_files(test_files)
        
        # Now clear them
        with qtbot.waitSignal(file_drop_widget.filesChanged) as blocker:
            file_drop_widget.clear_files()
        
        assert file_drop_widget.file_list.count() == 0
        assert not file_drop_widget.convert_button.isEnabled()
    
    def test_convert_button_click(self, file_drop_widget, qtbot):
        """Test that the convert button emits the correct signal."""
        # Add some test files
        test_files = ["/path/to/test1.mp3", "/path/to/test2.wav"]
        file_drop_widget.add_files(test_files)
        
        # Connect to the signal and click the button
        with qtbot.waitSignal(file_drop_widget.convertRequested) as blocker:
            qtbot.mouseClick(file_drop_widget.convert_button, Qt.MouseButton.LeftButton)
        
        # Check that the signal was emitted with the correct files
        assert blocker.args[0] == test_files
    
    def test_drag_enter_event_accepts_audio(self, file_drop_widget, qtbot):
        """Test that drag enter event accepts audio files."""
        # Create a mock event with audio file URLs
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile("/path/to/test.mp3")])
        
        # Create a mock event
        event = MagicMock()
        event.mimeData.return_value = mime_data
        
        # Call the event handler
        file_drop_widget.dragEnterEvent(event)
        
        # Check that the event was accepted
        event.acceptProposedAction.assert_called_once()
    
    def test_drag_enter_event_rejects_non_audio(self, file_drop_widget, qtbot):
        """Test that drag enter event rejects non-audio files."""
        # Create a mock event with non-audio file URLs
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile("/path/to/test.txt")])
        
        # Create a mock event
        event = MagicMock()
        event.mimeData.return_value = mime_data
        
        # Call the event handler
        file_drop_widget.dragEnterEvent(event)
        
        # Check that the event was ignored
        event.ignore.assert_called_once()
    
    def test_drop_event_adds_files(self, file_drop_widget, qtbot):
        """Test that drop event adds audio files to the list."""
        # Create a mock event with audio file URLs
        mime_data = QMimeData()
        mime_data.setUrls([
            QUrl.fromLocalFile("/path/to/test1.mp3"),
            QUrl.fromLocalFile("/path/to/test2.wav")
        ])
        
        # Create a mock event
        event = MagicMock()
        event.mimeData.return_value = mime_data
        
        # Connect to the signal
        with qtbot.waitSignal(file_drop_widget.filesChanged) as blocker:
            # Call the event handler
            file_drop_widget.dropEvent(event)
        
        # Check that the event was accepted
        event.acceptProposedAction.assert_called_once()
        
        # Check that the files were added
        assert file_drop_widget.file_list.count() == 2
