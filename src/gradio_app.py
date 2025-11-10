"""Gradio interface for the MP3paraMIDI project.

This module defines a tabbed Gradio Blocks application that exposes the
project's core capabilities: audio stem separation using Demucs models and
conversion of the generated stems into a combined MIDI file. The interface is
intended to be mounted inside a FastAPI parent (see :mod:`src.main`) or
launched in standalone mode (see :mod:`src.gradio_standalone`).

Key architectural decisions:

* Reuse the existing Flask/CLI processing functions directly to avoid
  duplicating I/O logic or invoking HTTP endpoints within the same process.
* Provide a multi-tab user experience that mirrors the web UI workflows while
  remaining notebook-friendly for ML demos.
* Maintain minimal state between tabs via ``gr.State`` components to enable the
  MIDI conversion tab to access the most recent separation results.

The module exposes a single public factory, :func:`create_gradio_interface`, so
that other entry points can construct the interface without triggering a
``gradio.Blocks.launch`` call.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import gradio as gr

from src.audio_separation import get_available_models, separate_audio
from src.audio_to_midi import (
    convert_stems_to_combined_midi,
    get_supported_stem_types,
)

try:  # Optional import used for more specific CUDA out-of-memory handling.
    import torch
except ImportError:  # pragma: no cover - torch should already be installed.
    torch = None  # type: ignore


logger = logging.getLogger(__name__)

STEM_ORDER: Tuple[str, ...] = ("drums", "bass", "other", "vocals")
"""Canonical order for displaying stem outputs."""

SUMMARY_HEADER = "### Separation Summary"
"""Markdown header used in summary outputs."""


def _format_file_size(num_bytes: int) -> str:
    """Return a human-readable string for *num_bytes*.

    Parameters
    ----------
    num_bytes:
        The number of bytes to format.

    Returns
    -------
    str
        A human-friendly representation (e.g., ``"12.34 MB"``).
    """

    if num_bytes < 0:
        raise ValueError("File size must be non-negative")

    step_unit = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < step_unit:
            return f"{size:.2f} {unit}"
        size /= step_unit
    return f"{size * step_unit:.2f} TB"


def _create_temp_output_dir() -> Path:
    """Create and return a temporary directory for Gradio outputs."""

    temp_path = Path(tempfile.mkdtemp(prefix="gradio_mp3midi_"))
    logger.debug("Created temporary output directory: %s", temp_path)
    return temp_path


def _cleanup_directory(path: Path) -> None:
    """Remove *path* if it exists. Logged but non-fatal on failure."""

    if path.exists():
        try:
            shutil.rmtree(path, ignore_errors=True)
            logger.debug("Cleaned up directory: %s", path)
        except OSError as exc:  # pragma: no cover - best-effort cleanup
            logger.warning("Failed to clean up directory %s: %s", path, exc)


def _serialize_stem_paths(stem_paths: Dict[str, str]) -> str:
    """Return a JSON string representing *stem_paths*."""

    return json.dumps(stem_paths, ensure_ascii=False)


def _prepare_stem_outputs(stem_paths: Dict[str, str]) -> Tuple[List[Optional[str]], str]:
    """Return a tuple of ordered stem audio paths and a Markdown summary.

    Parameters
    ----------
    stem_paths:
        Mapping of stem name to absolute file path produced by
        :func:`separate_audio`.

    Returns
    -------
    tuple
        ``([stem_path_or_none, ...], summary_markdown)`` where the list is
        ordered according to :data:`STEM_ORDER`.
    """

    ordered_paths: List[Optional[str]] = []
    summary_lines: List[str] = [SUMMARY_HEADER]

    for stem_name in STEM_ORDER:
        stem_path = stem_paths.get(stem_name)
        if stem_path and Path(stem_path).exists():
            try:
                file_size = Path(stem_path).stat().st_size
                human_size = _format_file_size(file_size)
            except OSError:
                file_size = 0
                human_size = "Unknown size"
            ordered_paths.append(stem_path)
            summary_lines.append(f"- **{stem_name.title()}**: {human_size}")
        else:
            ordered_paths.append(None)
            summary_lines.append(f"- **{stem_name.title()}**: Not available")

    summary_markdown = "\n".join(summary_lines)
    return ordered_paths, summary_markdown


def process_separation(audio_file: Optional[str], model_name: str) -> Tuple[
    str,
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    str,
    str,
    str,
]:
    """Separate an input *audio_file* into stems using *model_name*.

    Parameters
    ----------
    audio_file:
        Absolute path to the uploaded audio file. Gradio provides this as a
        filesystem path when ``type="filepath"`` is used.
    model_name:
        Name of the Demucs model to use.

    Returns
    -------
    tuple
        ``(status, drums, bass, other, vocals, job_id, stem_paths_json, summary)``
        where individual stem outputs are file paths or ``None``.
    """

    if not audio_file:
        logger.warning("process_separation called without an audio file")
        return (
            "Please upload an audio file before starting separation.",
            None,
            None,
            None,
            None,
            "",
            "{}",
            "",
        )

    output_dir = _create_temp_output_dir()
    logger.info(
        "Starting audio separation | audio=%s | model=%s | output_dir=%s",
        audio_file,
        model_name,
        output_dir,
    )

    try:
        stem_paths = separate_audio(audio_file, str(output_dir), model_name)
    except ValueError as exc:
        logger.error("Invalid input for separation: %s", exc)
        _cleanup_directory(output_dir)
        return (
            f"Input error: {exc}",
            None,
            None,
            None,
            None,
            "",
            "{}",
            "",
        )
    except RuntimeError as exc:
        logger.exception("Runtime error during separation: %s", exc)
        _cleanup_directory(output_dir)
        return (
            f"Separation failed: {exc}",
            None,
            None,
            None,
            None,
            "",
            "{}",
            "",
        )
    except Exception as exc:  # pragma: no cover - defensive catch-all
        if torch is not None and isinstance(exc, torch.cuda.OutOfMemoryError):
            message = "GPU out of memory. Reduce input size or use CPU mode."
            logger.error("CUDA OOM during separation: %s", exc)
        else:
            message = f"Unexpected error: {exc}"
            logger.exception("Unhandled error during separation: %s", exc)
        _cleanup_directory(output_dir)
        return (
            message,
            None,
            None,
            None,
            None,
            "",
            "{}",
            "",
        )

    ordered_paths, summary_markdown = _prepare_stem_outputs(stem_paths)
    stem_paths_json = _serialize_stem_paths(stem_paths)
    job_id = output_dir.name

    status_message = "Audio separated successfully."
    logger.info("Separation completed | job_id=%s", job_id)

    return (
        status_message,
        ordered_paths[0],
        ordered_paths[1],
        ordered_paths[2],
        ordered_paths[3],
        job_id,
        stem_paths_json,
        summary_markdown,
    )


def _resolve_job_directory(job_id: str) -> Optional[Path]:
    """Locate the temporary directory associated with *job_id* if it exists."""

    if not job_id:
        logger.warning("process_midi_conversion called without a job ID")
        return None

    temp_dir = Path(tempfile.gettempdir())
    candidate = temp_dir / job_id
    if candidate.exists():
        return candidate

    # Handle prefixed directories created via :func:`_create_temp_output_dir`.
    prefixed_candidate = temp_dir / f"gradio_mp3midi_{job_id}"
    if prefixed_candidate.exists():
        return prefixed_candidate

    logger.error("No directory found for job_id=%s", job_id)
    return None


def process_midi_conversion(job_id: str, stem_paths_json: str) -> Tuple[str, Optional[str]]:
    """Convert stems referenced by *stem_paths_json* into a combined MIDI file."""

    if not job_id:
        return ("Missing job ID. Run audio separation first.", None)

    try:
        stem_paths: Dict[str, str] = json.loads(stem_paths_json) if stem_paths_json else {}
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode stem paths JSON: %s", exc)
        return ("Invalid internal state. Please rerun separation.", None)

    if not stem_paths:
        return ("No stems available. Run audio separation first.", None)

    job_dir = _resolve_job_directory(job_id)
    if job_dir is None:
        return ("Could not locate separated stems. Please rerun separation.", None)

    midi_output_dir = job_dir / "midi"
    midi_output_dir.mkdir(parents=True, exist_ok=True)
    midi_output_path = midi_output_dir / "combined.mid"
    logger.info("Starting MIDI conversion | job_id=%s", job_id)

    try:
        midi_path = convert_stems_to_combined_midi(stem_paths, str(midi_output_path))
    except (ValueError, RuntimeError, IOError) as exc:
        logger.exception("Failed to convert stems to MIDI: %s", exc)
        return (f"MIDI conversion failed: {exc}", None)
    except Exception as exc:  # pragma: no cover - defensive catch-all
        logger.exception("Unexpected error during MIDI conversion: %s", exc)
        return (f"Unexpected error: {exc}", None)

    logger.info("MIDI conversion completed | midi_path=%s", midi_path)
    return ("MIDI conversion completed successfully.", midi_path)


def process_full_workflow(audio_file: Optional[str], model_name: str) -> Tuple[
    str,
    List[Optional[str]],
    Optional[str],
    str,
]:
    """Run separation followed by MIDI conversion in a single step."""

    (
        separation_status,
        drums,
        bass,
        other,
        vocals,
        job_id,
        stem_paths_json,
        summary,
    ) = process_separation(audio_file, model_name)

    stems = [drums, bass, other, vocals]
    if not job_id:
        return (separation_status, stems, None, summary)

    midi_status, midi_path = process_midi_conversion(job_id, stem_paths_json)
    final_status = f"{separation_status} {midi_status}".strip()
    return (final_status, stems, midi_path, summary)


def _build_tab_audio_separation() -> Dict[str, gr.components.Component]:
    """Create the "Separate Audio" tab and return its components."""

    with gr.Tab("🎚️ Separate Audio"):
        gr.Markdown("Upload an audio file to separate it into stems using Demucs.")
        audio_input = gr.Audio(
            type="filepath",
            label="Upload Audio File",
            sources=["upload"],
            file_types=[".mp3", ".wav", ".flac", ".ogg"],
        )
        model_dropdown = gr.Dropdown(
            choices=get_available_models(),
            value="htdemucs",
            label="Demucs Model",
        )
        separate_btn = gr.Button("Separate Audio", variant="primary")
        status_text = gr.Textbox(label="Status", interactive=False)
        gr.Markdown("### Separated Stems")

        stem_outputs = [
            gr.Audio(label="Drums", type="filepath"),
            gr.Audio(label="Bass", type="filepath"),
            gr.Audio(label="Other", type="filepath"),
            gr.Audio(label="Vocals", type="filepath"),
        ]

        job_id_state = gr.State()
        stem_paths_state = gr.State()
        summary_output = gr.Markdown()

        separate_btn.click(
            fn=process_separation,
            inputs=[audio_input, model_dropdown],
            outputs=[
                status_text,
                *stem_outputs,
                job_id_state,
                stem_paths_state,
                summary_output,
            ],
        )

    return {
        "audio_input": audio_input,
        "model_dropdown": model_dropdown,
        "separate_btn": separate_btn,
        "status_text": status_text,
        "stem_outputs": stem_outputs,
        "job_id_state": job_id_state,
        "stem_paths_state": stem_paths_state,
        "summary_output": summary_output,
    }


def _build_tab_midi_conversion(job_id_state: gr.State, stem_paths_state: gr.State) -> Dict[str, gr.components.Component]:
    """Create the "Convert to MIDI" tab and return its components."""

    with gr.Tab("🎼 Convert to MIDI"):
        gr.Markdown(
            "Convert previously separated stems into a multi-track MIDI file. "
            "Run the separation step first to populate the hidden state."
        )
        convert_btn = gr.Button("Convert to MIDI", variant="primary")
        midi_status = gr.Textbox(label="Status", interactive=False)
        midi_output = gr.File(label="Download MIDI File")

        convert_btn.click(
            fn=process_midi_conversion,
            inputs=[job_id_state, stem_paths_state],
            outputs=[midi_status, midi_output],
        )

    return {
        "convert_btn": convert_btn,
        "midi_status": midi_status,
        "midi_output": midi_output,
    }


def _build_tab_full_workflow() -> Dict[str, gr.components.Component]:
    """Create the "Quick Workflow" tab and return its components."""

    with gr.Tab("⚡ Quick Workflow"):
        gr.Markdown(
            "Upload audio to run separation and MIDI conversion in a single step."
        )
        quick_audio_input = gr.Audio(
            type="filepath",
            label="Upload Audio File",
            sources=["upload"],
            file_types=[".mp3", ".wav", ".flac", ".ogg"],
        )
        quick_model_dropdown = gr.Dropdown(
            choices=get_available_models(),
            value="htdemucs",
            label="Demucs Model",
        )
        quick_process_btn = gr.Button("Process & Convert", variant="primary")
        quick_status = gr.Textbox(label="Status", interactive=False)
        gr.Markdown("### Results")
        quick_stem_outputs = [
            gr.Audio(label="Drums", type="filepath"),
            gr.Audio(label="Bass", type="filepath"),
            gr.Audio(label="Other", type="filepath"),
            gr.Audio(label="Vocals", type="filepath"),
        ]
        quick_midi_output = gr.File(label="Download MIDI File")
        quick_summary = gr.Markdown()

        quick_process_btn.click(
            fn=process_full_workflow,
            inputs=[quick_audio_input, quick_model_dropdown],
            outputs=[quick_status, *quick_stem_outputs, quick_midi_output, quick_summary],
        )

    return {
        "quick_audio_input": quick_audio_input,
        "quick_model_dropdown": quick_model_dropdown,
        "quick_process_btn": quick_process_btn,
        "quick_status": quick_status,
        "quick_stem_outputs": quick_stem_outputs,
        "quick_midi_output": quick_midi_output,
        "quick_summary": quick_summary,
    }


def create_gradio_interface() -> gr.Blocks:
    """Return the configured Gradio Blocks interface for MP3paraMIDI."""

    logger.debug("Building Gradio interface")
    with gr.Blocks(
        title="MP3paraMIDI - Gradio Interface",
        css=None,
        theme=gr.themes.Soft(),
        analytics_enabled=False,
    ) as demo:
        gr.Markdown("""
        # MP3paraMIDI - Gradio Interface
        AI-powered audio separation and MIDI conversion.

        Developed by [zarigata](https://github.com/zarigata)
        """)

        components_sep = _build_tab_audio_separation()
        components_midi = _build_tab_midi_conversion(
            components_sep["job_id_state"], components_sep["stem_paths_state"]
        )
        _build_tab_full_workflow()

        gr.Markdown(
            """
            ---
            **Need a public URL?** Use the standalone launcher with ``GRADIO_SHARE=True``
            or tunnel the unified server via ngrok. Source code available on
            [GitHub](https://github.com/zarigata/MP3paraMIDI).
            """
        )

    logger.debug("Gradio interface built successfully")
    return demo


__all__ = ["create_gradio_interface", "process_separation", "process_midi_conversion", "process_full_workflow"]
