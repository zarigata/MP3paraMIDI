"""
Settings dialog for MP3paraMIDI.

This module provides a comprehensive settings dialog for user configuration
of conversion parameters, quantization, tempo detection, and AI features.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget
)

from ..midi.quantizer import QuantizationGrid


@dataclass
class SettingsData:
    """Data structure for application settings."""
    quantization_enabled: bool = False
    quantization_grid: QuantizationGrid = QuantizationGrid.SIXTEENTH
    detect_tempo: bool = True
    default_tempo: float = 120.0
    use_ai_models: bool = False
    enable_separation: bool = False
    sensitivity_preset: str = 'balanced'  # 'balanced', 'sensitive', 'conservative'
    min_note_duration: float = 0.05
    min_confidence: float = 0.3
    remove_outliers: bool = True
    fmin: str = 'C2'  # Minimum frequency
    fmax: str = 'C6'  # Maximum frequency


class SettingsDialog(QDialog):
    """
    Comprehensive settings dialog for user configuration.
    
    Provides tabbed interface with General, AI Models, and Advanced settings.
    Settings are persisted using QSettings.
    """
    
    def __init__(self, parent=None, current_settings: Optional[SettingsData] = None):
        """
        Initialize settings dialog.
        
        Args:
            parent: Parent widget
            current_settings: Current settings to load, if any
        """
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.resize(500, 400)
        
        # Initialize settings
        self.settings_data = current_settings or self._load_from_qsettings()
        
        # Setup UI
        self._setup_ui()
        self._load_settings()
        
        # Connect signals
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self._create_general_tab()
        self._create_ai_models_tab()
        self._create_advanced_tab()
        
        layout.addWidget(self.tab_widget)
        
        # Create button box
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("Reset to Defaults")
        self.apply_button = QPushButton("Apply")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button = QPushButton("OK")
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
    
    def _create_general_tab(self) -> None:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Quantization group
        quant_group = QGroupBox("Note Quantization")
        quant_layout = QVBoxLayout()
        
        self.quantization_enabled = QCheckBox("Enable note quantization")
        quant_layout.addWidget(self.quantization_enabled)
        
        grid_layout = QHBoxLayout()
        grid_layout.addWidget(QLabel("Quantization grid:"))
        self.quantization_grid = QComboBox()
        self.quantization_grid.addItems(["Quarter (1/4)", "Eighth (1/8)", 
                                        "Sixteenth (1/16)", "Thirty-second (1/32)"])
        grid_layout.addWidget(self.quantization_grid)
        quant_layout.addLayout(grid_layout)
        
        quant_group.setLayout(quant_layout)
        layout.addWidget(quant_group)
        
        # Tempo detection group
        tempo_group = QGroupBox("Tempo Detection")
        tempo_layout = QVBoxLayout()
        
        self.detect_tempo = QCheckBox("Auto-detect tempo")
        tempo_layout.addWidget(self.detect_tempo)
        
        tempo_spin_layout = QHBoxLayout()
        tempo_spin_layout.addWidget(QLabel("Default tempo (BPM):"))
        self.default_tempo = QDoubleSpinBox()
        self.default_tempo.setRange(40.0, 240.0)
        self.default_tempo.setSingleStep(1.0)
        tempo_spin_layout.addWidget(self.default_tempo)
        tempo_layout.addLayout(tempo_spin_layout)
        
        tempo_group.setLayout(tempo_layout)
        layout.addWidget(tempo_group)
        
        # Note duration group
        duration_group = QGroupBox("Note Duration")
        duration_layout = QVBoxLayout()
        
        duration_spin_layout = QHBoxLayout()
        duration_spin_layout.addWidget(QLabel("Minimum note duration (seconds):"))
        self.min_note_duration = QDoubleSpinBox()
        self.min_note_duration.setRange(0.01, 1.0)
        self.min_note_duration.setSingleStep(0.01)
        self.min_note_duration.setDecimals(2)
        duration_spin_layout.addWidget(self.min_note_duration)
        duration_layout.addLayout(duration_spin_layout)
        
        duration_group.setLayout(duration_layout)
        layout.addWidget(duration_group)
        
        layout.addStretch()
        self.tab_widget.addTab(widget, "General")
    
    def _create_ai_models_tab(self) -> None:
        """Create the AI Models settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # AI models group
        ai_group = QGroupBox("AI Models")
        ai_layout = QVBoxLayout()
        
        self.use_ai_models = QCheckBox("Use AI models (polyphonic detection)")
        ai_layout.addWidget(self.use_ai_models)
        
        self.enable_separation = QCheckBox("Enable source separation")
        ai_layout.addWidget(self.enable_separation)
        
        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)
        
        # Sensitivity preset group
        sensitivity_group = QGroupBox("Sensitivity Preset")
        sensitivity_layout = QVBoxLayout()
        
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self.sensitivity_preset = QComboBox()
        self.sensitivity_preset.addItems(["Balanced", "Sensitive", "Conservative"])
        preset_layout.addWidget(self.sensitivity_preset)
        sensitivity_layout.addLayout(preset_layout)
        
        # Description label
        desc_label = QLabel(
            "Balanced: Standard detection accuracy\n"
            "Sensitive: Higher detection, more false positives\n"
            "Conservative: Fewer false positives, may miss notes"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray; font-size: 11px;")
        sensitivity_layout.addWidget(desc_label)
        
        sensitivity_group.setLayout(sensitivity_layout)
        layout.addWidget(sensitivity_group)
        
        layout.addStretch()
        self.tab_widget.addTab(widget, "AI Models")
    
    def _create_advanced_tab(self) -> None:
        """Create the Advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Frequency range group
        freq_group = QGroupBox("Frequency Range")
        freq_layout = QVBoxLayout()
        
        freq_combo_layout = QHBoxLayout()
        freq_combo_layout.addWidget(QLabel("Range:"))
        self.frequency_range = QComboBox()
        self.frequency_range.addItems([
            "Piano: A0-C8", "Vocals: C2-C6", "Guitar: E2-E6", "Custom"
        ])
        freq_combo_layout.addWidget(self.frequency_range)
        freq_layout.addLayout(freq_combo_layout)
        
        freq_group.setLayout(freq_layout)
        layout.addWidget(freq_group)
        
        # Filtering group
        filter_group = QGroupBox("Note Filtering")
        filter_layout = QVBoxLayout()
        
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("Minimum confidence:"))
        self.min_confidence = QDoubleSpinBox()
        self.min_confidence.setRange(0.0, 1.0)
        self.min_confidence.setSingleStep(0.05)
        self.min_confidence.setDecimals(2)
        confidence_layout.addWidget(self.min_confidence)
        filter_layout.addLayout(confidence_layout)
        
        self.remove_outliers = QCheckBox("Remove pitch outliers")
        filter_layout.addWidget(self.remove_outliers)
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        layout.addStretch()
        self.tab_widget.addTab(widget, "Advanced")
    
    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self._apply_settings)
        self.reset_button.clicked.connect(self._reset_to_defaults)
        
        # Enable/disable related widgets
        self.quantization_enabled.toggled.connect(self.quantization_grid.setEnabled)
        self.use_ai_models.toggled.connect(self.enable_separation.setEnabled)
    
    def get_settings(self) -> SettingsData:
        """
        Get current settings from widgets.
        
        Returns:
            SettingsData with current widget values
        """
        # Map quantization grid
        grid_map = {
            "Quarter (1/4)": QuantizationGrid.QUARTER,
            "Eighth (1/8)": QuantizationGrid.EIGHTH,
            "Sixteenth (1/16)": QuantizationGrid.SIXTEENTH,
            "Thirty-second (1/32)": QuantizationGrid.THIRTY_SECOND
        }
        
        # Map sensitivity preset
        preset_map = {
            "Balanced": "balanced",
            "Sensitive": "sensitive", 
            "Conservative": "conservative"
        }
        
        return SettingsData(
            quantization_enabled=self.quantization_enabled.isChecked(),
            quantization_grid=grid_map[self.quantization_grid.currentText()],
            detect_tempo=self.detect_tempo.isChecked(),
            default_tempo=self.default_tempo.value(),
            use_ai_models=self.use_ai_models.isChecked(),
            enable_separation=self.enable_separation.isChecked(),
            sensitivity_preset=preset_map[self.sensitivity_preset.currentText()],
            min_note_duration=self.min_note_duration.value(),
            min_confidence=self.min_confidence.value(),
            remove_outliers=self.remove_outliers.isChecked(),
            fmin='C2',  # Default for now
            fmax='C6'   # Default for now
        )
    
    def set_settings(self, settings: SettingsData) -> None:
        """
        Set widget values from settings data.
        
        Args:
            settings: SettingsData to load into widgets
        """
        self.settings_data = settings
        self._load_settings()
    
    def _load_settings(self) -> None:
        """Load settings into widgets."""
        settings = self.settings_data
        
        # Load general settings
        self.quantization_enabled.setChecked(settings.quantization_enabled)
        self.quantization_grid.setEnabled(settings.quantization_enabled)
        
        grid_map = {
            QuantizationGrid.QUARTER: "Quarter (1/4)",
            QuantizationGrid.EIGHTH: "Eighth (1/8)",
            QuantizationGrid.SIXTEENTH: "Sixteenth (1/16)",
            QuantizationGrid.THIRTY_SECOND: "Thirty-second (1/32)"
        }
        grid_index = self.quantization_grid.findText(grid_map[settings.quantization_grid])
        if grid_index >= 0:
            self.quantization_grid.setCurrentIndex(grid_index)
        
        self.detect_tempo.setChecked(settings.detect_tempo)
        self.default_tempo.setValue(settings.default_tempo)
        self.min_note_duration.setValue(settings.min_note_duration)
        
        # Load AI model settings
        self.use_ai_models.setChecked(settings.use_ai_models)
        self.enable_separation.setChecked(settings.enable_separation)
        self.enable_separation.setEnabled(settings.use_ai_models)
        
        preset_map = {
            "balanced": "Balanced",
            "sensitive": "Sensitive",
            "conservative": "Conservative"
        }
        preset_index = self.sensitivity_preset.findText(preset_map[settings.sensitivity_preset])
        if preset_index >= 0:
            self.sensitivity_preset.setCurrentIndex(preset_index)
        
        # Load advanced settings
        self.min_confidence.setValue(settings.min_confidence)
        self.remove_outliers.setChecked(settings.remove_outliers)
    
    def _apply_settings(self) -> None:
        """Apply settings without closing dialog."""
        self.settings_data = self.get_settings()
        self._save_to_qsettings()
    
    def _reset_to_defaults(self) -> None:
        """Reset all settings to default values."""
        self.settings_data = SettingsData()
        self._load_settings()
    
    def _load_from_qsettings(self) -> SettingsData:
        """
        Load settings from QSettings.
        
        Returns:
            SettingsData loaded from persistent storage
        """
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
    
    def _save_to_qsettings(self) -> None:
        """Save settings to QSettings for persistence."""
        qsettings = QSettings('Zarigata', 'MP3paraMIDI')
        
        settings = self.settings_data
        
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
    
    def accept(self) -> None:
        """Handle dialog acceptance."""
        self.settings_data = self.get_settings()
        self._save_to_qsettings()
        super().accept()
