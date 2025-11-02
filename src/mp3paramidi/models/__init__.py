"""AI model wrappers for MP3paraMIDI including Demucs (source separation) and Basic-Pitch (polyphonic transcription)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Deferred imports to avoid circular dependencies during package initialization.
try:  # pragma: no cover - conditional to allow partial installations
    from .basic_pitch_wrapper import BasicPitchWrapper
except ImportError:  # pragma: no cover - placeholder until module is implemented
    BasicPitchWrapper = None  # type: ignore

try:  # pragma: no cover
    from .demucs_wrapper import DemucsWrapper, SeparatedStem
except ImportError:  # pragma: no cover
    DemucsWrapper = None  # type: ignore
    SeparatedStem = None  # type: ignore

from .exceptions import ModelError, ModelLoadError


if BasicPitchWrapper is None:  # pragma: no cover - executed when optional deps missing
    class BasicPitchWrapper:  # type: ignore[no-redef]
        """Placeholder Basic-Pitch wrapper that surfaces missing dependency errors."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ModelLoadError(
                model_name="basic_pitch",
                message="Basic-Pitch dependencies are not installed.",
                details=(
                    "Install the optional AI dependencies (basic-pitch, pretty_midi, torch) "
                    "to enable polyphonic transcription."
                ),
            )

        @staticmethod
        def get_default_config() -> dict[str, dict[str, float]]:
            return {
                "balanced": {"onset_threshold": 0.5, "frame_threshold": 0.3},
                "sensitive": {"onset_threshold": 0.45, "frame_threshold": 0.25},
                "conservative": {"onset_threshold": 0.55, "frame_threshold": 0.35},
            }


if DemucsWrapper is None:  # pragma: no cover - executed when optional deps missing
    from ..audio.loader import AudioMetadata

    @dataclass(slots=True)
    class SeparatedStem:  # type: ignore[no-redef]
        """Lightweight stand-in for Demucs stems when the model is unavailable."""

        name: str
        samples: Any
        sample_rate: int
        confidence: Optional[float] = None
        metadata: AudioMetadata = field(init=False, repr=False)

        def __post_init__(self) -> None:
            sample_count = getattr(self.samples, "shape", (len(self.samples),))[0] if self.samples is not None else 0
            channels = 1
            if hasattr(self.samples, "ndim") and getattr(self.samples, "ndim") == 2:
                channels = getattr(self.samples, "shape", (0, 1))[1]
            self.metadata = AudioMetadata(
                duration=float(sample_count) / self.sample_rate if self.sample_rate else 0.0,
                sample_rate=self.sample_rate,
                channels=channels,
                format="STEM",
            )

    class DemucsWrapper:  # type: ignore[no-redef]
        """Placeholder Demucs wrapper that surfaces missing dependency errors."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ModelLoadError(
                model_name=kwargs.get("model_name", "demucs"),
                message="Demucs dependencies are not installed.",
                details=(
                    "Install the optional AI dependencies (torch, torchaudio, demucs) "
                    "to enable source separation."
                ),
            )


@dataclass(slots=True)
class ModelConfig:
    """Metadata describing an AI model used within MP3paraMIDI.

    Attributes:
        name: Identifier of the model (e.g., ``"htdemucs"``).
        version: Optional semantic version or commit hash information when available.
        description: Human-friendly summary of the model's purpose or characteristics.
    """

    name: str
    version: Optional[str] = None
    description: Optional[str] = None


__all__ = [
    "BasicPitchWrapper",
    "DemucsWrapper",
    "ModelConfig",
    "ModelError",
    "SeparatedStem",
]
