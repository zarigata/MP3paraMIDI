"""Tests for multi-track MIDI generation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi
import pytest

from mp3paramidi.audio import NoteEvent
from mp3paramidi.midi.generator import (
    MidiGenerationError,
    MidiGenerator,
)


def _make_note(pitch: int) -> NoteEvent:
    return NoteEvent(
        start_time=0.0,
        end_time=0.5,
        pitch_hz=float(pitch) * 2.0,
        midi_note=pitch,
        velocity=90,
        confidence=0.9,
    )


def test_multi_track_midi_creates_separate_instruments(tmp_path: Path) -> None:
    generator = MidiGenerator()
    stems = {
        "drums": [_make_note(36)],
        "piano": [_make_note(60)],
    }

    output_path = tmp_path / "multitrack.mid"
    generator.create_multi_track_midi(stems, output_path)

    midi = pretty_midi.PrettyMIDI(str(output_path))
    instruments = {instrument.name: instrument for instrument in midi.instruments}

    assert instruments["drums"].is_drum is True
    assert instruments["drums"].program == 0
    assert instruments["piano"].is_drum is False
    assert instruments["piano"].program == 0


def test_multi_track_midi_skips_empty_stems(tmp_path: Path) -> None:
    generator = MidiGenerator()
    stems = {
        "drums": [_make_note(36)],
        "bass": [],
    }

    output_path = tmp_path / "skip.mid"
    generator.create_multi_track_midi(stems, output_path)

    midi = pretty_midi.PrettyMIDI(str(output_path))
    names = {instrument.name for instrument in midi.instruments}
    assert names == {"drums"}


def test_multi_track_midi_requires_notes() -> None:
    generator = MidiGenerator()
    with pytest.raises(MidiGenerationError):
        generator.create_multi_track_midi({}, Path("unused.mid"))
