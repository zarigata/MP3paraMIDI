"""
Tests for the note filtering module.
"""
import pytest
import numpy as np
from pathlib import Path

from mp3paramidi.audio.note_filter import NoteFilter, FilterConfig
from mp3paramidi.audio.pitch_detector import NoteEvent


class TestFilterConfig:
    """Test the FilterConfig dataclass."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = FilterConfig()
        
        assert config.min_confidence == 0.3
        assert config.min_duration == 0.05
        assert config.min_velocity == 40
        assert config.max_velocity == 110
        assert config.remove_outliers == True
        assert config.outlier_std_threshold == 2.0
    
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = FilterConfig(
            min_confidence=0.5,
            min_duration=0.1,
            min_velocity=50,
            max_velocity=100,
            remove_outliers=False,
            outlier_std_threshold=1.5
        )
        
        assert config.min_confidence == 0.5
        assert config.min_duration == 0.1
        assert config.min_velocity == 50
        assert config.max_velocity == 100
        assert config.remove_outliers == False
        assert config.outlier_std_threshold == 1.5


class TestNoteFilter:
    """Test the NoteFilter class."""
    
    @pytest.fixture
    def sample_notes(self) -> list[NoteEvent]:
        """Create sample note events for testing."""
        return [
            # Good note (should pass all filters)
            NoteEvent(
                start_time=0.0,
                end_time=0.5,
                pitch_hz=440.0,
                midi_note=69,
                velocity=80,
                confidence=0.9
            ),
            # Low confidence note (should be filtered)
            NoteEvent(
                start_time=0.6,
                end_time=1.1,
                pitch_hz=523.25,
                midi_note=72,
                velocity=75,
                confidence=0.2
            ),
            # Short duration note (should be filtered)
            NoteEvent(
                start_time=1.2,
                end_time=1.22,
                pitch_hz=659.25,
                midi_note=76,
                velocity=70,
                confidence=0.8
            ),
            # Low velocity note (should be filtered)
            NoteEvent(
                start_time=1.3,
                end_time=1.8,
                pitch_hz=392.0,
                midi_note=67,
                velocity=30,
                confidence=0.85
            ),
            # High velocity note (should be filtered)
            NoteEvent(
                start_time=1.9,
                end_time=2.4,
                pitch_hz=880.0,
                midi_note=81,
                velocity=120,
                confidence=0.9
            ),
            # Pitch outlier (should be filtered if outlier removal enabled)
            NoteEvent(
                start_time=2.5,
                end_time=3.0,
                pitch_hz=50.0,  # Very low pitch
                midi_note=28,
                velocity=75,
                confidence=0.8
            ),
        ]
    
    def test_filter_initialization(self) -> None:
        """Test filter initialization."""
        config = FilterConfig(min_confidence=0.5)
        filter = NoteFilter(config)
        
        assert filter.config.min_confidence == 0.5
    
    def test_filter_by_confidence(self, sample_notes: list[NoteEvent]) -> None:
        """Test filtering by confidence threshold."""
        config = FilterConfig(min_confidence=0.5)
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(sample_notes)
        
        # Should only keep notes with confidence >= 0.5
        assert len(filtered) == 5  # All except the low confidence note
        
        for note in filtered:
            assert note.confidence >= 0.5
    
    def test_filter_by_duration(self, sample_notes: list[NoteEvent]) -> None:
        """Test filtering by minimum duration."""
        config = FilterConfig(min_duration=0.3)
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(sample_notes)
        
        # Should only keep notes with duration >= 0.3s
        assert len(filtered) == 5  # All except the short duration note
        
        for note in filtered:
            duration = note.end_time - note.start_time
            assert duration >= 0.3
    
    def test_filter_by_velocity(self, sample_notes: list[NoteEvent]) -> None:
        """Test filtering by velocity range."""
        config = FilterConfig(min_velocity=50, max_velocity=100)
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(sample_notes)
        
        # Should only keep notes with velocity between 50 and 100
        assert len(filtered) == 4  # Filter out low and high velocity notes
        
        for note in filtered:
            assert 50 <= note.velocity <= 100
    
    def test_filter_outliers(self, sample_notes: list[NoteEvent]) -> None:
        """Test filtering pitch outliers."""
        config = FilterConfig(remove_outliers=True, outlier_std_threshold=1.5)
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(sample_notes)
        
        # Should filter out the pitch outlier (MIDI note 28)
        assert len(filtered) == 5
        
        # Check that outlier was removed
        midi_notes = [note.midi_note for note in filtered]
        assert 28 not in midi_notes
    
    def test_no_outlier_removal(self, sample_notes: list[NoteEvent]) -> None:
        """Test that outlier removal can be disabled."""
        config = FilterConfig(remove_outliers=False)
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(sample_notes)
        
        # Should keep all notes except those filtered by other criteria
        assert len(filtered) == 6  # Only low confidence note filtered
        
        # Check that outlier is still present
        midi_notes = [note.midi_note for note in filtered]
        assert 28 in midi_notes
    
    def test_combined_filters(self, sample_notes: list[NoteEvent]) -> None:
        """Test multiple filters applied together."""
        config = FilterConfig(
            min_confidence=0.5,
            min_duration=0.1,
            min_velocity=50,
            max_velocity=100,
            remove_outliers=True
        )
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(sample_notes)
        
        # Should only keep notes that pass ALL filters
        assert len(filtered) == 2  # Only the first note and maybe one other
        
        for note in filtered:
            assert note.confidence >= 0.5
            assert (note.end_time - note.start_time) >= 0.1
            assert 50 <= note.velocity <= 100
    
    def test_empty_note_list(self) -> None:
        """Test filtering an empty list of notes."""
        filter = NoteFilter()
        filtered = filter.filter_notes([])
        assert filtered == []
    
    def test_all_notes_filtered(self, sample_notes: list[NoteEvent]) -> None:
        """Test when all notes are filtered out."""
        config = FilterConfig(min_confidence=0.95)  # Very high threshold
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(sample_notes)
        
        # Should return empty list
        assert filtered == []
    
    def test_statistics_tracking(self, sample_notes: list[NoteEvent]) -> None:
        """Test that filter statistics are tracked."""
        filter = NoteFilter()
        
        filtered = filter.filter_notes(sample_notes)
        
        # Check that statistics were updated
        stats = filter.get_statistics()
        assert 'original_count' in stats
        assert 'filtered_count' in stats
        assert 'confidence_filtered' in stats
        assert 'duration_filtered' in stats
        assert 'velocity_filtered' in stats
        assert 'outliers_filtered' in stats
        
        assert stats['original_count'] == len(sample_notes)
        assert stats['filtered_count'] == len(sample_notes) - len(filtered)
    
    def test_reset_statistics(self, sample_notes: list[NoteEvent]) -> None:
        """Test resetting filter statistics."""
        filter = NoteFilter()
        
        # Filter once to generate statistics
        filter.filter_notes(sample_notes)
        stats_before = filter.get_statistics()
        assert stats_before['original_count'] > 0
        
        # Reset and check statistics are cleared
        filter.reset_statistics()
        stats_after = filter.get_statistics()
        assert stats_after['original_count'] == 0
        assert stats_after['filtered_count'] == 0
    
    def test_pitch_outlier_detection(self) -> None:
        """Test pitch outlier detection algorithm."""
        # Create notes with one clear outlier
        notes = [
            NoteEvent(0.0, 0.5, 440.0, 69, 80, 0.9),   # A4
            NoteEvent(0.6, 1.1, 523.25, 72, 75, 0.8),  # C5
            NoteEvent(1.2, 1.7, 659.25, 76, 70, 0.85), # E5
            NoteEvent(1.8, 2.3, 783.99, 78, 65, 0.9),  # G5
            NoteEvent(2.4, 2.9, 50.0, 28, 75, 0.8),    # Very low outlier
        ]
        
        config = FilterConfig(remove_outliers=True, outlier_std_threshold=2.0)
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(notes)
        
        # Should remove the outlier
        assert len(filtered) == 4
        midi_notes = [note.midi_note for note in filtered]
        assert 28 not in midi_notes
    
    def test_velocity_outlier_detection(self) -> None:
        """Test velocity outlier detection."""
        # Create notes with velocity outliers
        notes = [
            NoteEvent(0.0, 0.5, 440.0, 69, 80, 0.9),   # Normal
            NoteEvent(0.6, 1.1, 523.25, 72, 75, 0.8),  # Normal
            NoteEvent(1.2, 1.7, 659.25, 76, 70, 0.85), # Normal
            NoteEvent(1.8, 2.3, 783.99, 78, 10, 0.9),  # Low velocity outlier
            NoteEvent(2.4, 2.9, 880.0, 81, 127, 0.8),  # High velocity outlier
        ]
        
        config = FilterConfig(
            min_velocity=40,
            max_velocity=110,
            remove_outliers=False  # Test velocity bounds only
        )
        filter = NoteFilter(config)
        
        filtered = filter.filter_notes(notes)
        
        # Should filter by velocity bounds
        assert len(filtered) == 3  # Only normal velocity notes
        
        for note in filtered:
            assert 40 <= note.velocity <= 110
    
    def test_different_outlier_thresholds(self) -> None:
        """Test different outlier threshold values."""
        notes = [
            NoteEvent(0.0, 0.5, 440.0, 69, 80, 0.9),
            NoteEvent(0.6, 1.1, 523.25, 72, 75, 0.8),
            NoteEvent(1.2, 1.7, 659.25, 76, 70, 0.85),
            NoteEvent(1.8, 2.3, 880.0, 81, 65, 0.9),  # Slightly higher
        ]
        
        # Strict threshold (should filter more)
        config_strict = FilterConfig(remove_outliers=True, outlier_std_threshold=1.0)
        filter_strict = NoteFilter(config_strict)
        filtered_strict = filter_strict.filter_notes(notes)
        
        # Lenient threshold (should filter less)
        config_lenient = FilterConfig(remove_outliers=True, outlier_std_threshold=3.0)
        filter_lenient = NoteFilter(config_lenient)
        filtered_lenient = filter_lenient.filter_notes(notes)
        
        # Strict should filter more than lenient
        assert len(filtered_strict) <= len(filtered_lenient)
