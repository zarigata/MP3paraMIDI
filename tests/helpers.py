"""Test helper utilities for MP3paraMIDI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from mp3paramidi.audio import AudioData, AudioMetadata


def create_audio_data(
    samples: np.ndarray,
    sample_rate: int,
    file_path: Optional[Path] = None,
) -> AudioData:
    """Build an AudioData instance for synthetic audio arrays used in tests."""
    file_path = Path(file_path) if file_path is not None else Path("synthetic.wav")

    # Ensure float32 samples for downstream processing
    samples = np.asarray(samples, dtype=np.float32)

    samples, channels = _normalize_samples(samples)

    duration = len(samples) / float(sample_rate)
    metadata = AudioMetadata(
        duration=duration,
        sample_rate=sample_rate,
        channels=channels,
    )

    # Align with pipeline expectations that metadata exposes file_path
    metadata.file_path = file_path  # type: ignore[attr-defined]

    return AudioData(
        file_path=file_path,
        samples=samples,
        metadata=metadata,
    )


def _normalize_samples(samples: np.ndarray) -> Tuple[np.ndarray, int]:
    """Ensure samples are in (n_samples,) or (n_samples, channels) format."""
    if samples.ndim == 1:
        return samples, 1

    if samples.ndim != 2:
        raise ValueError("Samples must be 1D or 2D arrays")

    rows, cols = samples.shape
    if cols in (1, 2):
        return samples.reshape(-1, cols), cols
    if rows in (1, 2):
        transposed = samples.T
        return transposed.reshape(-1, transposed.shape[1]), transposed.shape[1]

    raise ValueError("2D samples must have 1 or 2 channels")
