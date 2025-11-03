"""Main application window for MP3paraMIDI."""
from __future__ import annotations

import logging
import os
import traceback

logger = logging.getLogger(__name__)
from pathlib import Path
from typing import List, Optional, Dict, Any

from mp3paramidi.audio import (
    AudioLoader, AudioData, AudioMetadata,
    AudioLoadError, UnsupportedFormatError, FFmpegNotFoundError, CorruptedFileError
)

from PyQt6.QtCore import Qt, QUrl, QCoreApplication, QThread
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QStatusBar, 
    QProgressBar, QLabel, QVBoxLayout, QWidget, QApplication
)

from .workers import ConversionWorker, ConversionConfig
from .settings_dialog import SettingsDialog, SettingsData
from .playback_widget import PlaybackWidget
from .widgets import FileDropWidget
from ..midi.quantizer import QuantizationGrid

from PyQt6.QtCore import QSettings


class MainWindow(QMainWindow):
    """Main application window for MP3paraMIDI."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the main window."""
        super().__init__(parent)
        
        # Set application metadata
        QCoreApplication.setApplicationName("MP3paraMIDI")
        QCoreApplication.setApplicationVersion("0.1.0")
        QCoreApplication.setOrganizationName("Zarigata")
        
        self.setWindowTitle("MP3paraMIDI by Zarigata")
        self.setMinimumSize(800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create and set up the file drop widget
        self.drop_widget = FileDropWidget()
        layout.addWidget(self.drop_widget)
        
        # Create and set up the playback widget (initially hidden)
        self.playback_widget = PlaybackWidget()
        self.playback_widget.hide()  # Hide until MIDI is generated
        layout.addWidget(self.playback_widget)
        
        # Initialize audio loader and worker thread
        self.audio_loader = AudioLoader(preserve_stereo=True, target_sample_rate=None)
        self.loaded_audio_data: List[AudioData] = []
        self.conversion_worker: Optional[ConversionWorker] = None
        self.worker_thread: Optional[QThread] = None
        
        # Settings and playback
        self.settings_data: Optional[SettingsData] = None
        
        # Connect signals
        self.drop_widget.browseRequested.connect(self._open_files)
        self.drop_widget.convertRequested.connect(self._on_convert_requested)
        
        # Initialize AI dependencies check
        self.ai_deps_available = self._check_ai_dependencies()
        
        # Set up menu bar
        self._setup_menu_bar()
        
        # Set up status bar
        self._setup_status_bar()
    
    def _setup_menu_bar(self) -> None:
        """Set up the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.setObjectName("file_menu")
        
        open_action = file_menu.addAction("&Open Audio Files...")
        open_action.triggered.connect(self._open_files)
        open_action.setShortcut("Ctrl+O")
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(QApplication.instance().quit)
        exit_action.setMenuRole(exit_action.MenuRole.QuitRole)
        exit_action.setShortcut("Ctrl+Q")
        
        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        settings_menu.setObjectName("settings_menu")
        
        preferences_action = settings_menu.addAction("&Preferences...")
        preferences_action.triggered.connect(self._show_settings_dialog)
        preferences_action.setShortcut("Ctrl+,")
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.setObjectName("help_menu")
        
        about_action = help_menu.addAction("&About MP3paraMIDI")
        about_action.triggered.connect(self._show_about)
        about_action.setMenuRole(about_action.MenuRole.AboutRole)
        
        about_qt_action = help_menu.addAction("About &Qt")
        about_qt_action.triggered.connect(QApplication.aboutQt)
    
    def _setup_status_bar(self) -> None:
        """Set up the status bar with a progress indicator."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        status_bar.addWidget(self.status_label, 1)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.hide()
        status_bar.addPermanentWidget(self.progress_bar)
    
    def _open_files(self) -> None:
        """Open a file dialog to select audio files."""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        
        # Set MIME type filters for better cross-platform support
        file_dialog.setMimeTypeFilters([
            "audio/mpeg",  # MP3
            "audio/wav",   # WAV
            "audio/x-wav"  # Alternative WAV MIME type
        ])
        
        # Set name filters for better UX on all platforms
        file_dialog.setNameFilters([
            "Audio Files (*.mp3 *.wav)",
            "MP3 Files (*.mp3)",
            "WAV Files (*.wav)",
            "All Files (*)"
        ])
        file_dialog.selectNameFilter("Audio Files (*.mp3 *.wav)")
        file_dialog.selectMimeTypeFilter("audio/mpeg")
        
        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            file_paths = []
            for url in file_dialog.selectedUrls():
                if url.isLocalFile():
                    file_paths.append(url.toLocalFile())
            
            if file_paths:
                self.drop_widget.add_files(file_paths)
    
    def _on_convert_requested(self, file_paths: List[str]) -> None:
        """Handle convert button click by starting the conversion in a background thread.
        
        Args:
            file_paths: List of file paths to process
        """
        if not file_paths:
            return
            
        # Reset state
        self.loaded_audio_data = []
        self.show_progress()
        self.set_progress_range(0, len(file_paths))
        self.drop_widget.set_convert_enabled(False)
        
        # Load all files first
        success_count = 0
        error_count = 0
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                self.set_status_message(f"Loading {os.path.basename(file_path)}...")
                
                # Load the audio file
                audio_data = self._load_audio_file(file_path)
                self.loaded_audio_data.append(audio_data)
                success_count += 1
                
                # Update progress
                self.set_progress_value(i)
                
            except Exception as e:
                error_count += 1
                self._handle_audio_load_error(file_path, e)
                continue
        
        if success_count == 0:
            self.hide_progress()
            self.drop_widget.set_convert_enabled(True)
            self.set_status_message("Failed to load any files", 5000)
            return
            
        # Start conversion in background thread
        self._start_conversion()
    
    def _check_ai_dependencies(self) -> bool:
        """Check if AI model dependencies are available.
        
        Returns:
            bool: True if all required AI dependencies are available, False otherwise
        """
        try:
            # Try importing basic pitch wrapper to check dependencies
            from mp3paramidi.models import BasicPitchWrapper
            # Try importing demucs wrapper to check dependencies
            from mp3paramidi.models import DemucsWrapper
            return True
        except (ImportError, ModuleNotFoundError) as e:
            logger.debug(f"AI dependencies not available: {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"Error checking AI dependencies: {str(e)}", exc_info=True)
            return False

    def _start_conversion(self) -> None:
        """Start the audio to MIDI conversion in a background thread."""
        # Load settings if not already loaded
        if self.settings_data is None:
            self.settings_data = self._load_settings()
        
        # Create worker and thread
        self.worker_thread = QThread()
        
        # Create conversion config from settings
        config = {
            'fmin': self.settings_data.fmin,
            'fmax': self.settings_data.fmax,
            'tempo': self.settings_data.default_tempo,
            'min_note_duration': self.settings_data.min_note_duration,
            'output_dir': None,  # Use default output directory
            'use_ai_models': self.settings_data.use_ai_models,
            'enable_separation': self.settings_data.enable_separation,
            'demucs_model': "htdemucs",
            'basic_pitch_config': self._get_basic_pitch_config(self.settings_data.sensitivity_preset),
            'device': None,
            'models_cache_dir': Path.cwd() / "models",
            # New settings
            'detect_tempo': self.settings_data.detect_tempo,
            'quantization_enabled': self.settings_data.quantization_enabled,
            'quantization_grid': self.settings_data.quantization_grid.name,
            'filter_config': {
                'min_confidence': self.settings_data.min_confidence,
                'min_duration': self.settings_data.min_note_duration,
                'remove_outliers': self.settings_data.remove_outliers,
            },
            'sensitivity_preset': self.settings_data.sensitivity_preset,
        }
        
        self.conversion_worker = ConversionWorker(
            audio_data_list=self.loaded_audio_data,
            config=config
        )
        
        # Move worker to thread
        self.conversion_worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker_thread.started.connect(self.conversion_worker.run)
        self.conversion_worker.progress.connect(self._on_conversion_progress)
        self.conversion_worker.file_completed.connect(self._on_file_completed)
        self.conversion_worker.all_completed.connect(self._on_all_completed)
        self.conversion_worker.error.connect(self._on_conversion_error)
        self.conversion_worker.finished.connect(self.worker_thread.quit)
        self.conversion_worker.model_download_progress.connect(self._on_model_download_progress)
        self.worker_thread.finished.connect(self._on_conversion_finished)
        
        # Start the thread
        self.worker_thread.start()
        
        # Update UI
        self.set_status_message("Starting conversion...")
        self.set_progress_range(0, len(self.loaded_audio_data))
        self.set_progress_value(0)
        self.drop_widget.set_convert_enabled(False)
    
    def _on_conversion_progress(self, percentage: int, message: str) -> None:
        """Handle progress updates from the conversion worker."""
        self.set_status_message(message)
        self.set_progress_value(percentage)
    
    def _on_file_completed(self, file_path: str, result: Any) -> None:
        """Handle completion of a single file conversion."""
        # Update progress bar
        current = self.progress_bar.value() + 1
        self.set_progress_value(current)
        
        # Show completion message
        if result and hasattr(result, 'success') and result.success:
            self.set_status_message(f"Converted {Path(file_path).name}", 2000)
            
            # Show playback widget and load MIDI if available
            if result.output_path and result.output_path.exists():
                if self.playback_widget.isHidden():
                    self.playback_widget.show()
                
                try:
                    self.playback_widget.load_midi(result.output_path)
                    self.set_status_message(f"Conversion complete - Ready to preview", 3000)
                except Exception as e:
                    logger.warning(f"Failed to load MIDI for playback: {str(e)}")
    
    def _on_all_completed(self, success_count: int, error_count: int) -> None:
        """Handle completion of all file conversions."""
        if success_count > 0 and error_count == 0:
            self.set_status_message(f"Successfully converted {success_count} file(s)", 5000)
        elif success_count > 0:
            self.set_status_message(
                f"Converted {success_count} file(s), {error_count} failed", 5000
            )
        else:
            self.set_status_message("Failed to convert any files", 5000)
    
    def _on_conversion_error(self, file_path: str, error_message: str) -> None:
        """Handle errors during conversion."""
        # Check for AI-related errors to show more detailed guidance
        if any(keyword in error_message.lower() for keyword in ["model", "ai", "download"]):
            self._show_ai_error_guidance(error_message)
        else:
            QMessageBox.critical(
                self,
                "Conversion Error",
                f"Error converting {Path(file_path).name}: {error_message}",
                QMessageBox.StandardButton.Ok
            )
    
    def _on_model_download_progress(self, model_name: str, progress: int) -> None:
        """Handle model download progress updates.
        
        Args:
            model_name: Name of the model being downloaded
            progress: Download progress percentage (0-100)
        """
        if progress < 0:
            # Indeterminate progress
            self.set_status_message(f"Preparing {model_name} model...")
        else:
            self.set_status_message(f"Downloading {model_name} model: {progress}%")
    
    def _show_ai_error_guidance(self, error_message: str) -> None:
        """Show a dialog with guidance for AI model errors.
        
        Args:
            error_message: The error message that was received
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("AI Model Error")
        
        # Create a more detailed message
        message = (
            "<p>An error occurred while using AI models:</p>"
            f"<p><b>{error_message}</b></p>"
            "<p>This may be because:</p>"
            "<ul>"
            "<li>This is your first time using AI features and the models need to be downloaded</li>"
            "<li>Your internet connection is unstable or blocked</li>"
            "<li>There's not enough disk space to save the models</li>"
            "<li>The model files are corrupted</li>"
            "</ul>"
            "<p>Please check your internet connection and try again. "
            "The models will be downloaded automatically on first use and may take several minutes "
            "depending on your connection speed.</p>"
            "<p>If the problem persists, you can try:</p>"
            "<ol>"
            "<li>Checking your internet connection</li>"
            "<li>Ensuring you have at least 2GB of free disk space</li>"
            "<li>Restarting the application</li>"
            "<li>Manually downloading the models from the documentation</li>"
            "</ol>"
        )
        
        msg_box.setText("AI Model Error")
        msg_box.setInformativeText(message)
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Make links clickable
        msg_box.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction |
            Qt.TextInteractionFlag.LinksAccessibleByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        
        msg_box.exec()
    
    def _on_conversion_finished(self) -> None:
        """Clean up after conversion is complete."""
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.worker_thread.deleteLater()
        self.conversion_worker.deleteLater()
        self.worker_thread = None
        self.conversion_worker = None
        
        # Reset UI
        self.hide_progress()
        self.drop_widget.set_convert_enabled(True)
    
    def _load_audio_file(self, file_path: str) -> AudioData:
        """Load an audio file using the audio loader.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Loaded audio data
            
        Raises:
            AudioLoadError: If the file cannot be loaded
        """
        try:
            return self.audio_loader.load(file_path)
        except FFmpegNotFoundError as e:
            # Show FFmpeg installation dialog
            self._show_ffmpeg_error()
            raise
        except (UnsupportedFormatError, CorruptedFileError) as e:
            # These are already user-friendly messages
            raise AudioLoadError(Path(file_path), str(e)) from e
        except Exception as e:
            # Wrap other exceptions in AudioLoadError
            raise AudioLoadError(Path(file_path), str(e)) from e
    
    def _handle_audio_load_error(self, file_path: str, error: Exception) -> None:
        """Handle errors that occur during audio loading."""
        file_name = os.path.basename(file_path)
        
        if isinstance(error, FFmpegNotFoundError):
            # Already shown in _load_audio_file
            error_msg = f"{file_name}: FFmpeg is required for MP3 files"
        elif isinstance(error, (UnsupportedFormatError, CorruptedFileError, AudioLoadError)):
            error_msg = f"{file_name}: {str(error)}"
        else:
            error_msg = f"{file_name}: An unexpected error occurred"
            logger.error(f"Error loading {file_path}: {str(error)}\n{traceback.format_exc()}")
        
        # Show error message
        QMessageBox.warning(
            self,
            "Error Loading File",
            error_msg,
            QMessageBox.StandardButton.Ok
        )
    
    def _show_ffmpeg_error(self) -> None:
        """Show a dialog explaining that FFmpeg is required for MP3 support."""
        message = """
        <p>FFmpeg is required to load MP3 files but was not found on your system.</p>
        
        <p>Please install FFmpeg using one of these methods:</p>
        
        <ul>
        <li><b>Windows:</b> Download from <a href="https://ffmpeg.org/download.html">ffmpeg.org</a> 
        and add it to your system PATH</li>
        
        <li><b>macOS:</b> <code>brew install ffmpeg</code> (using <a href="https://brew.sh/">Homebrew</a>)</li>
        
        <li><b>Linux (Debian/Ubuntu):</b> <code>sudo apt install ffmpeg</code></li>
        <li><b>Linux (Fedora):</b> <code>sudo dnf install ffmpeg</code></li>
        </ul>
        
        <p>After installing FFmpeg, restart the application.</p>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("FFmpeg Not Found")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText("FFmpeg is Required")
        msg_box.setInformativeText(message)
        
        # Make links clickable
        msg_box.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction |
            Qt.TextInteractionFlag.LinksAccessibleByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        msg_box.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    
    def _show_about(self) -> None:
        """Show the About dialog."""
        about_text = """
        <h2>MP3paraMIDI 0.1.0</h2>
        <p><strong>Created by Zarigata</strong></p>
        <p>An application to convert audio files to MIDI format.</p>
        <p>This tool extracts musical notes from audio files and generates 
        corresponding MIDI files that can be edited in any music software.</p>
        <p><a href="https://github.com/zarigata/mp3paramidi">GitHub Repository</a></p>
        
        <p><strong>Features:</strong><br>
        • Note quantization with configurable grid sizes<br>
        • Automatic tempo detection using librosa beat tracking<br>
        • Enhanced note filtering to remove spurious detections<br>
        • MIDI preview playback with play/pause/stop controls<br>
        • Comprehensive settings for customizing conversion parameters<br>
        • Improved velocity detection based on audio amplitude analysis</p>
        
        <p><strong>Technologies used:</strong><br>
        • PyQt6 for the user interface<br>
        • Librosa for audio analysis<br>
        • Basic-Pitch for pitch detection<br>
        • Demucs for source separation<br>
        • pygame for MIDI playback</p>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("About MP3paraMIDI")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(about_text)
        msg_box.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction |
            Qt.TextInteractionFlag.LinksAccessibleByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        
        # Make links clickable with proper URL handling
        msg_box.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        
        msg_box.setStandardButtons(QMessageBox.StandardButton.Close)
        msg_box.exec()
    
    def _show_settings_dialog(self) -> None:
        """Show the settings dialog."""
        # Load current settings if not already loaded
        if self.settings_data is None:
            self.settings_data = self._load_settings()
        
        # Create and show settings dialog
        dialog = SettingsDialog(self, self.settings_data)
        
        if dialog.exec() == QMessageBox.DialogCode.Accepted:
            # Save new settings
            self.settings_data = dialog.get_settings()
            self._save_settings(self.settings_data)
            self.set_status_message("Settings saved - will apply to next conversion", 3000)
    
    def _load_settings(self) -> SettingsData:
        """Load settings from QSettings."""
        qsettings = QSettings('Zarigata', 'MP3paraMIDI')
        
        return SettingsData(
            quantization_enabled=qsettings.value('quantization_enabled', False, type=bool),
            quantization_grid=QuantizationGrid[qsettings.value('quantization_grid', 'SIXTEENTH', type=str)],
            detect_tempo=qsettings.value('detect_tempo', True, type=bool),
            default_tempo=qsettings.value('default_tempo', 120.0, type=float),
            use_ai_models=qsettings.value('use_ai_models', False, type=bool),
            enable_separation=qsettings.value('enable_separation', False, type=bool),
            sensitivity_preset=qsettings.value('sensitivity_preset', 'balanced', type=str),
            min_note_duration=qsettings.value('min_note_duration', 0.05, type=float),
            min_confidence=qsettings.value('min_confidence', 0.3, type=float),
            remove_outliers=qsettings.value('remove_outliers', True, type=bool),
            fmin=qsettings.value('fmin', 'C2', type=str),
            fmax=qsettings.value('fmax', 'C6', type=str)
        )
    
    def _save_settings(self, settings: SettingsData) -> None:
        """Save settings to QSettings."""
        qsettings = QSettings('Zarigata', 'MP3paraMIDI')
        
        qsettings.setValue('quantization_enabled', settings.quantization_enabled)
        qsettings.setValue('quantization_grid', settings.quantization_grid.name)
        qsettings.setValue('detect_tempo', settings.detect_tempo)
        qsettings.setValue('default_tempo', settings.default_tempo)
        qsettings.setValue('use_ai_models', settings.use_ai_models)
        qsettings.setValue('enable_separation', settings.enable_separation)
        qsettings.setValue('sensitivity_preset', settings.sensitivity_preset)
        qsettings.setValue('min_note_duration', settings.min_note_duration)
        qsettings.setValue('min_confidence', settings.min_confidence)
        qsettings.setValue('remove_outliers', settings.remove_outliers)
        qsettings.setValue('fmin', settings.fmin)
        qsettings.setValue('fmax', settings.fmax)
        
        qsettings.sync()
    
    def _get_basic_pitch_config(self, preset: str) -> Dict[str, float]:
        """Get Basic-Pitch configuration based on sensitivity preset."""
        from mp3paramidi.models import BasicPitchWrapper
        
        # Get default config and adjust based on preset
        default_config = BasicPitchWrapper.get_default_config()
        
        if preset == 'sensitive':
            return {
                **default_config,
                'onset_threshold': 0.3,  # Lower threshold = more sensitive
                'frame_threshold': 0.2,
                'minimum_note_length': 0.04,
            }
        elif preset == 'conservative':
            return {
                **default_config,
                'onset_threshold': 0.7,  # Higher threshold = more conservative
                'frame_threshold': 0.5,
                'minimum_note_length': 0.08,
            }
        else:  # balanced
            return default_config
    
    def _on_playback_error(self, error_msg: str) -> None:
        """Handle playback errors gracefully."""
        logger.warning(f"Playback error: {error_msg}")
        self.set_status_message(f"Playback error: {error_msg}", 3000)
    
    def show_progress(self, show: bool = True) -> None:
        """Show or hide the progress bar.
        
        Args:
            show: Whether to show the progress bar
        """
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setValue(0)
            
    def hide_progress(self) -> None:
        """Hide the progress bar."""
        self.progress_bar.hide()
    
    def set_progress_range(self, min_val: int, max_val: int) -> None:
        """Set the range of the progress bar.
        
        Args:
            min_val: Minimum progress value
            max_val: Maximum progress value
        """
        self.progress_bar.setRange(min_val, max_val)
    
    def set_progress_value(self, value: int) -> None:
        """Set the current value of the progress bar.
        
        Args:
            value: Current progress value
        """
        self.progress_bar.setValue(value)
        QApplication.processEvents()  # Ensure UI updates
    
    def set_status_message(self, message: str, timeout: int = 0) -> None:
        """Set a status message in the status bar.
        
        Args:
            message: The message to display
            timeout: Time in milliseconds before the message is cleared (0 = show until cleared)
        """
        self.status_label.setText(message)
        if timeout > 0:
            self.statusBar().showMessage(message, timeout)
        else:
            self.statusBar().showMessage(message)
        QApplication.processEvents()  # Ensure UI updates
