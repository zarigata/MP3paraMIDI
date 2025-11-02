"""Tests for the BasicPitchWrapper abstraction."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from mp3paramidi.models.exceptions import ModelLoadError
from tests.helpers import create_audio_data


@pytest.fixture
def basic_pitch_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Provide a patched BasicPitchWrapper module with lightweight dependencies."""
    import mp3paramidi.models.basic_pitch_wrapper as module

    counters = {"instances": 0, "loads": 0, "predict_calls": 0}

    class FakeModel:
        def __init__(self, load_path: str | None) -> None:
            counters["instances"] += 1
            self.load_path = load_path

        def load_model(self) -> None:
            counters["loads"] += 1

    def fake_predict(**kwargs):  # type: ignore[no-untyped-def]
        counters["predict_calls"] += 1
        # basic-pitch predict returns (model_output, midi_data, note_events)
        model_output = {"note": np.array([0.9], dtype=np.float32)}
        midi_data = SimpleNamespace()
        note_events = [(0.0, 0.5, 60, 0.9)]
        return model_output, midi_data, note_events

    monkeypatch.setattr(module, "Model", FakeModel, raising=False)
    monkeypatch.setattr(module, "predict", fake_predict, raising=False)
    monkeypatch.setattr(
        module,
        "pretty_midi",
        SimpleNamespace(note_number_to_hz=lambda midi: float(midi) * 2.0),
        raising=False,
    )

    yield SimpleNamespace(module=module, counters=counters, cache_dir=tmp_path)


def _build_stem_from_audio(audio_data):
    return SimpleNamespace(
        name="stem",
        samples=audio_data.samples,
        metadata=audio_data.metadata,
    )


def test_basic_pitch_lazy_loading(basic_pitch_env) -> None:
    module = basic_pitch_env.module
    counters = basic_pitch_env.counters

    wrapper = module.BasicPitchWrapper(cache_dir=basic_pitch_env.cache_dir)

    wrapper.ensure_model_loaded()
    wrapper.ensure_model_loaded()  # Should reuse cached model

    assert counters["instances"] == 1
    assert counters["loads"] == 1


def test_basic_pitch_transcription_flow(basic_pitch_env) -> None:
    module = basic_pitch_env.module
    counters = basic_pitch_env.counters

    wrapper = module.BasicPitchWrapper(cache_dir=basic_pitch_env.cache_dir)

    audio_data = create_audio_data(
        samples=np.ones(4410, dtype=np.float32),
        sample_rate=44100,
    )

    progress_updates: list[tuple[float, str]] = []

    result = wrapper.transcribe(
        audio_data,
        progress_callback=lambda value, message: progress_updates.append((value, message)),
    )

    assert len(result.note_events) == 1
    assert result.note_events[0].midi_note == 60
    assert counters["predict_calls"] == 1
    assert progress_updates[0][0] == 0.0
    assert progress_updates[-1][0] == 1.0

    stem_result = wrapper.transcribe_stem(_build_stem_from_audio(audio_data))
    assert len(stem_result.note_events) == 1


def test_basic_pitch_missing_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    import mp3paramidi.models.basic_pitch_wrapper as module

    monkeypatch.setattr(module, "Model", None, raising=False)
    monkeypatch.setattr(module, "predict", None, raising=False)
    monkeypatch.setattr(module, "pretty_midi", None, raising=False)

    with pytest.raises(ModelLoadError):
        module.BasicPitchWrapper()
