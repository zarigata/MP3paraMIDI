"""Tests for the AI-enabled audio to MIDI pipeline."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mp3paramidi.audio import AudioToMidiPipeline, NoteEvent
from mp3paramidi.models import SeparatedStem
from tests.helpers import create_audio_data


def _make_note(pitch: int) -> NoteEvent:
    return NoteEvent(
        start_time=0.0,
        end_time=0.5,
        pitch_hz=float(pitch) * 2.0,
        midi_note=pitch,
        velocity=90,
        confidence=0.95,
    )


class DummyDemucsWrapper:
    model_name = "dummy-demucs"

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self.loaded = False

    def ensure_model_loaded(self, progress_callback=None):
        self.loaded = True
        if progress_callback:
            progress_callback(1.0, "Demucs ready")
        return self

    def separate(self, audio_data, progress_callback=None):
        if progress_callback:
            progress_callback(0.5, "Separating")
            progress_callback(1.0, "Separation complete")
        samples = np.zeros((audio_data.metadata.sample_rate, 2), dtype=np.float32)
        return [
            SeparatedStem(name="drums", samples=samples, sample_rate=audio_data.metadata.sample_rate),
            SeparatedStem(name="other", samples=samples, sample_rate=audio_data.metadata.sample_rate),
        ]


class DummyBasicPitchWrapper:
    def __init__(self) -> None:
        self.loaded = False
        self.transcribed_stems: list[str] = []

    def ensure_model_loaded(self, progress_callback=None):
        self.loaded = True
        if progress_callback:
            progress_callback(1.0, "Basic-Pitch ready")
        return SimpleNamespace()

    def transcribe_stem(self, stem, progress_callback=None):
        self.transcribed_stems.append(stem.name)
        if progress_callback:
            progress_callback(0.5, f"{stem.name} halfway")
            progress_callback(1.0, f"{stem.name} done")
        pitch = 36 if stem.name == "drums" else 60
        return SimpleNamespace(note_events=[_make_note(pitch)])


def test_ai_pipeline_polyphonic_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    audio_data = create_audio_data(
        samples=np.ones(44100, dtype=np.float32),
        sample_rate=44100,
        file_path=tmp_path / "input.wav",
    )

    progress_events: list[tuple[str, str]] = []

    pipeline = AudioToMidiPipeline(
        use_ai_models=True,
        enable_separation=True,
        models_cache_dir=tmp_path,
        progress_callback=lambda update: progress_events.append((update.stage, update.message)),
    )

    demucs = DummyDemucsWrapper(sample_rate=audio_data.metadata.sample_rate)
    basic_pitch = DummyBasicPitchWrapper()

    def fake_initialize(self):
        self._demucs_wrapper = demucs
        self._basic_pitch_wrapper = basic_pitch
        return demucs, basic_pitch

    monkeypatch.setattr(AudioToMidiPipeline, "_initialize_ai_models", fake_initialize, raising=False)

    captured_stems: dict[str, list[NoteEvent]] = {}

    def fake_create_multi_track_midi(stems, output_path):
        captured_stems.update({name: list(notes) for name, notes in stems.items()})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"MThd")
        return output_path

    def fake_get_midi_info(stems):
        return {
            "note_count": sum(len(notes) for notes in stems.values()),
            "duration": 1.0,
        }

    pipeline.midi_generator.create_multi_track_midi = fake_create_multi_track_midi  # type: ignore[assignment]
    pipeline.midi_generator.get_midi_info = fake_get_midi_info  # type: ignore[assignment]

    output_path = tmp_path / "output.mid"
    result = pipeline.process(audio_data, output_path)

    assert result.success is True
    assert output_path.exists()
    assert result.stem_count == 2
    assert result.separation_enabled is True
    assert result.note_count == 2
    assert "drums" in captured_stems
    assert "other" in captured_stems
    assert captured_stems["drums"][0].midi_note == 36
    assert captured_stems["other"][0].midi_note == 60

    stages = [stage for stage, _ in progress_events]
    assert "model_loading" in stages
    assert ("midi_generation", "Generating multi-track MIDI (AI)...") in progress_events

    assert demucs.loaded is True
    assert basic_pitch.loaded is True
    assert set(basic_pitch.transcribed_stems) == {"drums", "other"}


def test_ai_pipeline_reports_missing_basic_pitch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import mp3paramidi.audio.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "BasicPitchWrapper", None)

    pipeline = pipeline_module.AudioToMidiPipeline(use_ai_models=True)
    audio_data = create_audio_data(
        samples=np.ones(22050, dtype=np.float32),
        sample_rate=22050,
        file_path=tmp_path / "input2.wav",
    )

    result = pipeline.process(audio_data, tmp_path / "ai.mid")

    assert result.success is False
    assert isinstance(result.error_message, str)
    assert "Basic-Pitch wrapper is unavailable" in result.error_message
