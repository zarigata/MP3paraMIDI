"""
Tests for the MIDI note quantizer module.
"""
import pytest
import numpy as np
from pathlib import Path

from mp3paramidi.midi.quantizer import NoteQuantizer, QuantizationGrid
from mp3paramidi.audio.pitch_detector import NoteEvent


class TestQuantizationGrid:
    """Test the QuantizationGrid enum."""
    
    def test_grid_values(self) -> None:
        """Test that grid values are correct."""
        assert QuantizationGrid.QUARTER.value == 1.0
        assert QuantizationGrid.EIGHTH.value == 0.5
        assert QuantizationGrid.SIXTEENTH.value == 0.25
        assert QuantizationGrid.THIRTY_SECOND.value == 0.125
        assert QuantizationGrid.NONE.value == 0.0
    
    def test_grid_comparison(self) -> None:
        """Test grid comparison operations."""
        assert QuantizationGrid.SIXTEENTH.value < QuantizationGrid.EIGHTH.value
        assert QuantizationGrid.QUARTER.value > QuantizationGrid.SIXTEENTH.value
        assert QuantizationGrid.NONE == QuantizationGrid.NONE


class TestNoteQuantizer:
    """Test the NoteQuantizer class."""
    
    @pytest.fixture
    def sample_notes(self) -> list[NoteEvent]:
        """Create sample note events for testing."""
        return [
            NoteEvent(
                start_time=0.0,
                end_time=0.5,
                pitch_hz=440.0,
                midi_note=69,
                velocity=80,
                confidence=0.9
            ),
            NoteEvent(
                start_time=0.52,
                end_time=1.02,
                pitch_hz=523.25,
                midi_note=72,
                velocity=75,
                confidence=0.85
            ),
            NoteEvent(
                start_time=1.55,
                end_time=2.05,
                pitch_hz=659.25,
                midi_note=76,
                velocity=70,
                confidence=0.8
            ),
            NoteEvent(
                start_time=2.51,
                end_time=3.01,
                pitch_hz=783.99,
                midi_note=78,
                velocity=65,
                confidence=0.75
            ),
        ]
    
    def test_quantizer_initialization(self) -> None:
        """Test quantizer initialization."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=120.0)
        assert quantizer.grid == QuantizationGrid.SIXTEENTH
        assert quantizer.tempo == 120.0
    
    def test_calculate_grid_size(self) -> None:
        """Test grid size calculation."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=120.0)
        grid_size = quantizer._calculate_grid_size(120.0, QuantizationGrid.SIXTEENTH)
        # 16th notes at 120 BPM = 0.125 seconds
        assert abs(grid_size - 0.125) < 0.001
        
        # Test different tempo
        grid_size_60 = quantizer._calculate_grid_size(60.0, QuantizationGrid.SIXTEENTH)
        # 16th notes at 60 BPM = 0.25 seconds
        assert abs(grid_size_60 - 0.25) < 0.001
    
    def test_quantize_single_note(self) -> None:
        """Test quantizing a single note."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=120.0)
        
        # Note that should quantize to beat 0
        note = NoteEvent(
            start_time=0.05,
            end_time=0.55,
            pitch_hz=440.0,
            midi_note=69,
            velocity=80,
            confidence=0.9
        )
        
        quantized = quantizer.quantize_single_note(note)
        assert quantized.start_time == 0.0  # Should snap to 0
        assert quantized.end_time == 0.5   # Should maintain duration
        assert quantized.pitch_hz == note.pitch_hz
        assert quantized.midi_note == note.midi_note
    
    def test_quantize_notes_sixteenth_grid(self, sample_notes: list[NoteEvent]) -> None:
        """Test quantizing notes to 16th note grid."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=120.0)
        quantized = quantizer.quantize_notes(sample_notes)
        
        # Check that start times are quantized to 16th note grid (0.125s intervals)
        expected_starts = [0.0, 0.5, 1.5, 2.5]
        for i, note in enumerate(quantized):
            assert abs(note.start_time - expected_starts[i]) < 0.001
            # Check that duration is preserved
            original_duration = sample_notes[i].end_time - sample_notes[i].start_time
            quantized_duration = note.end_time - note.start_time
            assert abs(quantized_duration - original_duration) < 0.001
    
    def test_quantize_notes_eighth_grid(self, sample_notes: list[NoteEvent]) -> None:
        """Test quantizing notes to 8th note grid."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.EIGHTH, tempo=120.0)
        quantized = quantizer.quantize_notes(sample_notes)
        
        # Check that start times are quantized to 8th note grid (0.25s intervals)
        expected_starts = [0.0, 0.5, 1.5, 2.5]
        for i, note in enumerate(quantized):
            assert abs(note.start_time - expected_starts[i]) < 0.001
    
    def test_quantize_notes_quarter_grid(self, sample_notes: list[NoteEvent]) -> None:
        """Test quantizing notes to quarter note grid."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.QUARTER, tempo=120.0)
        quantized = quantizer.quantize_notes(sample_notes)
        
        # Check that start times are quantized to quarter note grid (0.5s intervals)
        expected_starts = [0.0, 0.5, 1.5, 2.5]
        for i, note in enumerate(quantized):
            assert abs(note.start_time - expected_starts[i]) < 0.001
    
    def test_quantize_notes_none_grid(self, sample_notes: list[NoteEvent]) -> None:
        """Test that NONE grid doesn't modify notes."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.NONE, tempo=120.0)
        quantized = quantizer.quantize_notes(sample_notes)
        
        # Notes should remain unchanged
        for i, note in enumerate(quantized):
            assert abs(note.start_time - sample_notes[i].start_time) < 0.001
            assert abs(note.end_time - sample_notes[i].end_time) < 0.001
    
    def test_preserve_minimum_duration(self) -> None:
        """Test that minimum note duration is preserved."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=120.0)
        
        # Create a very short note
        short_note = NoteEvent(
            start_time=0.0,
            end_time=0.01,  # Very short duration
            pitch_hz=440.0,
            midi_note=69,
            velocity=80,
            confidence=0.9
        )
        
        quantized = quantizer.quantize_single_note(short_note)
        duration = quantized.end_time - quantized.start_time
        assert duration >= 0.05  # Should preserve minimum duration
    
    def test_empty_note_list(self) -> None:
        """Test quantizing an empty list of notes."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=120.0)
        quantized = quantizer.quantize_notes([])
        assert quantized == []
    
    def test_different_tempos(self) -> None:
        """Test quantization with different tempos."""
        # Fast tempo
        quantizer_fast = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=240.0)
        grid_size_fast = quantizer_fast._calculate_grid_size(240.0, QuantizationGrid.SIXTEENTH)
        assert abs(grid_size_fast - 0.0625) < 0.001  # Half the time
        
        # Slow tempo
        quantizer_slow = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=60.0)
        grid_size_slow = quantizer_slow._calculate_grid_size(60.0, QuantizationGrid.SIXTEENTH)
        assert abs(grid_size_slow - 0.25) < 0.001  # Double the time
    
    def test_tempo_change_after_initialization(self) -> None:
        """Test changing tempo after initialization."""
        quantizer = NoteQuantizer(grid=QuantizationGrid.SIXTEENTH, tempo=120.0)
        
        note = NoteEvent(
            start_time=0.1,
            end_time=0.6,
            pitch_hz=440.0,
            midi_note=69,
            velocity=80,
            confidence=0.9
        )
        
        # Quantize with original tempo
        quantized_120 = quantizer.quantize_single_note(note)
        
        # Change tempo
        quantizer.tempo = 60.0
        
        # Quantize same note with new tempo
        quantized_60 = quantizer.quantize_single_note(note)
        
        # Results should be different due to different grid sizes
        assert quantized_120.start_time != quantized_60.start_time
