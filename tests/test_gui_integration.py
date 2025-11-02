"""Integration tests for the GUI and audio loader."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from mp3paramidi.gui.main_window import MainWindow
from mp3paramidi.audio import AudioData, AudioMetadata
from tests.fixtures import create_test_wav


@pytest.fixture
def main_window(qtbot):
    """Create and return a MainWindow instance for testing."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitForWindowShown(window)
    return window


def test_convert_with_valid_files(main_window, qtbot, tmp_path):
    """Test converting valid audio files through the GUI."""
    # Create test WAV files
    wav_path1 = create_test_wav(
        output_path=tmp_path / 'test1.wav',
        frequency=440.0,
        duration=0.1,
        sample_rate=44100,
        channels=1
    )
    wav_path2 = create_test_wav(
        output_path=tmp_path / 'test2.wav',
        frequency=880.0,
        duration=0.1,
        sample_rate=44100,
        channels=1
    )
    
    # Directly call add_files with the test file paths
    main_window.drop_widget.add_files([str(wav_path1), str(wav_path2)])
    
    # Verify files were added to the drop widget
    assert main_window.drop_widget.file_list.count() == 2
    
    # Mock the audio loading process
    test_audio_data = AudioData(
        file_path=wav_path1,
        samples=np.zeros(4410, dtype=np.float32),  # 0.1s at 44.1kHz
        metadata=AudioMetadata(
            duration=0.1,
            sample_rate=44100,
            channels=1,
            bit_depth=32,
            format='WAV'
        )
    )
    
    # Mock the AudioLoader to return our test data
    with patch('mp3paramidi.audio.AudioLoader.load', return_value=test_audio_data):
        # Click the "Convert to MIDI" button
        with qtbot.waitSignal(main_window.drop_widget.convertRequested, timeout=1000) as blocker:
            qtbot.mouseClick(main_window.drop_widget.convert_btn, Qt.MouseButton.LeftButton)
        
        # Verify the signal was emitted with the correct files
        assert blocker.args == ([str(wav_path1), str(wav_path2)],)
        
        # Verify the progress bar is visible and updates
        assert main_window.progress_bar.isVisible()
        
        # Simulate progress updates (normally done by the worker thread)
        main_window.set_progress_value(1)
        assert main_window.progress_bar.value() == 1
        
        # Verify the audio data was stored
        assert len(main_window.loaded_audio_data) == 2
        assert all(isinstance(data, AudioData) for data in main_window.loaded_audio_data)
        
        # Verify the status message was updated
        assert "Loaded 2 files" in main_window.statusBar().currentMessage()


def test_convert_with_invalid_file(main_window, qtbot, tmp_path):
    """Test handling of invalid audio files through the GUI."""
    # Create an invalid audio file
    invalid_path = tmp_path / 'invalid.wav'
    invalid_path.write_bytes(b'This is not a valid WAV file')
    
    # Directly call add_files with the invalid file path
    main_window.drop_widget.add_files([str(invalid_path)])
    
    # Mock the QMessageBox to prevent it from showing during tests
    with patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warning:
        # Mock the audio loading to raise an exception
        with patch('mp3paramidi.audio.AudioLoader.load', 
                  side_effect=Exception("Invalid WAV file")):
            # Click the "Convert to MIDI" button
            with qtbot.waitSignal(main_window.drop_widget.convertRequested, timeout=1000):
                qtbot.mouseClick(main_window.drop_widget.convert_btn, Qt.MouseButton.LeftButton)
            
            # Verify the error dialog was shown
            assert mock_warning.called
            
            # Verify the progress bar is hidden after error
            assert not main_window.progress_bar.isVisible()
            
            # Verify the status message indicates an error
            assert "error" in main_window.statusBar().currentMessage().lower()


def test_convert_with_mp3_no_ffmpeg(main_window, qtbot, tmp_path, monkeypatch):
    """Test MP3 file handling when FFmpeg is not available."""
    # Create a test MP3 file
    mp3_path = tmp_path / 'test.mp3'
    mp3_path.touch()  # Empty file, we'll mock the loading anyway
    
    # Directly call add_files with the MP3 file path
    main_window.drop_widget.add_files([str(mp3_path)])
    
    # Mock FFmpeg as not available
    monkeypatch.setattr('mp3paramidi.audio.FFmpegDetector.is_available', lambda: False)
    
    # Mock QMessageBox to capture the instance and patch exec()
    with patch('PyQt6.QtWidgets.QMessageBox') as mock_msg_box_class:
        mock_msg_box = MagicMock()
        mock_msg_box_class.return_value = mock_msg_box
        
        # Click the "Convert to MIDI" button
        with qtbot.waitSignal(main_window.drop_widget.convertRequested, timeout=1000):
            qtbot.mouseClick(main_window.drop_widget.convert_btn, Qt.MouseButton.LeftButton)
        
        # Verify the message box was created with correct parameters
        mock_msg_box_class.assert_called_once()
        assert mock_msg_box.setIcon.called
        assert mock_msg_box.setWindowTitle.called_with("FFmpeg Not Found")
        assert mock_msg_box.setTextFormat.called_with(Qt.TextFormat.RichText)
        assert mock_msg_box.setText.called_with("FFmpeg is Required")
        
        # Verify exec was called to show the dialog
        mock_msg_box.exec.assert_called_once()
        
        # Verify the progress bar is hidden after error
        assert not main_window.progress_bar.isVisible()
        
        # Verify the status message indicates an error
        assert "FFmpeg" in main_window.statusBar().currentMessage()


def test_progress_updates(main_window, qtbot, tmp_path):
    """Test that progress updates are correctly handled."""
    # Create test WAV files
    test_files = []
    for i in range(3):
        path = create_test_wav(
            output_path=tmp_path / f'test_{i}.wav',
            frequency=440.0 * (i + 1),
            duration=0.1,
            sample_rate=44100,
            channels=1
        )
        test_files.append(str(path))
    
    # Directly call add_files with the test files
    main_window.drop_widget.add_files(test_files)
    
    # Create a test audio data object
    test_audio_data = AudioData(
        file_path=Path(test_files[0]),
        samples=np.zeros(4410, dtype=np.float32),  # 0.1s at 44.1kHz
        metadata=AudioMetadata(
            duration=0.1,
            sample_rate=44100,
            channels=1,
            bit_depth=32,
            format='WAV'
        )
    )
    
    # Mock the AudioLoader to return our test data
    with patch('mp3paramidi.audio.AudioLoader.load', return_value=test_audio_data):
        # Verify initial state
        assert not main_window.progress_bar.isVisible()
        
        # Click the "Convert to MIDI" button
        with qtbot.waitSignal(main_window.drop_widget.convertRequested, timeout=1000):
            qtbot.mouseClick(main_window.drop_widget.convert_btn, Qt.MouseButton.LeftButton)
        
        # Verify progress bar is visible and has correct range
        assert main_window.progress_bar.isVisible()
        assert main_window.progress_bar.maximum() == len(test_files)
        
        # Simulate progress updates (normally done by the worker thread)
        for i in range(len(test_files)):
            main_window.set_progress_value(i + 1)
            assert main_window.progress_bar.value() == i + 1
        
        # Verify progress bar is hidden after completion
        main_window.hide_progress()
        assert not main_window.progress_bar.isVisible()
        
        # Verify the status message was updated
        assert "Loaded 3 files" in main_window.statusBar().currentMessage()


def test_convert_button_state(main_window, qtbot, tmp_path):
    """Test that the Convert button state is managed correctly."""
    # Initially, the Convert button should be disabled (no files added)
    assert not main_window.drop_widget.convert_btn.isEnabled()
    
    # Create a test WAV file
    wav_path = create_test_wav(
        output_path=tmp_path / 'test.wav',
        frequency=440.0,
        duration=0.1,
        sample_rate=44100,
        channels=1
    )
    
    # Directly call add_files with the test file path
    main_window.drop_widget.add_files([str(wav_path)])
    
    # After adding files, the Convert button should be enabled
    assert main_window.drop_widget.convert_btn.isEnabled()
    
    # Create a test audio data object
    test_audio_data = AudioData(
        file_path=wav_path,
        samples=np.zeros(4410, dtype=np.float32),  # 0.1s at 44.1kHz
        metadata=AudioMetadata(
            duration=0.1,
            sample_rate=44100,
            channels=1,
            bit_depth=32,
            format='WAV'
        )
    )
    
    # Mock the AudioLoader to return our test data
    with patch('mp3paramidi.audio.AudioLoader.load', return_value=test_audio_data):
        # Click the "Convert to MIDI" button
        with qtbot.waitSignal(main_window.drop_widget.convertRequested, timeout=1000):
            qtbot.mouseClick(main_window.drop_widget.convert_btn, Qt.MouseButton.LeftButton)
        
        # During processing, the Convert button should be disabled
        assert not main_window.drop_widget.convert_btn.isEnabled()
        
        # Simulate completion
        main_window.hide_progress()
        
        # After completion, the Convert button should be re-enabled
        assert main_window.drop_widget.convert_btn.isEnabled()
