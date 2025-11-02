"""Demucs source separation wrapper for MP3paraMIDI."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional

import numpy as np

try:  # pragma: no cover - heavy dependency
    import torch
    import torchaudio
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
except ImportError as exc:  # pragma: no cover - handled in runtime
    torch = None  # type: ignore
    torchaudio = None  # type: ignore
    get_model = None  # type: ignore
    apply_model = None  # type: ignore

from ..audio.loader import AudioData, AudioMetadata
from .device_manager import DeviceManager
from .exceptions import (
    InferenceError,
    ModelDownloadError,
    ModelLoadError,
    ModelError,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


@dataclass(slots=True)
class SeparatedStem:
    """Container representing a separated audio stem from Demucs."""

    name: str
    samples: np.ndarray
    sample_rate: int
    confidence: Optional[float] = None

    metadata: AudioMetadata = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.metadata = AudioMetadata(
            duration=self.samples.shape[0] / self.sample_rate,
            sample_rate=self.sample_rate,
            channels=self.samples.shape[1] if self.samples.ndim == 2 else 1,
            format="STEM",
        )


class DemucsWrapper:
    """High-level interface around Demucs for source separation.

    Args:
        model_name: Name of the Demucs model to load.
        device: Optional computation device override (e.g., "cuda" or torch.device).
        cache_dir: Directory to store downloaded Demucs weights.
        segment_duration: Duration of audio segments processed per batch (seconds).
        overlap: Overlap ratio applied between consecutive segments.
        shifts: Number of random shifts for test-time augmentation.
    """

    def __init__(
        self,
        model_name: str = "htdemucs",
        device: Optional["torch.device | str"] = None,
        cache_dir: Optional[Path] = None,
        segment_duration: float = 7.8,
        overlap: float = 0.25,
        shifts: int = 1,
    ) -> None:
        self.model_name = model_name
        if segment_duration <= 0:
            raise ValueError("segment_duration must be greater than zero")

        self.segment_duration = segment_duration
        self.overlap = overlap
        self.shifts = shifts

        if torch is None or torchaudio is None or get_model is None:
            raise ModelLoadError(
                model_name=model_name,
                message="Demucs dependencies are not installed.",
                details=(
                    "Install the optional AI dependencies (torch, torchaudio, demucs) "
                    "to enable source separation."
                ),
            )

        self.cache_dir = cache_dir or Path(__file__).resolve().parents[3] / "models"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if "DEMUCS_PATH" not in os.environ:
            os.environ["DEMUCS_PATH"] = str(self.cache_dir)
            logger.info("Configured DEMUCS_PATH to %s", os.environ["DEMUCS_PATH"])

        if isinstance(device, str) and torch is not None:
            device = torch.device(device)

        self._device = device or DeviceManager.detect_device()
        self._model: Optional[torch.nn.Module] = None

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return

        try:
            logger.info("Loading Demucs model '%s' from cache %s", self.model_name, self.cache_dir)
            model = get_model(name=self.model_name)
        except Exception as exc:
            raise ModelDownloadError(
                model_name=self.model_name,
                message="Failed to download Demucs model weights.",
                details=str(exc),
            ) from exc

        try:
            self._model = model.to(self._device)
            self._model.eval()
            logger.info(
                "Demucs model ready on %s with stems: %s",
                self._device,
                ", ".join(self._model.sources),
            )
        except Exception as exc:  # pragma: no cover - hardware dependent
            raise ModelLoadError(
                model_name=self.model_name,
                message="Failed to move Demucs model to target device.",
                details=str(exc),
            ) from exc

    def _report_progress(self, callback: Optional[ProgressCallback], value: float, message: str) -> None:
        if callback:
            try:
                callback(max(0.0, min(1.0, value)), message)
            except Exception:  # pragma: no cover - guard user callbacks
                logger.debug("Progress callback raised an exception", exc_info=True)

    def ensure_model_loaded(self, progress_callback: Optional[ProgressCallback] = None) -> "torch.nn.Module":
        """Public accessor that ensures the Demucs model weights are ready."""

        if self._model is not None:
            self._report_progress(progress_callback, 1.0, "Demucs model ready")
            return self._model

        self._report_progress(progress_callback, 0.0, "Loading Demucs model")
        self._ensure_model_loaded()
        self._report_progress(progress_callback, 1.0, "Demucs model ready")
        assert self._model is not None
        return self._model

    def get_stem_names(self) -> List[str]:
        self._ensure_model_loaded()
        assert self._model is not None
        return list(self._model.sources)

    @staticmethod
    def get_available_models() -> List[str]:
        return ["htdemucs", "htdemucs_ft", "htdemucs_6s", "hdemucs_mmi"]

    def _preprocess_audio(self, audio_data: AudioData) -> "torch.Tensor":
        samples = audio_data.samples
        if samples.ndim == 1:
            samples = np.stack([samples, samples], axis=1)
        elif samples.shape[1] == 1:
            samples = np.repeat(samples, 2, axis=1)

        tensor = torch.from_numpy(samples.T.astype(np.float32))

        sample_rate = audio_data.metadata.sample_rate
        if sample_rate != 44100:
            tensor = torchaudio.functional.resample(tensor, sample_rate, 44100)

        return tensor

    def separate(
        self,
        audio_data: AudioData,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[SeparatedStem]:
        self._ensure_model_loaded()
        assert self._model is not None

        self._report_progress(progress_callback, 0.0, "Preparing audio for separation")

        try:
            mix = self._preprocess_audio(audio_data)
            mix = mix.to(self._device)
            mix_batch = mix.unsqueeze(0)
        except Exception as exc:
            raise ModelError(
                model_name=self.model_name,
                message="Failed to preprocess audio before separation.",
                details=str(exc),
            ) from exc

        try:
            with torch.no_grad():
                estimates = apply_model(
                    self._model,
                    mix_batch,
                    overlap=self.overlap,
                    shifts=self.shifts,
                    segment=self.segment_duration,
                    device=self._device,
                )
        except Exception as exc:
            raise InferenceError(
                model_name=self.model_name,
                message="Demucs inference failed.",
                details=str(exc),
            ) from exc

        # Handle different return types from apply_model
        if isinstance(estimates, (list, tuple)):  # If it's a sequence of tensors (e.g., from overlapping segments)
            if not estimates:
                raise InferenceError(
                    model_name=self.model_name,
                    message="Empty output from Demucs model",
                    details="The model returned an empty sequence of estimates.",
                )
            
            # Stack all segments along the batch dimension
            estimates = torch.cat(estimates, dim=0)
            
            # If we have multiple segments, average them (this is a simple approach;
            # for better quality, consider using overlap-add with proper windowing)
            if len(estimates) > 1:
                estimates = estimates.mean(dim=0, keepdim=True)
        
        if not isinstance(estimates, torch.Tensor):
            raise InferenceError(
                model_name=self.model_name,
                message=f"Unexpected output type from Demucs: {type(estimates).__name__}",
                details="Expected a PyTorch tensor or sequence of tensors.",
            )
            
        # Ensure the tensor has the expected shape: (batch=1, n_sources, channels, samples)
        if estimates.dim() == 3:  # (batch, n_sources, samples) - missing channels
            estimates = estimates.unsqueeze(2)  # Add channel dimension
        elif estimates.dim() != 4:
            raise InferenceError(
                model_name=self.model_name,
                message=f"Unexpected tensor shape from Demucs: {tuple(estimates.shape)}",
                details=f"Expected 3 or 4 dimensions, got {estimates.dim()}",
            )
            
        # Ensure we have the expected shape: (batch=1, n_sources, channels, samples)
        if estimates.shape[0] != 1:
            logger.warning(
                "Unexpected batch size %d in Demucs output, taking first item",
                estimates.shape[0]
            )
            estimates = estimates[:1]  # Take first batch item if multiple
            
        # Convert to numpy and ensure we have the right shape (sources, channels, samples)
        estimates = estimates.squeeze(0).cpu().numpy()
        stems: List[SeparatedStem] = []
        stem_names = self._model.sources

        for index, stem_name in enumerate(stem_names):
            self._report_progress(
                progress_callback,
                0.2 + (0.6 * (index + 1) / len(stem_names)),
                f"Processing {stem_name} stem",
            )
            stem_audio = estimates[index]
            stem_audio = np.moveaxis(stem_audio, 0, 1)
            stems.append(
                SeparatedStem(
                    name=stem_name,
                    samples=stem_audio.astype(np.float32),
                    sample_rate=44100,
                    confidence=None,
                )
            )

        self._report_progress(progress_callback, 1.0, "Source separation complete")
        return stems


__all__ = ["DemucsWrapper", "SeparatedStem"]
