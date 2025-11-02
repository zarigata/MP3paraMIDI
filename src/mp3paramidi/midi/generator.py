"""
MIDI file generation using pretty_midi.

This module provides a high-level interface for creating MIDI files from note events,
with support for different instruments, tempos, and note properties.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union, Any

import pretty_midi

from ..audio.pitch_detector import NoteEvent


logger = logging.getLogger(__name__)


class MidiGenerationError(Exception):
    """Exception raised for errors during MIDI file generation."""
    pass


@dataclass
class MidiInfo:
    """Metadata about a generated MIDI file."""
    note_count: int
    duration: float
    pitch_range: tuple[int, int]
    average_velocity: float


@dataclass(frozen=True)
class InstrumentMapping:
    """Describes how a separated stem should be rendered in MIDI.
    
    Attributes:
        stem_name: The name of the audio stem (e.g., 'drums', 'bass', 'vocals')
        program: The MIDI program number (0-127) for the instrument
        is_drum: Whether this is a drum/percussion instrument. When True, the stem
                will be assigned to MIDI channel 10 (9 in zero-based) as per the
                General MIDI standard.
    """

    stem_name: str
    program: int
    is_drum: bool = False


DEFAULT_INSTRUMENT_MAP: Dict[str, InstrumentMapping] = {
    "vocals": InstrumentMapping(stem_name="vocals", program=52),  # Choir Aahs
    "drums": InstrumentMapping(stem_name="drums", program=0, is_drum=True),
    "bass": InstrumentMapping(stem_name="bass", program=32),  # Acoustic Bass
    "other": InstrumentMapping(stem_name="other", program=48),  # String Ensemble 1
    "guitar": InstrumentMapping(stem_name="guitar", program=26),  # Jazz Guitar
    "piano": InstrumentMapping(stem_name="piano", program=0),  # Acoustic Grand Piano
}


class MidiGenerator:
    """Generates MIDI files from note events.
    
    Args:
        tempo: Tempo in beats per minute (default: 120.0).
        program: MIDI program number (0-127) for the instrument (default: 0, Acoustic Grand Piano).
    """
    
    def __init__(self, tempo: float = 120.0, program: int = 0):
        self.tempo = tempo
        self.program = program
    
    def create_midi(
        self,
        note_events: List[NoteEvent],
        output_path: Path,
        instrument_name: str = 'Acoustic Grand Piano'
    ) -> Path:
        """Create a MIDI file from note events.
        
        Args:
            note_events: List of NoteEvent objects to include in the MIDI file.
            output_path: Path where the MIDI file will be saved.
            instrument_name: Name of the instrument to use (default: 'Acoustic Grand Piano').
            
        Returns:
            Path to the generated MIDI file.
            
        Raises:
            MidiGenerationError: If there's an error creating the MIDI file.
        """
        try:
            self._validate_note_events(note_events)
            
            # Create a PrettyMIDI object with the specified tempo
            midi = pretty_midi.PrettyMIDI(initial_tempo=self.tempo)
            
            # Create an Instrument instance with the specified program
            instrument = pretty_midi.Instrument(program=self.program, name=instrument_name)
            
            # Add notes to the instrument
            for event in note_events:
                note = pretty_midi.Note(
                    velocity=event.velocity,
                    pitch=event.midi_note,
                    start=event.start_time,
                    end=event.end_time
                )
                instrument.notes.append(note)
            
            # Add the instrument to the PrettyMIDI object
            midi.instruments.append(instrument)
            
            # Write the MIDI file
            midi.write(str(output_path))
            
            return output_path
            
        except Exception as e:
            raise MidiGenerationError(f"Failed to create MIDI file: {str(e)}")
    
    def create_multi_track_midi(
        self,
        stems_notes: Dict[str, List[NoteEvent]],
        output_path: Path,
        instrument_map: Optional[Dict[str, InstrumentMapping]] = None,
    ) -> Path:
        """Create a multi-track MIDI file from separated stems.

        This creates a multi-track MIDI file where each stem is assigned to a separate
        track with appropriate instrument settings. Drums are always assigned to MIDI
        channel 10 (9 in zero-based indexing) as per the General MIDI standard.

        Args:
            stems_notes: Mapping of stem name to a list of NoteEvent objects.
            output_path: Destination path for the MIDI file.
            instrument_map: Optional override mapping for instrument assignments per stem.
                Use this to customize the MIDI program and drum settings for each stem.

        Returns:
            Path to the generated MIDI file.

        Raises:
            MidiGenerationError: If validation fails or MIDI cannot be written.
        """
        try:
            normalized: Dict[str, List[NoteEvent]] = {
                stem: list(notes) for stem, notes in stems_notes.items()
            }
            self._validate_multi_track_input(normalized)

            midi = pretty_midi.PrettyMIDI(initial_tempo=self.tempo)
            mapping = instrument_map or self.get_instrument_map_for_stems(list(normalized.keys()))

            # Track used channels to avoid conflicts
            used_channels = set()
            
            for stem_name, note_list in normalized.items():
                if not note_list:
                    logger.debug("Skipping stem '%s' with no note events", stem_name)
                    continue
                    
                instrument_cfg = mapping.get(stem_name)
                if instrument_cfg is None:
                    instrument_cfg = InstrumentMapping(stem_name=stem_name, program=self.program)

                # Create instrument with appropriate settings
                if instrument_cfg.is_drum:
                    # Use channel 10 (9 in zero-based) for drums as per GM standard
                    instrument = pretty_midi.Instrument(
                        program=0,  # Program 0 for drums (though it's often ignored for channel 10)
                        is_drum=True,
                        name=stem_name,
                    )
                    # Explicitly set channel 10 (9 in zero-based) for drums
                    instrument.program = 0  # Set to 0 (Acoustic Grand Piano) as a fallback
                    instrument.channel = 9   # Channel 10 (0-based)
                    used_channels.add(9)     # Mark channel 10 as used
                else:
                    # Find an available channel (skip channel 9 which is reserved for drums)
                    channel = 0
                    while channel in used_channels or channel == 9:  # Skip channel 10 (drums)
                        channel = (channel + 1) % 16
                        if channel not in used_channels:
                            break
                    
                    instrument = pretty_midi.Instrument(
                        program=instrument_cfg.program,
                        name=stem_name,
                    )
                    instrument.channel = channel
                    used_channels.add(channel)

                self._validate_note_events(note_list)
                instrument.notes.extend(
                    pretty_midi.Note(
                        velocity=event.velocity,
                        pitch=event.midi_note,
                        start=event.start_time,
                        end=event.end_time,
                    )
                    for event in note_list
                )
                midi.instruments.append(instrument)

            midi.write(str(output_path))
            return output_path
        except MidiGenerationError:
            raise
        except Exception as exc:
            raise MidiGenerationError(f"Failed to create multi-track MIDI file: {str(exc)}")

    def get_instrument_map_for_stems(self, stem_names: List[str]) -> Dict[str, InstrumentMapping]:
        """Build a mapping of stems to instruments, falling back to defaults.
        
        This method maps stem names to instrument configurations. For drum stems,
        it ensures they're marked as drums and will be assigned to MIDI channel 10.
        
        Args:
            stem_names: List of stem names to create mappings for.
            
        Returns:
            A dictionary mapping stem names to InstrumentMapping objects.
            
        Note:
            - Drums are always assigned to MIDI channel 10 (9 in zero-based)
            - Other instruments are assigned to the next available channel
            - The default program is Acoustic Grand Piano (program 0)
        """
        mapping: Dict[str, InstrumentMapping] = {}
        for name in stem_names:
            lower = name.lower()
            if lower in DEFAULT_INSTRUMENT_MAP:
                mapping[name] = DEFAULT_INSTRUMENT_MAP[lower]
            else:
                # Create a new mapping with default settings
                mapping[name] = InstrumentMapping(
                    stem_name=name,
                    program=self.program,
                    is_drum=('drum' in lower or 'drums' in lower or 'percussion' in lower)
                )
        return mapping

    def get_midi_info(self, note_source: Union[List[NoteEvent], Dict[str, List[NoteEvent]]]) -> dict:
        """Get metadata about the MIDI that would be generated from note events.

        Args:
            note_source: Either a list of NoteEvent objects or a mapping of stem name
                to lists of NoteEvent objects for multi-track MIDI.

        Returns:
            Dictionary containing MIDI metadata. When a dict of stems is provided the
            metadata is calculated per stem under the ``tracks`` key.
        """
        if isinstance(note_source, dict):
            per_track: Dict[str, dict] = {}
            for stem, notes in note_source.items():
                per_track[stem] = self.get_midi_info(list(notes))

            total_note_count = sum(track.get('note_count', 0) for track in per_track.values())
            total_duration = max((track.get('duration', 0.0) for track in per_track.values()), default=0.0)
            pitch_mins = [track['pitch_range'][0] for track in per_track.values() if track.get('note_count')]
            pitch_maxes = [track['pitch_range'][1] for track in per_track.values() if track.get('note_count')]
            avg_velocities = [track.get('average_velocity', 0.0) for track in per_track.values() if track.get('note_count')]
            aggregated_velocity = sum(avg_velocities) / len(avg_velocities) if avg_velocities else 0.0
            return {
                'note_count': total_note_count,
                'duration': total_duration,
                'pitch_range': (
                    min(pitch_mins) if pitch_mins else 0,
                    max(pitch_maxes) if pitch_maxes else 0,
                ),
                'average_velocity': aggregated_velocity,
                'tracks': per_track,
            }

        note_events = note_source
        if not note_events:
            return {
                'note_count': 0,
                'duration': 0.0,
                'pitch_range': (0, 0),
                'average_velocity': 0,
            }

        start_times = [n.start_time for n in note_events]
        end_times = [n.end_time for n in note_events]
        duration = max(end_times) - min(start_times)
        pitches = [n.midi_note for n in note_events]
        pitch_range = (min(pitches), max(pitches))
        note_count = len(note_events)
        avg_velocity = sum(n.velocity for n in note_events) / note_count

        return {
            'note_count': note_count,
            'duration': duration,
            'pitch_range': pitch_range,
            'average_velocity': avg_velocity,
        }

    def _validate_multi_track_input(self, stems_notes: Dict[str, List[NoteEvent]]) -> None:
        """Ensure multi-track inputs are well formed before MIDI generation."""
        if not stems_notes:
            raise MidiGenerationError("No stems provided for multi-track MIDI generation")

        for stem, notes in stems_notes.items():
            if not isinstance(stem, str) or not stem:
                raise MidiGenerationError("Stem names must be non-empty strings")
            if not isinstance(notes, Iterable):
                raise MidiGenerationError(f"Notes for stem '{stem}' must be iterable")
            for index, event in enumerate(notes):
                if not isinstance(event, NoteEvent):
                    raise MidiGenerationError(
                        f"Invalid note event at index {index} for stem '{stem}'"
                    )
    
    def _validate_note_events(self, note_events: List[NoteEvent]) -> None:
        """Validate note events before MIDI generation.
        
        Args:
            note_events: List of NoteEvent objects to validate.
            
        Raises:
            MidiGenerationError: If any note events are invalid.
        """
        if not note_events:
            raise MidiGenerationError("No note events provided")
        
        for i, event in enumerate(note_events):
            # Check for negative times
            if event.start_time < 0 or event.end_time < 0:
                raise MidiGenerationError(
                    f"Note {i} has negative time values: start={event.start_time}, end={event.end_time}"
                )
            
            # Check for invalid duration
            if event.end_time <= event.start_time:
                raise MidiGenerationError(
                    f"Note {i} has invalid duration: start={event.start_time}, end={event.end_time}"
                )
            
            # Check MIDI note range
            if not (0 <= event.midi_note <= 127):
                raise MidiGenerationError(
                    f"Note {i} has invalid MIDI note: {event.midi_note} (must be 0-127)"
                )
            
            # Check velocity range
            if not (1 <= event.velocity <= 127):
                raise MidiGenerationError(
                    f"Note {i} has invalid velocity: {event.velocity} (must be 1-127)"
                )
