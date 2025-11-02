"""Tests for MIDI file generation."""
import os
import tempfile
import numpy as np
import pytest
import pretty_midi
from pathlib import Path

from mp3paramidi.audio import NoteEvent
from mp3paramidi.midi.generator import MidiGenerator, MidiGenerationError


def test_create_midi_basic():
    """Test basic MIDI file creation with valid note events."""
    # Create test note events
    notes = [
        NoteEvent(
            start_time=0.0,
            end_time=0.5,
            pitch_hz=440.0,  # A4
            midi_note=69,
            velocity=80,
            confidence=0.9
        ),
        NoteEvent(
            start_time=0.5,
            end_time=1.0,
            pitch_hz=523.25,  # C5
            midi_note=72,
            velocity=90,
            confidence=0.9
        )
    ]
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as tmp_file:
        output_path = Path(tmp_file.name)
    
    try:
        # Create MIDI file
        midi_gen = MidiGenerator(tempo=120.0, program=0)
        result_path = midi_gen.create_midi(notes, output_path)
        
        # Verify the file was created
        assert result_path.exists()
        assert result_path == output_path
        
        # Load the generated MIDI file
        midi_data = pretty_midi.PrettyMIDI(str(result_path))
        
        # Verify basic properties
        assert len(midi_data.instruments) == 1
        instrument = midi_data.instruments[0]
        assert instrument.program == 0  # Acoustic Grand Piano
        
        # Verify notes
        assert len(instrument.notes) == 2
        
        # Check first note (A4)
        note1 = instrument.notes[0]
        assert note1.pitch == 69  # A4
        assert 0.49 <= note1.end - note1.start <= 0.51  # ~0.5s duration
        assert note1.velocity == 80
        
        # Check second note (C5)
        note2 = instrument.notes[1]
        assert note2.pitch == 72  # C5
        assert 0.49 <= note2.end - note2.start <= 0.51  # ~0.5s duration
        assert note2.velocity == 90
        
        # Verify tempo
        tempos = midi_data.get_tempo_changes()
        assert len(tempos) == 2  # (tempo_changes, tempo_values)
        assert 119.9 <= tempos[1][0] <= 120.1  # ~120 BPM
        
    finally:
        # Clean up
        if output_path.exists():
            os.unlink(output_path)


def test_create_midi_empty_notes():
    """Test that empty note list raises an error."""
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as tmp_file:
        output_path = Path(tmp_file.name)
    
    try:
        midi_gen = MidiGenerator()
        with pytest.raises(MidiGenerationError, match="No note events provided"):
            midi_gen.create_midi([], output_path)
    finally:
        if output_path.exists():
            os.unlink(output_path)


def test_create_midi_invalid_pitch():
    """Test that invalid MIDI pitches raise an error."""
    # Test pitch too low
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as tmp_file:
        output_path = Path(tmp_file.name)
    
    try:
        midi_gen = MidiGenerator()
        
        # Test pitch too low
        notes = [
            NoteEvent(start_time=0, end_time=0.5, pitch_hz=440, midi_note=-1, velocity=80, confidence=0.9)
        ]
        with pytest.raises(MidiGenerationError, match="Invalid MIDI note number"):
            midi_gen.create_midi(notes, output_path)
        
        # Test pitch too high
        notes[0].midi_note = 128
        with pytest.raises(MidiGenerationError, match="Invalid MIDI note number"):
            midi_gen.create_midi(notes, output_path)
    finally:
        if output_path.exists():
            os.unlink(output_path)


def test_create_midi_invalid_velocity():
    """Test that invalid velocities raise an error."""
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as tmp_file:
        output_path = Path(tmp_file.name)
    
    try:
        midi_gen = MidiGenerator()
        
        # Test velocity too low (should raise error)
        notes = [
            NoteEvent(start_time=0, end_time=0.5, pitch_hz=440, midi_note=69, velocity=0, confidence=0.9)
        ]
        with pytest.raises(MidiGenerationError, match="invalid velocity"):
            midi_gen.create_midi(notes, output_path)
        
        # Test velocity too high (should raise error)
        notes[0].velocity = 200
        with pytest.raises(MidiGenerationError, match="invalid velocity"):
            midi_gen.create_midi(notes, output_path)
        
    finally:
        if output_path.exists():
            os.unlink(output_path)


def test_get_midi_info():
    """Test getting information about note events."""
    # Create test notes
    notes = [
        NoteEvent(start_time=0.0, end_time=0.5, pitch_hz=440.0, midi_note=69, velocity=80, confidence=0.9),
        NoteEvent(start_time=0.5, end_time=1.0, pitch_hz=523.25, midi_note=72, velocity=90, confidence=0.9),
        NoteEvent(start_time=1.0, end_time=1.5, pitch_hz=659.25, midi_note=76, velocity=100, confidence=0.9)
    ]
    
    # Get MIDI info
    midi_gen = MidiGenerator()
    info = midi_gen.get_midi_info(notes)
    
    # Verify info is a dictionary with the expected keys and values
    assert isinstance(info, dict)
    assert info['note_count'] == 3
    assert info['duration'] == pytest.approx(1.5, rel=1e-6)
    assert info['pitch_range'] == (69, 76)
    assert info['average_velocity'] == pytest.approx(90)


def test_create_midi_custom_program():
    """Test MIDI creation with a custom instrument program."""
    # Create test note
    notes = [
        NoteEvent(start_time=0.0, end_time=0.5, pitch_hz=440.0, midi_note=69, velocity=80, confidence=0.9)
    ]
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as tmp_file:
        output_path = Path(tmp_file.name)
    
    try:
        # Create MIDI file with Electric Piano (program=4)
        midi_gen = MidiGenerator(program=4)
        midi_gen.create_midi(notes, output_path)
        
        # Load the MIDI file
        midi_data = pretty_midi.PrettyMIDI(str(output_path))
        
        # Verify the instrument program
        assert len(midi_data.instruments) == 1
        assert midi_data.instruments[0].program == 4  # Electric Piano
        
    finally:
        if output_path.exists():
            os.unlink(output_path)
