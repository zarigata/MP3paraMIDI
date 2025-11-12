"""Audio-to-MIDI conversion utilities leveraging Basic Pitch and Melodia.

This module mirrors the architecture of :mod:`src.audio_separation` by exposing
public APIs with comprehensive validation, logging, and error handling. It
provides:

* :func:`convert_stem_to_midi` – route stems through Spotify Basic Pitch or
  Melodia depending on the stem type and return the generated MIDI file path.
* :func:`combine_midi_files` – merge multiple MIDI files into a multi-track
  output while optionally preserving tempo information from the first file.
* :func:`convert_stems_to_combined_midi` – convenience workflow combining the
  above two steps for an end-to-end experience.

Basic Pitch is well-suited for polyphonic stems (drums, bass, guitar, piano,
and general instrumentals), while Melodia excels at extracting monophonic vocal
melodies. The resulting MIDI data leverages General MIDI program numbers so the
tracks play back with sensible instrument assignments.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import pretty_midi
from basic_pitch.inference import Model as BasicPitchModel
from basic_pitch.inference import predict_and_save as basic_pitch_predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_FORMATS = [".wav", ".mp3", ".flac", ".ogg"]
GM_PROGRAM_NUMBERS: Dict[str, int | None] = {
    "piano": 0,
    "guitar": 24,
    "bass": 33,
    "drums": None,
    "vocals": 0,
    "other": 0,
}
MELODIA_STEMS = ["vocals"]


def _validate_audio_file(file_path: Path) -> Path:
    """Validate that the input audio file exists and is supported.

    Parameters
    ----------
    file_path : pathlib.Path
        Path to the audio file being validated.

    Returns
    -------
    pathlib.Path
        Resolved path to the validated audio file.

    Raises
    ------
    ValueError
        If the file does not exist or its suffix is unsupported.
    """

    resolved_path = file_path.expanduser().resolve()
    if not resolved_path.exists():
        raise ValueError(f"Audio file not found: {resolved_path}")

    if resolved_path.suffix.lower() not in SUPPORTED_AUDIO_FORMATS:
        raise ValueError(
            "Unsupported audio format. Supported formats: "
            + ", ".join(SUPPORTED_AUDIO_FORMATS)
        )

    return resolved_path


def _assign_instrument_program(instrument: pretty_midi.Instrument, stem_name: str) -> None:
    """Assign a General MIDI program to the instrument based on the stem name.

    Parameters
    ----------
    instrument : pretty_midi.Instrument
        The instrument object whose metadata will be updated.
    stem_name : str
        Stem identifier (``"drums"``, ``"bass"``, ``"piano"``, ``"guitar"``,
        ``"vocals"``, or ``"other"``).
    """

    normalized_stem = stem_name.lower()
    instrument.name = f"{normalized_stem.title()} Track"

    if normalized_stem == "drums":
        instrument.is_drum = True
        logger.info("Assigned drum instrument metadata for stem '%s'.", stem_name)
        return

    program = GM_PROGRAM_NUMBERS.get(normalized_stem, GM_PROGRAM_NUMBERS["other"])
    if program is None:
        logger.warning(
            "Program number is None for non-drum stem '%s'. Leaving default program.",
            stem_name,
        )
        return

    instrument.program = program
    logger.info(
        "Assigned program %s to instrument for stem '%s'.", instrument.program, stem_name
    )


@lru_cache(maxsize=1)
def _get_basic_pitch_model_path() -> Optional[Path]:
    """Return the Basic Pitch model path, loading default if available."""

    model_path = os.getenv("BASIC_PITCH_MODEL_PATH")
    if model_path:
        candidate = Path(model_path).expanduser()
        if candidate.exists():
            return candidate
        logger.warning("Configured BASIC_PITCH_MODEL_PATH=%s not found.", candidate)
    if ICASSP_2022_MODEL_PATH:
        path_obj = Path(ICASSP_2022_MODEL_PATH)
        if path_obj.exists():
            return path_obj
    logger.warning(
        "Basic Pitch default model not found. MIDI conversion may fail; reinstall basic-pitch with models."
    )
    return None


@lru_cache(maxsize=1)
def _get_basic_pitch_model() -> Optional[BasicPitchModel]:
    """Instantiate and cache the Basic Pitch model if possible."""

    model_path = _get_basic_pitch_model_path()
    if not model_path:
        return None
    try:
        return BasicPitchModel(model_path)
    except Exception as exc:
        logger.warning("Failed to load Basic Pitch model at %s: %s", model_path, exc)
        return None


def _convert_with_basic_pitch(audio_path: Path, stem_name: str) -> pretty_midi.PrettyMIDI:
    """Convert audio to MIDI using Spotify Basic Pitch.

    Parameters
    ----------
    audio_path : pathlib.Path
        Path to the audio file to transcribe.
    stem_name : str
        Stem identifier used to assign General MIDI metadata.

    Returns
    -------
    pretty_midi.PrettyMIDI
        Transcribed MIDI data with instrument metadata applied.

    Raises
    ------
    RuntimeError
        If Basic Pitch inference fails.
    """

    try:
        logger.info("Running Basic Pitch inference for stem '%s'.", stem_name)
        with tempfile.TemporaryDirectory(prefix="basic_pitch_") as tmpdir:
            model = _get_basic_pitch_model()
            model_path = _get_basic_pitch_model_path()
            if model is None and model_path is None:
                raise RuntimeError(
                    "Basic Pitch model unavailable. Ensure 'basic-pitch' extras are installed."
                )

            basic_pitch_predict_and_save(
                audio_path_list=[str(audio_path)],
                output_directory=tmpdir,
                save_midi=True,
                sonify_midi=False,
                save_model_outputs=False,
                save_notes=False,
                model_or_model_path=model if model is not None else str(model_path),
            )
            temp_dir = Path(tmpdir)
            midi_candidates = sorted(temp_dir.glob("*_basic_pitch.mid"))
            if not midi_candidates:
                midi_candidates = sorted(temp_dir.glob("*.mid"))

            if not midi_candidates:
                raise RuntimeError("Basic Pitch did not produce a MIDI file.")

            midi_path = midi_candidates[0]
            try:
                midi_data = pretty_midi.PrettyMIDI(str(midi_path))
            except Exception as exc:
                raise RuntimeError(
                    "Basic Pitch produced an unreadable MIDI file."
                ) from exc
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging for inference
        logger.exception(
            "Basic Pitch transcription failed for '%s' (%s).", audio_path, stem_name
        )
        raise RuntimeError(
            "Basic Pitch transcription failed. Ensure the audio file is valid and try again."
        ) from exc

    if not midi_data.instruments:
        logger.warning(
            "Basic Pitch produced no instruments for '%s'. Returning empty MIDI.",
            audio_path,
        )
        return pretty_midi.PrettyMIDI()

    for instrument in midi_data.instruments:
        _assign_instrument_program(instrument, stem_name)

    return midi_data


def _convert_with_melodia(audio_path: Path, stem_name: str) -> pretty_midi.PrettyMIDI:
    """Convert audio to MIDI using Melodia with a librosa fallback.

    Parameters
    ----------
    audio_path : pathlib.Path
        Path to the audio file to transcribe.
    stem_name : str
        Stem identifier used to assign General MIDI metadata. Intended for
        ``"vocals"``.

    Returns
    -------
    pretty_midi.PrettyMIDI
        Transcribed MIDI data with instrument metadata applied.

    Raises
    ------
    RuntimeError
        If Melodia inference fails or the Vamp plugin is unavailable.
    """

    midi_data: pretty_midi.PrettyMIDI | None = None

    try:
        try:
            from audio2midi import Melodia  # type: ignore[attr-defined]
        except ImportError:
            from audio2midi.melodia_pitch_detector import (  # type: ignore[attr-defined]
                Melodia,
            )

        logger.info("Running Melodia inference for stem '%s'.", stem_name)
        melodia = Melodia()
        with tempfile.TemporaryDirectory(prefix="melodia_") as tmpdir:
            output_file = Path(tmpdir) / f"{audio_path.stem}_melodia.mid"
            result_path = melodia.predict(
                str(audio_path),
                output_file=str(output_file),
            )

            midi_path = Path(result_path) if result_path else output_file
            if not midi_path.exists():
                raise RuntimeError("Melodia did not produce a MIDI file.")

            midi_data = pretty_midi.PrettyMIDI(str(midi_path))
    except ImportError:
        logger.warning(
            "Melodia plugin not available; falling back to librosa.pyin for stem '%s'.",
            stem_name,
        )
    except Exception as exc:  # pragma: no cover - dependent on external plugin
        logger.exception(
            "Melodia transcription failed for '%s' (%s).", audio_path, stem_name
        )
        logger.warning(
            "Falling back to librosa.pyin for stem '%s' after Melodia failure.",
            stem_name,
        )
    else:
        if not midi_data.instruments:
            logger.warning(
                "Melodia produced no instruments for '%s'. Returning empty MIDI.",
                audio_path,
            )
            return pretty_midi.PrettyMIDI()

        for instrument in midi_data.instruments:
            _assign_instrument_program(instrument, stem_name)

        return midi_data

    return _convert_with_librosa_py_in(audio_path, stem_name)


def _convert_with_librosa_py_in(audio_path: Path, stem_name: str) -> pretty_midi.PrettyMIDI:
    """Fallback transcription using ``librosa.pyin`` for monophonic melodies."""

    try:
        import numpy as np
        import librosa
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise RuntimeError(
            "Melodia transcription failed and librosa is unavailable for fallback."
        ) from exc

    logger.info("Estimating F0 contour with librosa.pyin for stem '%s'.", stem_name)
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)

    if y.size == 0:
        logger.warning("Audio file '%s' is empty. Returning empty MIDI.", audio_path)
        return pretty_midi.PrettyMIDI()

    hop_length = 256
    try:
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            hop_length=hop_length,
        )
    except Exception as exc:
        logger.exception("librosa.pyin failed for '%s'.", audio_path)
        raise RuntimeError("Fallback transcription failed using librosa.pyin.") from exc

    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)
    midi.instruments.append(instrument)

    if f0 is None or voiced_flag is None:
        logger.warning("librosa.pyin returned no F0 track for '%s'.", audio_path)
    else:
        times = librosa.times_like(f0, sr=sr, hop_length=hop_length)
        frame_duration = hop_length / sr

        current_start: float | None = None
        current_pitches: list[float] = []

        for idx, (frequency, is_voiced) in enumerate(zip(f0, voiced_flag)):
            time = times[idx]
            if is_voiced and frequency is not None and not np.isnan(frequency):
                if current_start is None:
                    current_start = time
                    current_pitches = [frequency]
                else:
                    current_pitches.append(frequency)
            elif current_start is not None:
                end_time = time
                _append_note_from_frequencies(instrument, current_start, end_time, current_pitches)
                current_start = None
                current_pitches = []

        if current_start is not None:
            end_time = times[-1] + frame_duration
            _append_note_from_frequencies(instrument, current_start, end_time, current_pitches)

    _assign_instrument_program(instrument, stem_name)

    return midi


def _append_note_from_frequencies(
    instrument: pretty_midi.Instrument,
    start_time: float,
    end_time: float,
    frequencies: list[float],
) -> None:
    """Create a PrettyMIDI note from frequency samples if possible."""

    import numpy as np
    from pretty_midi.utilities import hz_to_note_number

    if not frequencies:
        return

    median_frequency = float(np.nanmedian(frequencies))
    if np.isnan(median_frequency):
        return

    pitch = int(round(hz_to_note_number(median_frequency)))
    if end_time <= start_time:
        end_time = start_time + 0.05

    note = pretty_midi.Note(
        velocity=100,
        pitch=pitch,
        start=start_time,
        end=end_time,
    )
    instrument.notes.append(note)


def convert_stem_to_midi(stem_path: str, stem_name: str, output_dir: str) -> str:
    """Convert a single audio stem to MIDI using the appropriate transcription model.

    Parameters
    ----------
    stem_path : str
        Path to the audio stem (WAV, MP3, FLAC, or OGG).
    stem_name : str
        Stem identifier indicating the route (``"vocals"`` uses Melodia, others
        use Basic Pitch).
    output_dir : str
        Directory where the generated MIDI file will be written.

    Returns
    -------
    str
        Path to the generated MIDI file.

    Raises
    ------
    ValueError
        If the input file is invalid or unsupported.
    RuntimeError
        If transcription fails.
    IOError
        If the output MIDI file cannot be written.
    """

    try:
        audio_path = _validate_audio_file(Path(stem_path))
        output_path_obj = Path(output_dir).expanduser().resolve()
        output_path_obj.mkdir(parents=True, exist_ok=True)

        normalized_stem = stem_name.lower()
        if normalized_stem in MELODIA_STEMS:
            midi_data = _convert_with_melodia(audio_path, normalized_stem)
        else:
            midi_data = _convert_with_basic_pitch(audio_path, normalized_stem)

        base_output_file = output_path_obj / f"{audio_path.stem}_midi_{normalized_stem}.mid"
        output_file = base_output_file
        suffix_counter = 1
        while output_file.exists():
            output_file = base_output_file.with_name(
                f"{base_output_file.stem}-{suffix_counter}{base_output_file.suffix}"
            )
            suffix_counter += 1

        midi_data.write(str(output_file))
        logger.info("Saved MIDI for stem '%s' to %s", stem_name, output_file)
        return str(output_file)
    except (ValueError, RuntimeError):
        raise
    except OSError as exc:
        logger.exception("Failed to write MIDI file for stem '%s'.", stem_name)
        raise IOError("Failed to write the MIDI file to disk.") from exc


def combine_midi_files(
    midi_paths: List[str], output_path: str, preserve_tempo: bool = True
) -> str:
    """Combine multiple MIDI files into a single multi-track MIDI file.

    Parameters
    ----------
    midi_paths : list[str]
        Collection of MIDI file paths to merge. Each file's instruments become
        separate tracks in the output.
    output_path : str
        Destination path for the combined MIDI file.
    preserve_tempo : bool, optional
        Preserve tempo, key, and time signature data from the first MIDI file
        when ``True``. Defaults to ``True``. Only the initial tempo can be
        retained because PrettyMIDI does not expose a public multi-tempo setter.

    Returns
    -------
    str
        Path to the combined MIDI file.

    Raises
    ------
    ValueError
        If ``midi_paths`` is empty.
    IOError
        If any file cannot be read or the output cannot be written.
    """

    if not midi_paths:
        raise ValueError("At least one MIDI file must be provided for combination.")

    resolved_paths: List[Path] = []
    invalid_paths: List[str] = []

    for path in midi_paths:
        candidate = Path(path).expanduser().resolve()
        if not candidate.exists() or not candidate.is_file() or candidate.suffix.lower() not in {".mid", ".midi"}:
            invalid_paths.append(str(path))
        else:
            resolved_paths.append(candidate)

    if invalid_paths:
        raise ValueError(
            "Invalid MIDI paths provided: " + ", ".join(invalid_paths)
        )

    first_path = resolved_paths[0]
    try:
        first_midi = pretty_midi.PrettyMIDI(str(first_path))
    except Exception as exc:
        logger.exception("Failed to read MIDI file: %s", first_path)
        raise IOError(f"Failed to read MIDI file: {first_path}") from exc

    tempo_preserved = False
    output_midi: pretty_midi.PrettyMIDI

    initial_tempo: float | None = None
    if preserve_tempo:
        try:
            _, tempo_bpm = first_midi.get_tempo_changes()
            if tempo_bpm.size > 0:
                initial_tempo = float(tempo_bpm[0])
                if tempo_bpm.size > 1:
                    logger.warning(
                        "Multiple tempo changes detected in '%s'; only the initial tempo (%.2f BPM) will be preserved due to PrettyMIDI lacking a public setter.",
                        first_path,
                        initial_tempo,
                    )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning(
                "Unable to retrieve tempo changes from '%s': %s", first_path, exc
            )

    if initial_tempo is not None:
        try:
            output_midi = pretty_midi.PrettyMIDI(initial_tempo=initial_tempo)
            tempo_preserved = True
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning(
                "Failed to initialize combined MIDI with tempo %.2f BPM from '%s': %s",
                initial_tempo,
                first_path,
                exc,
            )
            output_midi = pretty_midi.PrettyMIDI()
    else:
        if preserve_tempo:
            logger.info(
                "No tempo information found in '%s'; PrettyMIDI default tempo will be used.",
                first_path,
            )
        output_midi = pretty_midi.PrettyMIDI()

    output_midi.time_signature_changes = list(first_midi.time_signature_changes)
    output_midi.key_signature_changes = list(first_midi.key_signature_changes)
    output_midi.instruments.extend(first_midi.instruments)

    for midi_path in resolved_paths[1:]:
        try:
            midi = pretty_midi.PrettyMIDI(str(midi_path))
        except Exception as exc:
            logger.exception("Failed to read MIDI file: %s", midi_path)
            raise IOError(f"Failed to read MIDI file: {midi_path}") from exc

        output_midi.instruments.extend(midi.instruments)

    if not output_midi.instruments:
        logger.warning("All provided MIDI files were empty. Output will contain no tracks.")

    output_path_obj = Path(output_path).expanduser().resolve()
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_midi.write(str(output_path_obj))
    except Exception as exc:
        logger.exception("Failed to write combined MIDI file: %s", output_path_obj)
        raise IOError("Failed to write the combined MIDI file to disk.") from exc

    track_count = len(output_midi.instruments)
    logger.info(
        "Saved combined MIDI with %s tracks%s to %s",
        track_count,
        " and preserved tempo" if tempo_preserved else "",
        output_path_obj,
    )
    return str(output_path_obj)


def convert_stems_to_combined_midi(
    stem_paths: Dict[str, str], output_path: str
) -> str:
    """Convert multiple stems and merge them into a single MIDI file.

    Parameters
    ----------
    stem_paths : dict[str, str]
        Mapping of stem names to audio file paths (e.g., ``{"drums": "/path"}`).
    output_path : str
        Destination path for the combined MIDI output file.

    Returns
    -------
    str
        Path to the combined MIDI file.

    Raises
    ------
    ValueError
        If any stem path is invalid.
    RuntimeError
        If transcription fails for any stem.
    IOError
        If writing intermediate or final MIDI files fails.
    """

    temp_dir = Path(tempfile.mkdtemp(prefix="audio_to_midi_"))
    midi_files: List[str] = []

    try:
        for stem_name, path in stem_paths.items():
            midi_file = convert_stem_to_midi(path, stem_name, str(temp_dir))
            midi_files.append(midi_file)

        combined_path = combine_midi_files(midi_files, output_path)
        return combined_path
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:  # pragma: no cover - best effort cleanup
            logger.warning("Failed to remove temporary directory: %s", temp_dir)


def get_supported_stem_types() -> List[str]:
    """Return the supported stem types and their associated transcription route.

    Returns
    -------
    list[str]
        Supported stem identifiers. ``"vocals"`` uses Melodia; all others use
        Basic Pitch.
    """

    return list(GM_PROGRAM_NUMBERS.keys())
