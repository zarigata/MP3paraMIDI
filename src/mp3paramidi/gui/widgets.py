"""Custom widgets for the MP3paraMIDI application."""
from __future__ import annotations

from typing import Optional, List

from PyQt6.QtCore import Qt, QMimeData, QUrl, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont, QPalette, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton, 
    QHBoxLayout, QListWidgetItem, QMessageBox
)


class FileDropWidget(QWidget):
    """Widget that accepts drag and drop of audio files."""
    
    # Signals
    filesChanged = pyqtSignal(list)  # Emitted when files are added or removed
    browseRequested = pyqtSignal()   # Emitted when browse button is clicked
    convertRequested = pyqtSignal(list)  # Emitted when convert button is clicked
    
    # Supported audio file extensions
    AUDIO_EXTENSIONS = {'.mp3', '.wav'}
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the file drop widget."""
        super().__init__(parent)
        self.setAcceptDrops(True)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Drop area label
        self.drop_label = QLabel("🎵 Drag & Drop Audio Files Here\n(MP3, WAV supported)")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                padding: 40px;
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f8f9fa;
                color: #6c757d;
            }
            QLabel:hover {
                background-color: #e9ecef;
                border-color: #6c757d;
            }
        """)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #e9ecef;
            }
            QListWidget::item:selected {
                background-color: #e9ecef;
                color: #212529;
            }
        """)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Browse button
        self.browse_button = QPushButton("Browse Files...")
        self.browse_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        
        # Convert button
        self.convert_button = QPushButton("Convert to MIDI")
        self.convert_button.setEnabled(False)
        self.convert_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #e9ecef;
            }
            QPushButton:hover:enabled {
                background-color: #0b5ed7;
            }
            QPushButton:pressed:enabled {
                background-color: #0a58ca;
            }
        """)
        
        # Add widgets to layouts
        button_layout.addWidget(self.browse_button)
        button_layout.addStretch()
        button_layout.addWidget(self.convert_button)
        
        layout.addWidget(self.drop_label)
        layout.addWidget(self.file_list)
        layout.addLayout(button_layout)
        
        # Connect signals
        self.browse_button.clicked.connect(self.browseRequested)
        self.convert_button.clicked.connect(self._on_convert_clicked)
    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event."""
        mime_data = event.mimeData()
        if mime_data.hasUrls() and self._has_audio_files(mime_data):
            event.acceptProposedAction()
            self._highlight_drop_area(True)
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Handle drag leave event."""
        self._highlight_drop_area(False)
    
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event."""
        self._highlight_drop_area(False)
        
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return
        
        file_paths = []
        for url in mime_data.urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if self._is_valid_audio_file(file_path):
                    file_paths.append(file_path)
        
        if file_paths:
            self.add_files(file_paths)
        
        event.acceptProposedAction()
    
    def _on_convert_clicked(self) -> None:
        """Handle convert button click."""
        files = self.get_files()
        if files:
            self.convertRequested.emit(files)
    
    def add_files(self, file_paths: List[str]) -> None:
        """Add files to the list."""
        if not file_paths:
            return
        
        current_files = set(self.get_files())
        added = False
        
        for file_path in file_paths:
            if not self._is_valid_audio_file(file_path):
                continue
                
            if file_path not in current_files:
                item = QListWidgetItem(file_path)
                self.file_list.addItem(item)
                current_files.add(file_path)
                added = True
        
        if added:
            self._update_ui_state()
    
    def get_files(self) -> List[str]:
        """Get the list of file paths."""
        return [self.file_list.item(i).text() 
                for i in range(self.file_list.count())]
    
    def clear_files(self) -> None:
        """Clear the file list."""
        self.file_list.clear()
        self._update_ui_state()
    
    def _is_valid_audio_file(self, file_path: str) -> bool:
        """Check if the file has a valid audio extension."""
        return any(file_path.lower().endswith(ext) 
                  for ext in self.AUDIO_EXTENSIONS)
    
    def _has_audio_files(self, mime_data: QMimeData) -> bool:
        """Check if any of the dragged files are valid audio files."""
        if not mime_data.hasUrls():
            return False
            
        for url in mime_data.urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if self._is_valid_audio_file(file_path):
                    return True
        return False
    
    def _highlight_drop_area(self, highlight: bool) -> None:
        """Highlight the drop area when files are dragged over."""
        if highlight:
            self.drop_label.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    padding: 40px;
                    border: 2px dashed #0d6efd;
                    border-radius: 10px;
                    background-color: #e7f1ff;
                    color: #0d6efd;
                }
            """)
        else:
            self.drop_label.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    padding: 40px;
                    border: 2px dashed #aaa;
                    border-radius: 10px;
                    background-color: #f8f9fa;
                    color: #6c757d;
                }
                QLabel:hover {
                    background-color: #e9ecef;
                    border-color: #6c757d;
                }
            """)
    def _update_ui_state(self) -> None:
        """Update the UI state based on the current file list."""
        has_files = self.file_list.count() > 0
        self.convert_button.setEnabled(has_files)
        self.drop_label.setVisible(not has_files)
        self.file_list.setVisible(has_files)
        self.filesChanged.emit(self.get_files())

    def set_convert_enabled(self, enabled: bool) -> None:
        """Enable or disable the convert button.
        
        Args:
            enabled: Whether to enable the convert button
        """
        self.convert_button.setEnabled(enabled)
