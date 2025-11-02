"""Utilities for selecting the optimal computation device for AI models."""

from __future__ import annotations

import logging
from typing import Dict, Optional

try:  # pragma: no cover - import guarded for environments without torch
    import torch
except ImportError:  # pragma: no cover - handled gracefully at runtime
    torch = None  # type: ignore

from .exceptions import UnsupportedDeviceError

logger = logging.getLogger(__name__)

_GPU_STAGE_MEMORY_GB = {
    "demucs": 4.0,
    "basic_pitch": 2.0,
}


class DeviceManager:
    """Utility helpers for selecting GPU/CPU backends for AI inference.

    The manager prefers CUDA-enabled GPUs when available and falls back to CPU
    execution when necessary. It also surfaces diagnostic information that can
    be displayed in the GUI to help users understand performance expectations.
    """

    @staticmethod
    def _ensure_torch_available() -> None:
        if torch is None:
            raise UnsupportedDeviceError(
                model_name="DeviceManager",
                message="PyTorch is required for AI features but is not installed.",
                details=(
                    "Install the optional AI dependencies using 'pip install "
                    "mp3paramidi[ai]' or refer to the project documentation."
                ),
            )

    @staticmethod
    def detect_device(prefer_gpu: bool = True) -> "torch.device":
        """Detect the preferred device for running AI models."""
        DeviceManager._ensure_torch_available()

        if prefer_gpu and torch.cuda.is_available():
            device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name(0)
            cuda_version = torch.version.cuda
            logger.info(
                "Using CUDA device '%s' (CUDA %s)",
                gpu_name,
                cuda_version or "unknown",
            )
            return device

        logger.info("Falling back to CPU device for AI inference.")
        return torch.device("cpu")

    @staticmethod
    def get_device_info() -> Dict[str, Optional[object]]:
        """Return diagnostic information about the available compute device."""
        DeviceManager._ensure_torch_available()

        info: Dict[str, Optional[object]] = {
            "device_type": "cpu",
            "device_name": "CPU",
            "cuda_available": False,
            "cuda_version": torch.version.cuda if torch is not None else None,
            "gpu_count": 0,
            "gpu_memory_gb": None,
        }

        if torch.cuda.is_available():
            info["device_type"] = "cuda"
            info["device_name"] = torch.cuda.get_device_name(0)
            info["cuda_available"] = True
            info["gpu_count"] = torch.cuda.device_count()
            properties = torch.cuda.get_device_properties(0)
            info["gpu_memory_gb"] = round(properties.total_memory / (1024 ** 3), 2)

        return info

    @staticmethod
    def force_cpu() -> "torch.device":
        """Return a CPU device descriptor regardless of GPU availability."""
        DeviceManager._ensure_torch_available()
        logger.warning("Forcing AI inference to run on CPU.")
        return torch.device("cpu")

    @staticmethod
    def check_memory_available(required_gb: float = 2.0) -> bool:
        """Check whether enough GPU memory is available for the workload."""
        DeviceManager._ensure_torch_available()

        if not torch.cuda.is_available():
            logger.info(
                "CUDA not available; assuming CPU execution which does not use GPU memory."
            )
            return True

        properties = torch.cuda.get_device_properties(0)
        available_gb = properties.total_memory / (1024 ** 3)
        if available_gb < required_gb:
            logger.warning(
                "Detected %.2f GB VRAM which is below the recommended %.2f GB.",
                available_gb,
                required_gb,
            )
            return False

        logger.info(
            "GPU memory check passed: %.2f GB available (requirement %.2f GB).",
            available_gb,
            required_gb,
        )
        return True


__all__ = ["DeviceManager"]
