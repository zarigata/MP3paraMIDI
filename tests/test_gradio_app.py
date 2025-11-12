"""Test scaffolding for the Gradio interface module.

The tests focus on ensuring the Blocks interface can be constructed and that the
processing helpers handle happy-path and error conditions. Heavy operations such
as Demucs inference and MIDI conversion are mocked out to keep the suite fast.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterator

import pytest
import torch
import torchaudio

from src import gradio_app
from src.gradio_app import (
    STEM_ORDER,
    _create_temp_output_dir,
    _format_file_size,
    create_gradio_interface,
    process_full_workflow,
    process_midi_conversion,
    process_separation,
)

pytestmark = pytest.mark.gradio


@pytest.fixture(scope="module")
def sample_audio_file(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Create a minimal sine wave WAV file for tests that require a filepath."""

    tmp_dir = tmp_path_factory.mktemp("audio")
    audio_path = tmp_dir / "tone.wav"

    sample_rate = 16000
    duration_seconds = 0.25
    t = torch.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
    waveform = torch.sin(2 * math.pi * 440 * t).unsqueeze(0)

    torchaudio.save(str(audio_path), waveform, sample_rate)
    yield str(audio_path)

    if audio_path.exists():  # Cleanup
        audio_path.unlink()


@pytest.fixture
def gradio_interface():
    """Return a freshly constructed Gradio Blocks interface."""

    return create_gradio_interface()


def test_create_gradio_interface_returns_blocks(gradio_interface):
    import gradio as gr

    assert isinstance(gradio_interface, gr.Blocks)


def test_gradio_interface_has_tabs(gradio_interface):
    config = gradio_interface.get_config_file()
    tab_labels = {
        component["props"].get("label")
        for component in config["components"].values()
        if component.get("type") == "tabitem"
    }

    expected_labels = {"🎚️ Separate Audio", "🎼 Convert to MIDI", "⚡ Quick Workflow"}
    assert expected_labels.issubset(tab_labels)


def test_process_separation_with_valid_audio(sample_audio_file, mocker):
    mock_stem_paths: Dict[str, str] = {
        stem: str(Path(sample_audio_file).with_name(f"{stem}.wav"))
        for stem in STEM_ORDER
    }
    mocker.patch("src.gradio_app.separate_audio", return_value=mock_stem_paths)

    status, dataset_rows, job_id, stem_paths_json, summary = process_separation(
        sample_audio_file, "htdemucs"
    )

    assert "successfully" in status.lower()
    assert dataset_rows
    assert all(len(row) == 3 for row in dataset_rows)
    assert all(row[0] for row in dataset_rows)
    assert job_id
    assert json.loads(stem_paths_json) == mock_stem_paths
    assert summary.startswith(gradio_app.SUMMARY_HEADER)


def test_process_separation_with_missing_audio():
    status, dataset_rows, job_id, stem_paths_json, summary = process_separation(
        None, "htdemucs"
    )
    assert "please upload" in status.lower()
    assert dataset_rows == []
    assert job_id == ""
    assert stem_paths_json == "{}"
    assert summary == ""


def test_process_separation_handles_value_error(sample_audio_file, mocker):
    mocker.patch("src.gradio_app.separate_audio", side_effect=ValueError("bad model"))
    status, dataset_rows, job_id, stem_paths_json, summary = process_separation(
        sample_audio_file, "invalid"
    )
    assert "input error" in status.lower()
    assert dataset_rows == []
    assert job_id == ""
    assert stem_paths_json == "{}"
    assert summary == ""


def test_process_midi_conversion_with_valid_data(tmp_path, mocker):
    job_dir = tmp_path / "gradio_mp3midi_job123"
    job_dir.mkdir()
    mocker.patch("src.gradio_app._resolve_job_directory", return_value=job_dir)

    midi_path = job_dir / "midi" / "combined.mid"
    mocker.patch(
        "src.gradio_app.convert_stems_to_combined_midi",
        return_value=str(midi_path),
    )

    stem_paths = {stem: f"/tmp/{stem}.wav" for stem in STEM_ORDER}
    status, midi_file = process_midi_conversion("job123", json.dumps(stem_paths))

    assert "successfully" in status.lower()
    assert midi_file == str(midi_path)


def test_process_midi_conversion_without_job_id():
    status, midi_file = process_midi_conversion("", json.dumps({}))
    assert "missing job" in status.lower()
    assert midi_file is None


def test_process_full_workflow_success(sample_audio_file, mocker):
    separation_result = (
        "Audio separated successfully.",
        [["drums.wav", "drums", ""], ["bass.wav", "bass", ""]],
        "job999",
        json.dumps({stem: f"/tmp/{stem}.wav" for stem in STEM_ORDER}),
        "summary",
    )
    midi_result = ("MIDI conversion completed successfully.", "combined.mid")

    mocker.patch("src.gradio_app.process_separation", return_value=separation_result)
    mocker.patch("src.gradio_app.process_midi_conversion", return_value=midi_result)

    status, stem_entries, midi_file, summary = process_full_workflow(sample_audio_file, "htdemucs")

    assert "audio separated" in status.lower()
    assert midi_file == "combined.mid"
    assert isinstance(stem_entries, list)
    assert {entry["stem"] for entry in stem_entries} == set(STEM_ORDER)
    assert all("path" in entry for entry in stem_entries)
    assert summary == "summary"


@pytest.mark.parametrize(
    "num_bytes, expected",
    [
        (0, "0.00 B"),
        (1023, "1023.00 B"),
        (1024, "1.00 KB"),
        (1024 * 1024, "1.00 MB"),
    ],
)
def test_format_file_size(num_bytes, expected):
    assert _format_file_size(num_bytes) == expected


def test_create_temp_output_dir_creates_directory():
    temp_dir = _create_temp_output_dir()
    assert temp_dir.exists()
    assert temp_dir.is_dir()
    # Cleanup
    if temp_dir.exists():
        for child in temp_dir.iterdir():
            child.unlink()
        temp_dir.rmdir()


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skip(reason="Heavy model inference to be implemented with dedicated mocks.")
def test_process_separation_integration(sample_audio_file):
    """Placeholder for an end-to-end separation test using real models."""

    process_separation(sample_audio_file, "htdemucs")
