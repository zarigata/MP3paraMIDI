"""Custom exceptions for AI model operations within MP3paraMIDI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ModelError(Exception):
    """Base exception raised for AI model related failures.

    Attributes:
        model_name: Identifier of the model involved in the failure.
        message: Human-friendly description of the error.
        details: Optional extra context that may include the original exception message
            or remediation hints.
    """

    model_name: str
    message: str
    details: Optional[str] = None

    def __str__(self) -> str:
        base = f"{self.model_name}: {self.message}"
        return f"{base} ({self.details})" if self.details else base


class ModelDownloadError(ModelError):
    """Raised when a model fails to download or cache correctly.

    Typical causes include missing internet connectivity, insufficient
    disk space in the cache directory, or authentication failures when
    retrieving the model weights.
    """


class ModelLoadError(ModelError):
    """Raised when a cached model cannot be loaded into memory.

    This may indicate version mismatches, corrupted weight files, or
    incompatible hardware backends for the stored checkpoints.
    """


class InferenceError(ModelError):
    """Raised when inference fails while executing a model.

    Wraps runtime exceptions that occur during forward passes including
    shape mismatches, numerical instability, or device-specific issues.
    """


class UnsupportedDeviceError(ModelError):
    """Raised when GPU/CUDA resources are unavailable or unsupported.

    Used to provide clearer feedback when the requested accelerator is
    not accessible (e.g., CUDA requested but not installed) and to
    suggest falling back to CPU execution.
    """
