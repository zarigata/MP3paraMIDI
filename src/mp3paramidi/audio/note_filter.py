"""
Note filtering module for MP3paraMIDI.

This module provides filtering capabilities to remove spurious note detections
and improve the quality of generated MIDI files.
"""

from __future__ import annotations

import logging
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any

from .pitch_detector import NoteEvent


@dataclass
class FilterConfig:
    """Configuration for note filtering."""
    min_confidence: float = 0.3          # Minimum confidence threshold
    min_duration: float = 0.05           # Minimum duration in seconds
    max_duration: float = 10.0           # Maximum duration in seconds
    remove_outliers: bool = True         # Remove pitch outliers
    outlier_std_threshold: float = 3.0   # Standard deviations for outlier removal
    min_velocity: int = 20               # Minimum velocity threshold


class NoteFilter:
    """
    Enhanced note filter to remove spurious detections.
    
    Applies multiple filtering strategies in sequence to improve note detection quality.
    """
    
    def __init__(self, config: FilterConfig):
        """
        Initialize note filter with configuration.
        
        Args:
            config: FilterConfig object with filtering parameters
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def filter_notes(self, note_events: List[NoteEvent]) -> List[NoteEvent]:
        """
        Apply all filters to a list of note events.
        
        Args:
            note_events: List of notes to filter
            
        Returns:
            Filtered list of NoteEvent objects
        """
        if not note_events:
            return []
            
        original_count = len(note_events)
        filtered_notes = note_events.copy()
        
        # Apply filters in sequence
        filtered_notes = self._filter_by_confidence(filtered_notes)
        filtered_notes = self._filter_by_duration(filtered_notes)
        filtered_notes = self._filter_by_velocity(filtered_notes)
        
        if self.config.remove_outliers:
            filtered_notes = self._remove_pitch_outliers(filtered_notes)
        
        filtered_count = len(filtered_notes)
        removed_count = original_count - filtered_count
        
        self.logger.info(f"Filtered notes: {removed_count}/{original_count} removed "
                        f"({removed_count/original_count*100:.1f}%)")
        
        return filtered_notes
    
    def _filter_by_confidence(self, notes: List[NoteEvent]) -> List[NoteEvent]:
        """
        Filter notes by confidence threshold.
        
        Args:
            notes: List of notes to filter
            
        Returns:
            Notes with confidence above threshold
        """
        return [note for note in notes if note.confidence >= self.config.min_confidence]
    
    def _filter_by_duration(self, notes: List[NoteEvent]) -> List[NoteEvent]:
        """
        Filter notes by duration range.
        
        Args:
            notes: List of notes to filter
            
        Returns:
            Notes within duration range
        """
        filtered = []
        for note in notes:
            duration = note.end_time - note.start_time
            if (self.config.min_duration <= duration <= self.config.max_duration):
                filtered.append(note)
        return filtered
    
    def _filter_by_velocity(self, notes: List[NoteEvent]) -> List[NoteEvent]:
        """
        Filter notes by velocity threshold.
        
        Args:
            notes: List of notes to filter
            
        Returns:
            Notes with velocity above threshold
        """
        return [note for note in notes if note.velocity >= self.config.min_velocity]
    
    def _remove_pitch_outliers(self, notes: List[NoteEvent]) -> List[NoteEvent]:
        """
        Remove pitch outliers using statistical methods.
        
        Args:
            notes: List of notes to filter
            
        Returns:
            Notes without pitch outliers
        """
        if len(notes) < 3:
            # Not enough notes for meaningful outlier detection
            return notes
            
        # Calculate mean and standard deviation of MIDI note numbers
        midi_pitches = np.array([note.midi_note for note in notes])
        mean_pitch = np.mean(midi_pitches)
        std_pitch = np.std(midi_pitches)
        
        if std_pitch == 0:
            # All notes have same pitch - no outliers
            return notes
            
        # Remove notes more than N standard deviations from mean
        filtered = []
        for note in notes:
            if not self._is_outlier(note, mean_pitch, std_pitch):
                filtered.append(note)
            else:
                self.logger.debug(
                    f"Removed outlier note: midi_note={note.midi_note} "
                    f"(mean={mean_pitch:.1f}, std={std_pitch:.1f})"
                )
        
        return filtered
    
    def _is_outlier(self, note: NoteEvent, mean_pitch: float, std_pitch: float) -> bool:
        """
        Check if a note is a pitch outlier.
        
        Args:
            note: NoteEvent to check
            mean_pitch: Mean pitch value
            std_pitch: Standard deviation of pitches
            
        Returns:
            True if note is an outlier
        """
        z_score = abs(note.midi_note - mean_pitch) / std_pitch
        return z_score > self.config.outlier_std_threshold
    
    def get_filter_statistics(self, original: List[NoteEvent], filtered: List[NoteEvent]) -> Dict[str, Any]:
        """
        Get statistics about filtering results.
        
        Args:
            original: Original list of notes
            filtered: Filtered list of notes
            
        Returns:
            Dictionary with filtering statistics
        """
        original_count = len(original)
        filtered_count = len(filtered)
        removed_count = original_count - filtered_count
        
        return {
            'original_count': original_count,
            'filtered_count': filtered_count,
            'removed_count': removed_count,
            'removal_percentage': (removed_count / original_count * 100) if original_count > 0 else 0,
            'kept_percentage': (filtered_count / original_count * 100) if original_count > 0 else 0
        }
