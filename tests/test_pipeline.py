"""Tests for the audio-to-MIDI pipeline."""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from mp3paramidi.audio import (
    AudioToMidiPipeline,
    NoteEvent,
    PipelineProgress,
    PipelineResult,
)
from tests.fixtures.audio_generators import generate_sine_wave
from tests.helpers import create_audio_data

# Test parameters
SAMPLE_RATE = 44100


def test_pipeline_basic_conversion():
    """Test basic audio-to-MIDI conversion with a simple sine wave."""
    # Create a simple audio signal (A4 for 0.5s)
    duration = 0.5
    audio_data = create_audio_data(
        samples=generate_sine_wave(440.0, duration, SAMPLE_RATE, channels=1),
        sample_rate=SAMPLE_RATE,
    )
    
    # Create a temporary output file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as tmp_file:
        output_path = Path(tmp_file.name)
    
    try:
        # Create and run pipeline
        pipeline = AudioToMidiPipeline()
        result = pipeline.process(audio_data, output_path)
        
        # Verify the result
        assert result.success is True
        assert result.output_path == output_path
        assert result.output_path.exists()
        assert result.note_count > 0
        assert result.duration > 0
        assert result.processing_time > 0
        assert result.error_message is None
        
        # Verify the output file is not empty
        assert output_path.stat().st_size > 0
        
    finally:
        # Clean up
        if output_path.exists():
            os.unlink(output_path)


def test_pipeline_progress_callback():
    """Test that progress callbacks are called with expected values."""
    # Create a simple audio signal
    audio_data = create_audio_data(
        samples=generate_sine_wave(440.0, 0.2, SAMPLE_RATE, channels=1),
        sample_rate=SAMPLE_RATE,
    )
    
    # Mock progress callback
    mock_callback = MagicMock()
    
    # Create and run pipeline with mock callback
    pipeline = AudioToMidiPipeline(progress_callback=mock_callback)
    
    with tempfile.NamedTemporaryFile(suffix='.mid') as tmp_file:
        result = pipeline.process(audio_data, Path(tmp_file.name))
    
    # Verify the callback was called multiple times with increasing progress
    assert mock_callback.call_count >= 3  # At least 3 stages: loading, processing, saving
    
    # Get all calls and extract progress values
    calls = mock_callback.call_args_list
    progress_values = [call[0][0].progress for call in calls]
    
    # Progress should be non-decreasing
    assert all(p1 <= p2 for p1, p2 in zip(progress_values, progress_values[1:]))
    
    # First call should have 0 progress
    first_call = calls[0][0][0]
    assert first_call.progress == 0
    
    # Last call should have 1.0 progress
    last_call = calls[-1][0][0]
    assert last_call.progress == 1.0


def test_pipeline_default_output_path():
    """Test that the pipeline generates a default output path if none is provided."""
    # Create a simple audio signal
    audio_data = create_audio_data(
        samples=generate_sine_wave(440.0, 0.2, SAMPLE_RATE, channels=1),
        sample_rate=SAMPLE_RATE,
        file_path=Path("test_audio.wav"),
    )
    
    # Create and run pipeline without output path
    pipeline = AudioToMidiPipeline()
    result = pipeline.process(audio_data)
    
    try:
        # Verify the result
        assert result.success is True
        assert result.output_path is not None
        assert result.output_path.suffix == '.mid'
        assert result.output_path.stem == 'test_audio'
        assert result.output_path.exists()
        
    finally:
        # Clean up
        if result.output_path and result.output_path.exists():
            os.unlink(result.output_path)


def test_pipeline_empty_audio():
    """Test that empty audio results in a failed conversion with an error message."""
    # Create empty audio
    audio_data = create_audio_data(
        samples=np.zeros((0,), dtype=np.float32),
        sample_rate=SAMPLE_RATE,
    )
    
    # Create and run pipeline
    pipeline = AudioToMidiPipeline()
    result = pipeline.process(audio_data)
    
    # Verify the result indicates failure
    assert result.success is False
    assert result.output_path is None
    assert "empty" in result.error_message.lower()
    assert result.note_count == 0
    assert result.duration == 0


def test_pipeline_silent_audio():
    """Test that silent audio results in no notes detected."""
    # Create silent audio (all zeros)
    audio_data = create_audio_data(
        samples=np.zeros((SAMPLE_RATE,), dtype=np.float32),
        sample_rate=SAMPLE_RATE,
    )
    
    # Create and run pipeline
    pipeline = AudioToMidiPipeline()
    with tempfile.NamedTemporaryFile(suffix='.mid') as tmp_file:
        result = pipeline.process(audio_data, Path(tmp_file.name))
    
    # Verify the result indicates success but no notes
    assert result.success is True
    assert result.note_count == 0
    assert result.duration > 0


def test_pipeline_custom_parameters():
    """Test that custom parameters are passed to the pitch detector and MIDI generator."""
    # Create a simple audio signal
    audio_data = create_audio_data(
        samples=generate_sine_wave(440.0, 0.2, SAMPLE_RATE, channels=1),
        sample_rate=SAMPLE_RATE,
    )

    with patch('mp3paramidi.audio.pipeline.PitchDetector') as mock_pitch_detector_cls, \
         patch('mp3paramidi.audio.pipeline.MidiGenerator') as mock_midi_generator_cls:
        
        # Set up mocks
        mock_pitch_detector = MagicMock()
        mock_pitch_detector.detect_pitch.return_value = [MagicMock()]
        mock_pitch_detector.segment_notes.return_value = [MagicMock(spec=NoteEvent)]
        mock_pitch_detector_cls.return_value = mock_pitch_detector
        
        mock_midi_generator = MagicMock()
        mock_midi_generator.get_midi_info.return_value = {
            'note_count': 1,
            'duration': 0.5,
            'pitch_range': (60, 60),
            'average_velocity': 80,
        }
        mock_midi_generator.create_midi.return_value = Path('output.mid')
        mock_midi_generator_cls.return_value = mock_midi_generator
        
        # Create and run pipeline with custom parameters
        pipeline = AudioToMidiPipeline(
            fmin='C3',
            fmax='C6',
            tempo=140.0,
            min_note_duration=0.1
        )
        
        with tempfile.NamedTemporaryFile(suffix='.mid') as tmp_file:
            pipeline.process(audio_data, Path(tmp_file.name))
        
        # Verify PitchDetector was created with correct parameters
        mock_pitch_detector_cls.assert_called_once_with(
            fmin='C3',
            fmax='C6',
        )
        
        # Verify MidiGenerator was created with correct tempo
        mock_midi_generator_cls.assert_called_once_with(
            tempo=140.0,
            program=0  # Default program (Acoustic Grand Piano)
        )
        
        # Verify segment_notes was called with custom min_note_duration
        mock_pitch_detector.segment_notes.assert_called_once()
        assert mock_pitch_detector.segment_notes.call_args[1]['min_note_duration'] == 0.1
