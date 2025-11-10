"""Placeholder tests for the audio_to_midi module.

TODO: Implement comprehensive tests. Some tests may require mocking Basic Pitch
and Melodia APIs to avoid dependencies on model downloads during CI/CD.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pretty_midi
import pytest
import torch
import torchaudio

from src import audio_to_midi


def has_melodia_plugin() -> bool:
    """Return whether the Melodia Vamp plugin is available for testing."""

    try:
        from audio2midi import Melodia  # type: ignore
    except Exception:
        return False
    return True


@pytest.fixture()
def sample_wav_file(tmp_path: Path) -> Path:
    """Create a simple mono sine wave WAV file for validation tests."""

    sample_rate = 44100
    duration_seconds = 1
    t = torch.linspace(0, duration_seconds, int(sample_rate * duration_seconds), dtype=torch.float32)
    frequency = 440.0
    waveform = torch.sin(2 * torch.pi * frequency * t).unsqueeze(0)

    output_file = tmp_path / "test_tone.wav"
    torchaudio.save(str(output_file), waveform, sample_rate)
    return output_file


@pytest.fixture()
def sample_midi_files(tmp_path: Path) -> List[Path]:
    """Generate simple MIDI files with different instruments for combination tests."""

    midi_paths: List[Path] = []
    for program, name in [(0, "piano"), (24, "guitar"), (33, "bass")]:
        midi = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=program, name=f"{name.title()} Track")
        note = pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5)
        instrument.notes.append(note)
        midi.instruments.append(instrument)

        file_path = tmp_path / f"{name}.mid"
        midi.write(str(file_path))
        midi_paths.append(file_path)
    return midi_paths


def test_validate_audio_file_valid(sample_wav_file: Path) -> None:
    """Ensure validation passes for a supported audio file."""

    result = audio_to_midi._validate_audio_file(sample_wav_file)
    assert result == sample_wav_file.resolve()


def test_validate_audio_file_invalid_format(tmp_path: Path) -> None:
    """Unsupported file extensions should raise ValueError."""

    invalid_file = tmp_path / "audio.txt"
    invalid_file.write_text("invalid")

    with pytest.raises(ValueError):
        audio_to_midi._validate_audio_file(invalid_file)


def test_validate_audio_file_not_exists(tmp_path: Path) -> None:
    """Non-existent files should raise ValueError."""

    missing_file = tmp_path / "missing.wav"

    with pytest.raises(ValueError):
        audio_to_midi._validate_audio_file(missing_file)


def test_assign_instrument_program_piano() -> None:
    """Piano stems should receive program 0."""

    instrument = pretty_midi.Instrument(program=5)
    audio_to_midi._assign_instrument_program(instrument, "piano")
    assert instrument.program == 0
    assert instrument.is_drum is False


def test_assign_instrument_program_guitar() -> None:
    """Guitar stems should receive program 24."""

    instrument = pretty_midi.Instrument(program=5)
    audio_to_midi._assign_instrument_program(instrument, "guitar")
    assert instrument.program == 24


def test_assign_instrument_program_bass() -> None:
    """Bass stems should receive program 33."""

    instrument = pretty_midi.Instrument(program=5)
    audio_to_midi._assign_instrument_program(instrument, "bass")
    assert instrument.program == 33


def test_assign_instrument_program_drums() -> None:
    """Drum stems should toggle the drum flag."""

    instrument = pretty_midi.Instrument(program=5)
    audio_to_midi._assign_instrument_program(instrument, "drums")
    assert instrument.is_drum is True


@pytest.mark.slow
def test_convert_with_basic_pitch_success(monkeypatch: pytest.MonkeyPatch, sample_wav_file: Path, tmp_path: Path) -> None:
    """Basic Pitch conversion should return MIDI data with assigned instruments."""

    def fake_predict_and_save(
        input_audio_path: str,
        output_directory: str,
        save_midi: bool = True,
        save_model_outputs: bool = False,
        save_notes: bool = False,
    ) -> None:  # pragma: no cover - stub
        assert input_audio_path == str(sample_wav_file)
        assert save_midi is True
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=1)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0, end=1))
        midi.instruments.append(inst)
        midi.write(str(Path(output_directory) / "fake_basic_pitch.mid"))

    monkeypatch.setattr(audio_to_midi, "basic_pitch_predict_and_save", fake_predict_and_save)

    midi = audio_to_midi._convert_with_basic_pitch(sample_wav_file, "piano")
    assert midi.instruments
    assert midi.instruments[0].program == 0


@pytest.mark.slow
@pytest.mark.skipif(not has_melodia_plugin(), reason="Melodia Vamp plugin not available")
def test_convert_with_melodia_success(monkeypatch: pytest.MonkeyPatch, sample_wav_file: Path) -> None:
    """Melodia conversion should return MIDI data with assigned instruments."""

    class DummyMelodia:  # pragma: no cover - simple stub
        def predict(self, path: str) -> pretty_midi.PrettyMIDI:
            assert path == str(sample_wav_file)
            midi = pretty_midi.PrettyMIDI()
            inst = pretty_midi.Instrument(program=1)
            inst.notes.append(pretty_midi.Note(velocity=100, pitch=64, start=0, end=1))
            midi.instruments.append(inst)
            return midi

    monkeypatch.setitem(sys.modules, "audio2midi", type("mod", (), {"Melodia": DummyMelodia}))

    midi = audio_to_midi._convert_with_melodia(sample_wav_file, "vocals")
    assert midi.instruments
    assert midi.instruments[0].program == 0


def test_convert_stem_to_midi_output_file_created(monkeypatch: pytest.MonkeyPatch, sample_wav_file: Path, tmp_path: Path) -> None:
    """Conversion should create a MIDI file on disk."""

    def fake_convert(audio_path: Path, stem: str) -> pretty_midi.PrettyMIDI:  # pragma: no cover - stub
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=90, pitch=60, start=0, end=1))
        midi.instruments.append(inst)
        return midi

    monkeypatch.setattr(audio_to_midi, "_convert_with_basic_pitch", fake_convert)

    output = audio_to_midi.convert_stem_to_midi(str(sample_wav_file), "piano", str(tmp_path))
    assert Path(output).exists()


def test_convert_stem_to_midi_handles_name_collision(monkeypatch: pytest.MonkeyPatch, sample_wav_file: Path, tmp_path: Path) -> None:
    """Existing filenames should force deterministic suffixes."""

    def fake_convert(audio_path: Path, stem: str) -> pretty_midi.PrettyMIDI:  # pragma: no cover - stub
        midi = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        instrument.notes.append(pretty_midi.Note(velocity=90, pitch=60, start=0, end=1))
        midi.instruments.append(instrument)
        return midi

    monkeypatch.setattr(audio_to_midi, "_convert_with_basic_pitch", fake_convert)

    first_output = audio_to_midi.convert_stem_to_midi(str(sample_wav_file), "piano", str(tmp_path))
    duplicate_path = Path(first_output)
    # Pre-create the same filename to force a collision on the next call.
    duplicate_path.write_bytes(duplicate_path.read_bytes())

    second_output = audio_to_midi.convert_stem_to_midi(str(sample_wav_file), "piano", str(tmp_path))
    assert second_output != first_output
    assert Path(second_output).exists()


def test_combine_midi_files_success(sample_midi_files: List[Path], tmp_path: Path) -> None:
    """Combining MIDI files should preserve track count."""

    output = tmp_path / "combined.mid"
    result = audio_to_midi.combine_midi_files([str(p) for p in sample_midi_files], str(output))
    combined = pretty_midi.PrettyMIDI(result)
    assert len(combined.instruments) == len(sample_midi_files)


def test_combine_midi_files_rejects_invalid_paths(tmp_path: Path) -> None:
    """Invalid MIDI inputs should raise ValueError before processing."""

    fake_midi = tmp_path / "track.mid"
    fake_midi.write_bytes(b"not_a_midi")

    with pytest.raises(ValueError) as excinfo:
        audio_to_midi.combine_midi_files([str(fake_midi), str(tmp_path / "missing.mid")], str(tmp_path / "combined.mid"))

    assert "Invalid MIDI paths" in str(excinfo.value)


def test_combine_midi_files_empty_list(tmp_path: Path) -> None:
    """Empty MIDI list should raise ValueError."""

    with pytest.raises(ValueError):
        audio_to_midi.combine_midi_files([], str(tmp_path / "combined.mid"))


def test_convert_stems_to_combined_midi_cleanup(monkeypatch: pytest.MonkeyPatch, sample_wav_file: Path, tmp_path: Path) -> None:
    """Temporary directory should be cleaned even when conversion fails."""

    def fake_convert(*args, **kwargs):  # pragma: no cover - stub
        raise RuntimeError("conversion failed")

    monkeypatch.setattr(audio_to_midi, "convert_stem_to_midi", fake_convert)

    with pytest.raises(RuntimeError):
        audio_to_midi.convert_stems_to_combined_midi({"piano": str(sample_wav_file)}, str(tmp_path / "out.mid"))


def test_get_supported_stem_types() -> None:
    """Ensure supported stem types are exposed."""

    stems = audio_to_midi.get_supported_stem_types()
    assert set(stems) == {"piano", "guitar", "bass", "drums", "vocals", "other"}
