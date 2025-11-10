"""Audio separation module leveraging Demucs HTDemucs models.

This module exposes the :func:`separate_audio` public API, which loads a Demucs
model, performs source separation on the provided audio file, and saves the
resulting stems to disk.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import torch
import torchaudio
from demucs import pretrained
from demucs.apply import apply_model

logging.basicConfig(level=logging.INFO)

SUPPORTED_FORMATS = [".mp3", ".wav", ".flac", ".ogg"]
DEFAULT_MODEL = "htdemucs"
STEM_NAMES = ["drums", "bass", "other", "vocals"]
_MODEL_CACHE: Dict[str, torch.nn.Module] = {}


def _get_device() -> str:
    """Return the preferred device for computation.

    Returns
    -------
    str
        ``"cuda"`` when a CUDA-capable GPU is available, otherwise ``"cpu"``.
    """

    if torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    logging.info("Using device: %s", device)
    return device


def _load_model(model_name: str, device: str) -> torch.nn.Module:
    """Load and cache the specified Demucs model.

    Parameters
    ----------
    model_name : str
        Name of the Demucs pretrained model to load.
    device : str
        Target device (``"cpu"`` or ``"cuda"``) to which the model will be
        moved.

    Returns
    -------
    torch.nn.Module
        Loaded Demucs model in evaluation mode and resident on the requested
        device.

    Raises
    ------
    RuntimeError
        If the pretrained model cannot be downloaded or initialized.
    """

    if model_name in _MODEL_CACHE:
        cached_model = _MODEL_CACHE[model_name]
        logging.info("Reusing cached model: %s", model_name)
        return cached_model

    try:
        logging.info("Loading Demucs model: %s", model_name)
        model = pretrained.get_model(model_name)
    except Exception as exc:  # pragma: no cover - defensive logging
        error_message = (
            f"Unable to load Demucs model '{model_name}'. Verify the model name "
            "and network connectivity."
        )
        logging.exception(error_message)
        raise RuntimeError(error_message) from exc

    model.to(device)
    model.eval()
    _MODEL_CACHE[model_name] = model
    return model


def _validate_input_file(file_path: Path) -> Path:
    """Validate that the input audio file exists and is supported.

    Parameters
    ----------
    file_path : pathlib.Path
        Path to the audio file provided by the caller.

    Returns
    -------
    pathlib.Path
        The validated, absolute path to the audio file.

    Raises
    ------
    ValueError
        If the file does not exist or has an unsupported extension.
    """

    resolved_path = file_path.expanduser().resolve()
    if not resolved_path.exists():
        raise ValueError(f"Audio file not found: {resolved_path}")

    if resolved_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            "Unsupported audio format. Supported formats: "
            + ", ".join(SUPPORTED_FORMATS)
        )

    return resolved_path


def separate_audio(
    input_path: str,
    output_dir: str,
    model_name: str = DEFAULT_MODEL,
) -> Dict[str, str]:
    """Separate an audio track into individual stems using Demucs.

    Parameters
    ----------
    input_path : str
        Path to the input audio file (MP3, WAV, FLAC, or OGG).
    output_dir : str
        Directory where the separated stems will be stored. Created if it does
        not already exist.
    model_name : str, optional
        Demucs model identifier to employ. Defaults to ``"htdemucs"``.

    Returns
    -------
    dict[str, str]
        Mapping from stem names (``"drums"``, ``"bass"``, ``"other"``,
        ``"vocals"``) to the absolute file paths of the generated WAV files.

    Raises
    ------
    ValueError
        If the input file is invalid or its format is unsupported.
    RuntimeError
        If the model cannot be loaded or inference fails.
    torch.cuda.OutOfMemoryError
        If GPU memory is insufficient for the separation task.
    """

    input_path_obj = _validate_input_file(Path(input_path))
    output_dir_obj = Path(output_dir).expanduser().resolve()
    output_dir_obj.mkdir(parents=True, exist_ok=True)

    device = _get_device()
    model = _load_model(model_name, device)

    try:
        waveform, sample_rate = torchaudio.load(str(input_path_obj))
    except FileNotFoundError as exc:
        logging.exception("Input file not found during load: %s", input_path_obj)
        raise ValueError(f"Audio file not found: {input_path_obj}") from exc
    except Exception as exc:  # pragma: no cover - depends on torchaudio internals
        logging.exception("Failed to load audio file: %s", input_path_obj)
        raise RuntimeError("Failed to load the audio file. It may be corrupted.") from exc

    if waveform.dtype != torch.float32:
        waveform = waveform.to(torch.float32)

    if waveform.dim() != 2:
        raise RuntimeError("Unexpected waveform shape. Expected [channels, samples].")

    channels, _ = waveform.shape
    if channels == 1:
        waveform = waveform.repeat(2, 1)
        logging.info("Converted mono audio to stereo for Demucs compatibility.")
    elif channels > 2:
        logging.info(
            "Input audio has %s channels; using the first two channels for separation.",
            channels,
        )
        waveform = waveform[:2, :]

    mix = waveform.unsqueeze(0)  # [1, channels, samples]

    try:
        with torch.no_grad():
            separated = apply_model(
                model,
                mix,
                device=device,
                shifts=1,
                split=True,
                overlap=0.25,
                progress=False,
            )
    except torch.cuda.OutOfMemoryError:
        logging.exception("CUDA out of memory during separation: %s", input_path_obj)
        raise
    except Exception as exc:  # pragma: no cover - inference errors are rare
        logging.exception("Audio separation failed for file: %s", input_path_obj)
        raise RuntimeError("Audio separation failed. Please try again.") from exc

    if separated.dim() != 4:
        raise RuntimeError(
            "Unexpected output shape from Demucs. Expected [batch, stems, channels, samples]."
        )

    _, stem_count, stem_channels, stem_samples = separated.shape
    if stem_channels != waveform.shape[0]:
        logging.warning(
            "Stem channel count (%s) does not match input channels (%s).",
            stem_channels,
            waveform.shape[0],
        )

    stem_paths: Dict[str, str] = {}
    input_stem = input_path_obj.stem

    if stem_count != len(STEM_NAMES):
        logging.warning(
            "Model produced %s stems; expected %s. Extra stems will be named generically.",
            stem_count,
            len(STEM_NAMES),
        )

    for index in range(stem_count):
        if index < len(STEM_NAMES):
            stem_name = STEM_NAMES[index]
        else:
            stem_name = f"stem_{index}"

        stem_waveform = separated[0, index].to("cpu")
        output_file = output_dir_obj / f"{input_stem}_stem_{stem_name}.wav"
        torchaudio.save(str(output_file), stem_waveform, sample_rate)
        stem_paths[stem_name] = str(output_file)
        logging.info("Saved stem '%s' to %s", stem_name, output_file)

    return stem_paths


def get_available_models() -> list[str]:
    """Return the list of supported Demucs model identifiers.

    Returns
    -------
    list[str]
        Available model names. ``"htdemucs"`` provides four standard stems,
        ``"htdemucs_ft"`` is fine-tuned for higher quality at the cost of speed,
        ``"htdemucs_6s"`` expands to six stems including dedicated guitar and
        piano tracks, and ``"hdemucs_mmi"`` is a multi-task model variant.
    """

    return ["htdemucs", "htdemucs_ft", "htdemucs_6s", "hdemucs_mmi"]
