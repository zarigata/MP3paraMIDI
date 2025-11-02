"""
Note quantization module for MP3paraMIDI.

This module provides note quantization functionality to snap note timings
to a musical grid, improving the rhythmic accuracy of generated MIDI files.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import List

from ..audio.pitch_detector import NoteEvent


class QuantizationGrid(Enum):
    """Quantization grid sizes."""
    QUARTER = 1.0      # 1/4 note
    EIGHTH = 0.5       # 1/8 note  
    SIXTEENTH = 0.25   # 1/16 note
    THIRTY_SECOND = 0.125  # 1/32 note
    NONE = 0.0         # No quantization


@dataclass
class NoteQuantizer:
    """
    Note quantizer that snaps note timings to a musical grid.
    
    The quantizer preserves pitch, velocity, and confidence while adjusting
    start_time and end_time to align with the specified grid.
    """
    
    grid: QuantizationGrid = QuantizationGrid.SIXTEENTH
    tempo: float = 120.0
    swing: float = 0.0
    
    def quantize_notes(self, note_events: List[NoteEvent]) -> List[NoteEvent]:
        """
        Quantize a list of note events to the specified grid.
        
        Args:
            note_events: List of notes to quantize
            
        Returns:
            List of quantized NoteEvent objects
        """
        if self.grid == QuantizationGrid.NONE:
            return note_events.copy()
            
        grid_size = self._calculate_grid_size(self.tempo, self.grid)
        quantized_notes = []
        
        for note in note_events:
            quantized_note = self.quantize_single_note(note)
            quantized_notes.append(quantized_note)
            
        return quantized_notes
    
    def quantize_single_note(self, note: NoteEvent) -> NoteEvent:
        """
        Quantize a single note event.
        
        Args:
            note: Single NoteEvent to quantize
            
        Returns:
            Quantized NoteEvent
        """
        if self.grid == QuantizationGrid.NONE:
            return note
            
        grid_size = self._calculate_grid_size(self.tempo, self.grid)
        
        # Snap start time to nearest grid point
        quantized_start = round(note.start_time / grid_size) * grid_size
        
        # Snap end time similarly but ensure minimum duration
        quantized_end = round(note.end_time / grid_size) * grid_size
        
        # Ensure minimum duration of at least one grid unit
        if quantized_end - quantized_start < grid_size:
            quantized_end = quantized_start + grid_size
            
        return NoteEvent(
            start_time=quantized_start,
            end_time=quantized_end,
            pitch_hz=note.pitch_hz,
            midi_note=note.midi_note,
            velocity=note.velocity,
            confidence=note.confidence
        )
    
    def _calculate_grid_size(self, tempo: float, grid: QuantizationGrid) -> float:
        """
        Convert musical time (beats) to seconds based on tempo.
        
        Args:
            tempo: Tempo in BPM
            grid: Quantization grid type
            
        Returns:
            Grid size in seconds
        """
        if grid == QuantizationGrid.NONE:
            return 0.0
            
        # Formula: 60 seconds / tempo beats_per_minute * grid_fraction beats
        return 60.0 / tempo * grid.value
