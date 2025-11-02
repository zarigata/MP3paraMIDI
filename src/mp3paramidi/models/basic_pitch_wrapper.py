"""Basic-Pitch transcription wrapper for MP3paraMIDI."""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Any

import numpy as np

try:  # pragma: no cover - heavy dependency
    import pretty_midi
    from basic_pitch.inference import Model, predict
except ImportError as exc:  # pragma: no cover
    pretty_midi = None  # type: ignore
    Model = None  # type: ignore
    predict = None  # type: ignore

from ..audio.loader import AudioData
from ..audio.pitch_detector import NoteEvent
from .exceptions import InferenceError, ModelLoadError

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]

VELOCITY_MIN = 40
VELOCITY_MAX = 110


@dataclass(slots=True)
class BasicPitchResult:
    """Container for Basic-Pitch transcription outputs."""

    note_events: List[NoteEvent]
    midi_data: "pretty_midi.PrettyMIDI"
    confidence_scores: np.ndarray
    processing_time: float


class BasicPitchWrapper:
    """High-level interface for running polyphonic transcription via Basic-Pitch."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        onset_threshold: float = 0.5,
        frame_threshold: float = 0.3,
        minimum_note_length: float = 0.058,
        minimum_frequency: Optional[float] = None,
        maximum_frequency: Optional[float] = None,
        cache_dir: Optional[Path] = None,
    ) -> None:
        if pretty_midi is None or Model is None or predict is None:
            raise ModelLoadError(
                model_name="basic_pitch",
                message="Basic-Pitch dependencies are not installed.",
                details=(
                    "Install the optional AI dependencies (basic-pitch, pretty_midi, torch) "
                    "to enable polyphonic transcription."
                ),
            )

        self.model_path = model_path
        self.onset_threshold = onset_threshold
        self.frame_threshold = frame_threshold
        self.minimum_note_length = minimum_note_length
        self.minimum_frequency = minimum_frequency
        self.maximum_frequency = maximum_frequency

        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parents[3] / "models" / "basic_pitch"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.model_path = Path(model_path).expanduser() if model_path else self.cache_dir / "basic_pitch.onnx"

        self._model: Optional[Model] = None

    def ensure_model_loaded(self, progress_callback: Optional[ProgressCallback] = None) -> Model:
        """Public accessor ensuring the Basic-Pitch model is available."""

        if self._model is not None:
            self._report_progress(progress_callback, 1.0, "Basic-Pitch model ready")
            return self._model

        self._report_progress(progress_callback, 0.0, "Loading Basic-Pitch model")
        self._ensure_model_loaded(progress_callback)
        self._report_progress(progress_callback, 1.0, "Basic-Pitch model ready")
        assert self._model is not None
        return self._model

    def _ensure_model_loaded(self, progress_callback: Optional[ProgressCallback] = None) -> None:
        if self._model is not None:
            return

        load_path: Optional[str]
        if self.model_path and Path(self.model_path).exists():
            load_path = str(self.model_path)
        else:
            load_path = None
        try:
            if load_path is None and self.model_path:
                logger.info("Basic-Pitch cache target will be %s", self.model_path)
            logger.info("Loading Basic-Pitch model from %s", load_path or "default package resources")
            self._model = Model(load_path)
            self._report_progress(progress_callback, 0.25, "Downloading Basic-Pitch weights")
            self._model.load_model()
            self._report_progress(progress_callback, 0.75, "Basic-Pitch weights loaded")
            self._cache_loaded_model_if_needed()
        except Exception as exc:
            raise ModelLoadError(
                model_name="basic_pitch",
                message="Failed to load Basic-Pitch model weights.",
                details=str(exc),
            ) from exc

    def _cache_loaded_model_if_needed(self) -> None:
        if self._model is None:
            return

        target = self.model_path
        if not target:
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            logger.debug("Basic-Pitch model already cached at %s", target)
            return

        candidate_paths: List[Path] = []
        for attr in ("model_path", "onnx_model_path", "model_file", "model"):
            value = getattr(self._model, attr, None)
            if isinstance(value, str):
                candidate_paths.append(Path(value))
        for candidate in candidate_paths:
            if candidate.exists():
                try:
                    shutil.copy2(candidate, target)
                    logger.info("Cached Basic-Pitch model to %s", target)
                    return
                except Exception:
                    logger.warning("Failed to cache Basic-Pitch model from %s", candidate, exc_info=True)
        logger.debug("No Basic-Pitch model file available for caching")

    def _report_progress(self, callback: Optional[ProgressCallback], value: float, message: str) -> None:
        if callback:
            try:
                callback(max(0.0, min(1.0, value)), message)
            except Exception:  # pragma: no cover
                logger.debug("Progress callback raised an exception", exc_info=True)

    def _convert_note_events(self, bp_note_events: Sequence[Tuple[float, float, int, float]]) -> List[NoteEvent]:
        converted: List[NoteEvent] = []
        for start, end, pitch, amplitude in bp_note_events:
            velocity = int(VELOCITY_MIN + (VELOCITY_MAX - VELOCITY_MIN) * float(amplitude))
            midi_note = int(pitch)
            pitch_hz = pretty_midi.note_number_to_hz(midi_note)
            converted.append(
                NoteEvent(
                    start_time=float(start),
                    end_time=float(end),
                    pitch_hz=float(pitch_hz),
                    midi_note=midi_note,
                    velocity=int(np.clip(velocity, VELOCITY_MIN, VELOCITY_MAX)),
                    confidence=float(amplitude),
                )
            )
        return converted

    def transcribe(
        self,
        audio_data: AudioData,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BasicPitchResult:
        self.ensure_model_loaded(progress_callback=progress_callback)
        assert self._model is not None

        start_time = time.perf_counter()
        self._report_progress(progress_callback, 0.0, "Starting Basic-Pitch transcription")

        waveform = audio_data.samples.astype(np.float32)
        if waveform.ndim == 2:
            waveform = waveform.mean(axis=1)
        elif waveform.ndim > 2:
            waveform = np.reshape(waveform, (waveform.shape[0], -1)).mean(axis=1)

        try:
            model_output, midi_data, note_events = predict(
                audio=waveform,
                sr=audio_data.metadata.sample_rate,
                model=self._model,
                onset_threshold=self.onset_threshold,
                frame_threshold=self.frame_threshold,
                minimum_note_length=self.minimum_note_length,
                minimum_frequency=self.minimum_frequency,
                maximum_frequency=self.maximum_frequency,
            )
        except Exception as exc:
            raise InferenceError(
                model_name="basic_pitch",
                message="Basic-Pitch transcription failed.",
                details=str(exc),
            ) from exc

        self._report_progress(progress_callback, 0.7, "Converting Basic-Pitch note events")
        converted_notes = self._convert_note_events(note_events)
        processing_time = time.perf_counter() - start_time

        # Basic-Pitch may expose confidence scores under different keys depending on the release.
        # Prefer the newer "note" key, falling back to "notes" to remain compatible with upgrades.
        confidence_scores: Any = model_output.get("note")
        if confidence_scores is None:
            confidence_scores = model_output.get("notes")
        if confidence_scores is None:
            confidence_scores = np.array([])
        elif not isinstance(confidence_scores, np.ndarray):
            confidence_scores = np.asarray(confidence_scores)
        self._report_progress(progress_callback, 1.0, "Basic-Pitch transcription complete")

        return BasicPitchResult(
            note_events=converted_notes,
            midi_data=midi_data,
            confidence_scores=confidence_scores,
            processing_time=processing_time,
        )

    def transcribe_stem(
        self,
        stem: "SeparatedStem",
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BasicPitchResult:
        from .demucs_wrapper import SeparatedStem  # Local import to avoid circular dependency

        audio_data = AudioData(
            file_path=Path(stem.name + ".wav"),
            samples=stem.samples,
            metadata=stem.metadata,
        )
        return self.transcribe(audio_data, progress_callback=progress_callback)

    @staticmethod
    def get_default_config() -> Dict[str, Dict[str, float]]:
        return {
            "balanced": {"onset_threshold": 0.5, "frame_threshold": 0.3},
            "sensitive": {"onset_threshold": 0.45, "frame_threshold": 0.25},
            "conservative": {"onset_threshold": 0.55, "frame_threshold": 0.35},
        }


__all__ = ["BasicPitchWrapper", "BasicPitchResult"]
