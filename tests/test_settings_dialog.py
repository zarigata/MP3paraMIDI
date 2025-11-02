"""Tests for the settings dialog module."""
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings
from PyQt6.QtCore import Qt

from mp3paramidi.gui.settings_dialog import SettingsDialog, SettingsData
from mp3paramidi.midi.quantizer import QuantizationGrid


class TestSettingsData:
    """Test the SettingsData dataclass."""
    
    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = SettingsData()
        
        assert settings.quantization_enabled == False
        assert settings.quantization_grid == QuantizationGrid.SIXTEENTH
        assert settings.detect_tempo == True
        assert settings.default_tempo == 120.0
        assert settings.use_ai_models == False
        assert settings.enable_separation == False
        assert settings.sensitivity_preset == 'balanced'
        assert settings.min_note_duration == 0.05
        assert settings.min_confidence == 0.3
        assert settings.remove_outliers == True
        assert settings.fmin == 'C2'
        assert settings.fmax == 'C6'
    
    def test_custom_settings(self) -> None:
        """Test custom settings values."""
        settings = SettingsData(
            quantization_enabled=True,
            quantization_grid=QuantizationGrid.EIGHTH,
            detect_tempo=False,
            default_tempo=140.0,
            use_ai_models=True,
            enable_separation=True,
            sensitivity_preset='sensitive',
            min_note_duration=0.1,
            min_confidence=0.5,
            remove_outliers=False,
            fmin='A1',
            fmax='C7'
        )
        
        assert settings.quantization_enabled == True
        assert settings.quantization_grid == QuantizationGrid.EIGHTH
        assert settings.detect_tempo == False
        assert settings.default_tempo == 140.0
        assert settings.use_ai_models == True
        assert settings.enable_separation == True
        assert settings.sensitivity_preset == 'sensitive'
        assert settings.min_note_duration == 0.1
        assert settings.min_confidence == 0.5
        assert settings.remove_outliers == False
        assert settings.fmin == 'A1'
        assert settings.fmax == 'C7'


@pytest.fixture
def app() -> QApplication:
    """Create QApplication for testing."""
    if not QApplication.instance():
        app = QApplication([])
    else:
        app = QApplication.instance()
    return app


class TestSettingsDialog:
    """Test the SettingsDialog class."""

    @pytest.fixture(autouse=True)
    def clear_settings(self) -> None:
        """Ensure QSettings are cleared before and after each test."""
        qsettings = QSettings('Zarigata', 'MP3paraMIDI')
        qsettings.clear()
        yield
        qsettings.clear()

    @pytest.fixture
    def default_settings(self) -> SettingsData:
        """Create default settings for testing."""
        return SettingsData()

    @pytest.fixture
    def custom_settings(self) -> SettingsData:
        """Create custom settings for testing."""
        return SettingsData(
            quantization_enabled=True,
            quantization_grid=QuantizationGrid.EIGHTH,
            detect_tempo=False,
            default_tempo=140.0,
            use_ai_models=True,
            enable_separation=True,
            sensitivity_preset='sensitive',
            min_note_duration=0.1,
            min_confidence=0.5,
            remove_outliers=False,
            fmin='A1',
            fmax='C7'
        )

    def test_dialog_initialization(self, app: QApplication, default_settings: SettingsData) -> None:
        """Test settings dialog initialization."""
        dialog = SettingsDialog(None, default_settings)

        assert dialog.windowTitle() == "Preferences"
        assert dialog.settings_data == default_settings

        assert dialog.tab_widget.count() == 3
        assert [dialog.tab_widget.tabText(i) for i in range(dialog.tab_widget.count())] == [
            "General",
            "AI Models",
            "Advanced",
        ]

    def test_dialog_with_custom_settings(self, app: QApplication, custom_settings: SettingsData) -> None:
        """Test that UI reflects provided custom settings."""
        dialog = SettingsDialog(None, custom_settings)

        grid_text_map = {
            QuantizationGrid.QUARTER: "Quarter (1/4)",
            QuantizationGrid.EIGHTH: "Eighth (1/8)",
            QuantizationGrid.SIXTEENTH: "Sixteenth (1/16)",
            QuantizationGrid.THIRTY_SECOND: "Thirty-second (1/32)",
        }

        assert dialog.quantization_enabled.isChecked() is True
        assert dialog.quantization_grid.currentText() == grid_text_map[custom_settings.quantization_grid]
        assert dialog.detect_tempo.isChecked() is False
        assert dialog.default_tempo.value() == custom_settings.default_tempo
        assert dialog.use_ai_models.isChecked() is True
        assert dialog.enable_separation.isChecked() is True
        assert dialog.enable_separation.isEnabled() is True
        assert dialog.sensitivity_preset.currentText() == "Sensitive"
        assert dialog.min_note_duration.value() == custom_settings.min_note_duration
        assert dialog.min_confidence.value() == custom_settings.min_confidence
        assert dialog.remove_outliers.isChecked() is False

    def test_quantization_controls(self, app: QApplication, default_settings: SettingsData) -> None:
        """Quantization toggle should enable and disable the grid combo box."""
        dialog = SettingsDialog(None, default_settings)

        assert not dialog.quantization_enabled.isChecked()
        assert not dialog.quantization_grid.isEnabled()

        dialog.quantization_enabled.setChecked(True)
        assert dialog.quantization_grid.isEnabled()

        dialog.quantization_enabled.setChecked(False)
        assert not dialog.quantization_grid.isEnabled()

    def test_ai_controls(self, app: QApplication, default_settings: SettingsData) -> None:
        """AI toggle should manage dependent controls."""
        dialog = SettingsDialog(None, default_settings)

        assert not dialog.use_ai_models.isChecked()
        assert not dialog.enable_separation.isEnabled()

        dialog.use_ai_models.setChecked(True)
        assert dialog.enable_separation.isEnabled()

        dialog.use_ai_models.setChecked(False)
        assert not dialog.enable_separation.isEnabled()

    def test_get_settings_roundtrip(self, app: QApplication, custom_settings: SettingsData) -> None:
        """get_settings should reflect UI state."""
        dialog = SettingsDialog(None, custom_settings)
        retrieved = dialog.get_settings()

        assert retrieved == custom_settings

    def test_set_settings_updates_ui(self, app: QApplication, default_settings: SettingsData, custom_settings: SettingsData) -> None:
        """set_settings should update widgets."""
        dialog = SettingsDialog(None, default_settings)
        dialog.set_settings(custom_settings)

        assert dialog.quantization_enabled.isChecked()
        assert dialog.use_ai_models.isChecked()
        assert dialog.enable_separation.isChecked()
        assert dialog.min_confidence.value() == custom_settings.min_confidence

    def test_reset_to_defaults(self, app: QApplication, custom_settings: SettingsData) -> None:
        """Reset should restore default settings."""
        dialog = SettingsDialog(None, custom_settings)
        dialog._reset_to_defaults()

        assert dialog.settings_data == SettingsData()

    def test_buttons_exist(self, app: QApplication, default_settings: SettingsData) -> None:
        """Ensure dialog buttons are exposed."""
        dialog = SettingsDialog(None, default_settings)

        assert dialog.ok_button.text() == "OK"
        assert dialog.cancel_button.text() == "Cancel"
        assert dialog.reset_button.text() == "Reset to Defaults"
        assert dialog.apply_button.text() == "Apply"

    def test_apply_button_updates_settings(self, app: QApplication, default_settings: SettingsData) -> None:
        """Apply button should persist current widget state."""
        dialog = SettingsDialog(None, default_settings)
        dialog.quantization_enabled.setChecked(True)
        dialog.apply_button.click()

        assert dialog.settings_data.quantization_enabled is True

        stored = QSettings('Zarigata', 'MP3paraMIDI').value('quantization_enabled', type=bool)
        assert stored is True
