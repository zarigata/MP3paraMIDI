"""Tests for the audio separation module.

TODO: Implement comprehensive tests after verifying the module works with real
audio files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest
import torch
import torchaudio

from src import audio_separation


@pytest.fixture()
def sample_audio_file(tmp_path: Path) -> Path:
    """Create a simple stereo sine wave WAV file for testing purposes."""

    sample_rate = 44100
    duration_seconds = 1
    t = torch.linspace(0, duration_seconds, int(sample_rate * duration_seconds), dtype=torch.float32)
    frequency = 440.0
    waveform = torch.stack([torch.sin(2 * torch.pi * frequency * t)] * 2)

    output_file = tmp_path / "test_tone.wav"
    torchaudio.save(str(output_file), waveform, sample_rate)
    return output_file


def test_validate_input_file_valid(sample_audio_file: Path) -> None:
    """Ensure validation passes for a supported audio file."""

    result = audio_separation._validate_input_file(sample_audio_file)
    assert result == sample_audio_file.resolve()


def test_validate_input_file_invalid_format(tmp_path: Path) -> None:
    """Unsupported file extensions should raise ValueError."""

    invalid_file = tmp_path / "audio.txt"
    invalid_file.write_text("invalid")

    with pytest.raises(ValueError):
        audio_separation._validate_input_file(invalid_file)


def test_validate_input_file_not_exists(tmp_path: Path) -> None:
    """Non-existent files should raise ValueError."""

    missing_file = tmp_path / "missing.wav"

    with pytest.raises(ValueError):
        audio_separation._validate_input_file(missing_file)


def test_get_device() -> None:
    """Device detection should return either cuda or cpu."""

    device = audio_separation._get_device()
    assert device in {"cuda", "cpu"}


def test_separate_audio_invalid_model(sample_audio_file: Path, tmp_path: Path) -> None:
    """Invalid model names should raise RuntimeError."""

    with pytest.raises(RuntimeError):
        audio_separation.separate_audio(
            input_path=str(sample_audio_file),
            output_dir=str(tmp_path),
            model_name="invalid_model",
        )


def test_get_available_models() -> None:
    """Ensure available models list is not empty and contains expected entries."""

    models = audio_separation.get_available_models()
    assert "htdemucs" in models
    assert isinstance(models, list)


@pytest.mark.skip(reason="Requires Demucs model download and longer runtime.")
def test_separate_audio_success(sample_audio_file: Path, tmp_path: Path) -> None:
    """Integration test for successful audio separation using Demucs."""

    results: Dict[str, str] = audio_separation.separate_audio(
        input_path=str(sample_audio_file),
        output_dir=str(tmp_path),
    )

    assert set(results.keys()) >= set(audio_separation.STEM_NAMES)
    for stem_path in results.values():
        assert Path(stem_path).exists()
        info = torchaudio.info(stem_path)
        assert info.num_channels > 0
        assert info.sample_rate > 0
