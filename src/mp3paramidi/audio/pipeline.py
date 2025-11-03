"""
Audio-to-MIDI conversion pipeline.

This module provides a high-level interface for converting audio files to MIDI
using pitch detection and note segmentation.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .pitch_detector import PitchDetector, NoteEvent
from ..midi.generator import MidiGenerator, MidiGenerationError
from .loader import AudioData
from .tempo_detector import TempoDetector, TempoInfo
from .note_filter import NoteFilter, FilterConfig
from ..midi.quantizer import NoteQuantizer, QuantizationGrid
from ..models import BasicPitchWrapper, DemucsWrapper, ModelError, ModelLoadError, SeparatedStem

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of an audio-to-MIDI conversion.
    
    Attributes:
        success: Whether the conversion was successful.
        output_path: Path to the generated MIDI file, or None if conversion failed.
        note_count: Number of notes detected in the audio.
        duration: Duration of the generated MIDI in seconds.
        error_message: Error message if conversion failed, or None if successful.
        processing_time: Time taken for the conversion in seconds.
    """
    success: bool
    output_path: Optional[Path]
    note_count: int = 0
    duration: float = 0.0
    error_message: Optional[str] = None
    processing_time: float = 0.0
    separation_enabled: bool = False
    stem_count: int = 1
    transcription_method: str = "monophonic"
    model_info: Dict[str, Any] = field(default_factory=dict)
    detected_tempo: Optional[float] = None
    beat_times: Optional[List[float]] = None
    quantization_applied: bool = False
    notes_filtered: int = 0


@dataclass
class PipelineProgress:
    """Progress update during audio-to-MIDI conversion.
    
    Attributes:
        stage: Current processing stage.
        progress: Progress percentage (0.0 to 1.0).
        message: Human-readable status message.
    """
    stage: str
    progress: float
    message: str


class AudioToMidiPipeline:
    """Pipeline for converting audio to MIDI.
    
    This class orchestrates the entire audio-to-MIDI conversion process,
    including pitch detection, note segmentation, and MIDI file generation.
    
    Args:
        fmin: Minimum frequency in Hz or note name (e.g., 'C2').
        fmax: Maximum frequency in Hz or note name (e.g., 'C7').
        tempo: Tempo in beats per minute.
        min_note_duration: Minimum duration in seconds for a note to be included.
        progress_callback: Optional callback function for progress updates.
    """
    
    def __init__(
        self,
        fmin: float | str = 'C2',
        fmax: float | str = 'C7',
        tempo: float = 120.0,
        min_note_duration: float = 0.05,
        progress_callback: Optional[Callable[[PipelineProgress], None]] = None,
        *,
        use_ai_models: bool = False,
        enable_separation: bool = False,
        demucs_model: str = "htdemucs",
        basic_pitch_config: Optional[Dict[str, float]] = None,
        device: Optional[str] = None,
        models_cache_dir: Optional[Path] = None,
        detect_tempo: bool = True,
        quantization_enabled: bool = False,
        quantization_grid: QuantizationGrid = QuantizationGrid.SIXTEENTH,
        filter_config: Optional[FilterConfig] = None,
    ) -> None:
        self.fmin = fmin
        self.fmax = fmax
        self.tempo = tempo
        self.min_note_duration = min_note_duration
        self.progress_callback = progress_callback

        self.use_ai_models = use_ai_models
        self.enable_separation = enable_separation
        self.demucs_model = demucs_model
        self.basic_pitch_config = basic_pitch_config or {}
        self._device_str = device
        self.models_cache_dir = models_cache_dir

        # New features
        self.detect_tempo = detect_tempo
        self.quantization_enabled = quantization_enabled
        self.quantization_grid = quantization_grid
        self.filter_config = filter_config or FilterConfig()

        self.pitch_detector = PitchDetector(fmin=fmin, fmax=fmax)
        self.midi_generator = MidiGenerator(tempo=tempo)

        # Initialize new components
        self.tempo_detector = TempoDetector() if self.detect_tempo else None
        self.note_quantizer = None  # Created after tempo detection
        self.note_filter = NoteFilter(self.filter_config)

        self._demucs_wrapper: Optional[DemucsWrapper] = None
        self._basic_pitch_wrapper: Optional[BasicPitchWrapper] = None
    
    def process(
        self,
        audio_data: AudioData,
        output_path: Optional[Path] = None
    ) -> PipelineResult:
        """Process an audio file and convert it to MIDI.
        
        Args:
            audio_data: Audio data to process.
            output_path: Path to save the MIDI file. If None, will use the same
                path as the input file with a .mid extension.
                
        Returns:
            PipelineResult containing the conversion result.
        """
        start_time = time.perf_counter()
        result = PipelineResult(success=False, output_path=None)
        
        try:
            # Set default output path if not provided
            if output_path is None:
                if not audio_data.metadata.file_path:
                    raise ValueError("No output path provided and audio has no file path")
                output_path = Path(audio_data.metadata.file_path).with_suffix('.mid')
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            self._report_progress('loading', 0.0, 'Loading audio...')

            if not self.use_ai_models:
                self._process_monophonic(audio_data, output_path, result)
            else:
                self._process_with_ai(audio_data, output_path, result)
            
        except Exception as e:
            logger.error(f"Audio-to-MIDI conversion failed: {str(e)}", exc_info=True)
            result.error_message = str(e)
            result.success = False
        
        # Calculate processing time
        result.processing_time = time.perf_counter() - start_time
        
        # Log completion
        if result.success:
            logger.info(
                f"Successfully converted audio to MIDI: "
                f"{result.note_count} notes, {result.duration:.2f}s duration, "
                f"took {result.processing_time:.2f}s"
            )
        else:
            logger.error(
                f"Audio-to-MIDI conversion failed: {result.error_message}"
            )
        
        return result
    
    def _initialize_ai_models(self) -> Tuple[Optional[DemucsWrapper], Optional[BasicPitchWrapper]]:
        if self._basic_pitch_wrapper is not None or self._demucs_wrapper is not None:
            return self._demucs_wrapper, self._basic_pitch_wrapper

        self._report_progress('model_loading', 0.05, 'Preparing AI models...')

        # Import DeviceManager here to avoid circular imports
        from ..models.device_manager import DeviceManager
        
        # Get device info for diagnostics
        device_info = DeviceManager.get_device_info()
        logger.info("Device Info: %s", device_info)
        
        # Log GPU memory information if available
        if device_info['cuda_available'] and device_info['gpu_memory_gb'] is not None:
            logger.info("GPU Memory: %.2f GB available", device_info['gpu_memory_gb'])
        
        demucs = None
        basic_pitch = None

        try:
            # Check memory requirements before loading models
            if self.enable_separation:
                if DemucsWrapper is None:
                    raise ModelLoadError(
                        model_name=self.demucs_model,
                        message="Demucs wrapper is unavailable.",
                        details="Install optional AI dependencies (torch, torchaudio, demucs).",
                    )
                
                # Check if we have enough memory for Demucs
                min_demucs_memory_gb = 4.0  # Minimum recommended for Demucs
                if device_info['cuda_available'] and device_info['gpu_memory_gb'] is not None:
                    if device_info['gpu_memory_gb'] < min_demucs_memory_gb:
                        logger.warning(
                            "Low GPU memory (%.2f GB). Demucs recommends at least %.1f GB. "
                            "This may cause out-of-memory errors.",
                            device_info['gpu_memory_gb'], min_demucs_memory_gb
                        )
                
                demucs = DemucsWrapper(
                    model_name=self.demucs_model,
                    device=self._device_str,
                    cache_dir=self.models_cache_dir,
                )
                
                # Log model size information
                if hasattr(demucs, 'get_model_size_mb'):
                    model_size_mb = demucs.get_model_size_mb()
                    logger.info("Demucs model size: %.2f MB", model_size_mb)
            
            if BasicPitchWrapper is None:
                raise ModelLoadError(
                    model_name="basic_pitch",
                    message="Basic-Pitch wrapper is unavailable.",
                    details="Install optional AI dependencies (basic-pitch, pretty_midi, torch).",
                )
                
            # Check if we have enough memory for Basic-Pitch
            min_bp_memory_gb = 2.0  # Minimum recommended for Basic-Pitch
            if device_info['cuda_available'] and device_info['gpu_memory_gb'] is not None:
                if device_info['gpu_memory_gb'] < min_bp_memory_gb:
                    logger.warning(
                        "Low GPU memory (%.2f GB). Basic-Pitch recommends at least %.1f GB. "
                        "This may cause out-of-memory errors.",
                        device_info['gpu_memory_gb'], min_bp_memory_gb
                    )
            
            basic_pitch = BasicPitchWrapper(
                model_path=self.basic_pitch_config.get('model_path'),
                onset_threshold=self.basic_pitch_config.get('onset_threshold', 0.5),
                frame_threshold=self.basic_pitch_config.get('frame_threshold', 0.3),
                minimum_note_length=self.basic_pitch_config.get('minimum_note_length', 0.058),
                minimum_frequency=self.basic_pitch_config.get('minimum_frequency'),
                maximum_frequency=self.basic_pitch_config.get('maximum_frequency'),
                cache_dir=self.models_cache_dir,
            )
            
            # Log model size information if available
            if hasattr(basic_pitch, 'get_model_size_mb'):
                model_size_mb = basic_pitch.get_model_size_mb()
                logger.info("Basic-Pitch model size: %.2f MB", model_size_mb)
                
            # Log device being used
            if hasattr(basic_pitch, 'device'):
                logger.info("Using device: %s", basic_pitch.device)
                
        except ModelError as exc:
            logger.error("Failed to initialize AI models: %s", exc, exc_info=True)
            # Add device info to the error message for better diagnostics
            device_type = device_info.get('device_type', 'unknown')
            device_name = device_info.get('device_name', 'unknown')
            gpu_memory = device_info.get('gpu_memory_gb', 0)
            
            if 'out of memory' in str(exc).lower():
                error_msg = (
                    f"Out of memory error on {device_type} ({device_name}). "
                    f"Available GPU memory: {gpu_memory:.2f} GB. "
                    "Try reducing the audio length or using a smaller model."
                )
                raise ModelLoadError(
                    model_name=exc.model_name,
                    message=error_msg,
                    details=(
                        "The model requires more GPU memory than is available. "
                        "Try closing other applications, using a smaller audio file, "
                        "or running on CPU with use_ai_models=False."
                    ),
                ) from exc
            raise

        self._demucs_wrapper = demucs
        self._basic_pitch_wrapper = basic_pitch

        return demucs, basic_pitch

    def _process_monophonic(
        self,
        audio_data: AudioData,
        output_path: Path,
        result: PipelineResult,
    ) -> None:
        self._report_progress('pitch_detection', 0.1, 'Detecting pitch...')
        try:
            pitch_frames = self.pitch_detector.detect_pitch(audio_data)
            if not pitch_frames:
                raise ValueError("No pitch detected in audio")
            self._report_progress('pitch_detection', 0.33, 'Pitch detection complete')
        except Exception as e:
            logger.error(f"Pitch detection failed: {str(e)}", exc_info=True)
            raise ValueError(f"Pitch detection failed: {str(e)}")

        self._report_progress('note_segmentation', 0.4, 'Segmenting notes...')
        try:
            note_events = self.pitch_detector.segment_notes(
                pitch_frames,
                audio_data,
                min_note_duration=self.min_note_duration,
            )
            if not note_events:
                raise ValueError("No notes detected in audio")
            self._report_progress('note_segmentation', 0.5, 'Note segmentation complete')
        except Exception as e:
            logger.error(f"Note segmentation failed: {str(e)}", exc_info=True)
            raise ValueError(f"Note segmentation failed: {str(e)}")

        # Tempo detection stage
        tempo_info: Optional[TempoInfo] = None
        if self.detect_tempo and self.tempo_detector:
            self._report_progress('tempo_detection', 0.55, 'Detecting tempo...')
            try:
                tempo_info = self.tempo_detector.detect_tempo(audio_data)
                self.midi_generator.tempo = tempo_info.tempo
                result.detected_tempo = tempo_info.tempo
                result.beat_times = tempo_info.beat_times.tolist()
                logger.info(f"Detected tempo: {tempo_info.tempo:.1f} BPM")
                self._report_progress('tempo_detection', 0.6, 'Tempo detection complete')
            except Exception as e:
                logger.warning(f"Tempo detection failed: {str(e)}, using default tempo")
                tempo_info = None
        
        # Note filtering stage
        original_note_count = len(note_events)
        self._report_progress('note_filtering', 0.65, 'Filtering notes...')
        try:
            filtered_notes = self.note_filter.filter_notes(note_events)
            if original_note_count and not filtered_notes:
                logger.warning("Note filtering removed all notes; reverting to unfiltered results")
                filtered_notes = note_events
                filtered_count = 0
            else:
                filtered_count = original_note_count - len(filtered_notes)
            note_events = filtered_notes
            result.notes_filtered = filtered_count
            if original_note_count:
                logger.info(
                    "Filtered %d notes (%.1f%% removed)",
                    filtered_count,
                    (filtered_count / original_note_count * 100.0) if original_note_count else 0.0,
                )
            self._report_progress('note_filtering', 0.7, 'Note filtering complete')
        except Exception as e:
            logger.warning(f"Note filtering failed: {str(e)}, using unfiltered notes")
        
        # Quantization stage
        if self.quantization_enabled:
            self._report_progress('quantization', 0.75, 'Quantizing notes...')
            try:
                quantize_tempo = tempo_info.tempo if tempo_info else self.tempo
                self.note_quantizer = NoteQuantizer(
                    grid=self.quantization_grid,
                    tempo=quantize_tempo
                )
                if note_events:
                    quantized_notes = self.note_quantizer.quantize_notes(note_events)
                    if not quantized_notes:
                        logger.warning("Quantization removed all notes; keeping unquantized results")
                        quantized_notes = note_events
                    else:
                        result.quantization_applied = True
                        logger.info(
                            "Quantized %d notes to %s grid",
                            len(quantized_notes),
                            self.quantization_grid.name,
                        )
                    note_events = quantized_notes
                self._report_progress('quantization', 0.8, 'Note quantization complete')
            except Exception as e:
                logger.warning(f"Note quantization failed: {str(e)}, using unquantized notes")

        self._report_progress('midi_generation', 0.85, 'Generating MIDI...')
        try:
            midi_info = self.midi_generator.get_midi_info(note_events)
            output_path = self.midi_generator.create_midi(
                note_events=note_events,
                output_path=output_path,
            )
            self._report_progress('midi_generation', 0.95, 'MIDI generation complete')
            result.success = True
            result.output_path = output_path
            result.note_count = midi_info['note_count']
            result.duration = midi_info['duration']
            result.transcription_method = 'monophonic'
            result.separation_enabled = False
            result.stem_count = 1
            result.model_info = {}
        except MidiGenerationError as e:
            logger.error(f"MIDI generation failed: {str(e)}", exc_info=True)
            raise ValueError(f"MIDI generation failed: {str(e)}")

        self._report_progress('complete', 1.0, 'Conversion complete')

    def _process_with_ai(
        self,
        audio_data: AudioData,
        output_path: Path,
        result: PipelineResult,
    ) -> None:
        # Import DeviceManager here to avoid circular imports
        from ..models.device_manager import DeviceManager
        
        # Log device info at the start of processing
        device_info = DeviceManager.get_device_info()
        logger.info("Starting AI processing with device: %s", device_info)
        
        # Add device info to the result for diagnostics
        result.model_info['device_info'] = {
            'device_type': device_info['device_type'],
            'device_name': device_info['device_name'],
            'cuda_available': device_info['cuda_available'],
            'cuda_version': device_info['cuda_version'],
            'gpu_memory_gb': device_info['gpu_memory_gb']
        }
        
        # Initialize AI models with progress reporting
        self._report_progress('model_loading', 0.05, 'Initializing AI models...')
        try:
            demucs_wrapper, basic_pitch_wrapper = self._initialize_ai_models()
            if basic_pitch_wrapper is None:
                raise ValueError("Basic-Pitch model failed to initialize")
        except Exception as e:
            logger.error("Failed to initialize AI models: %s", str(e), exc_info=True)
            # Add more context to the error message
            error_msg = f"AI model initialization failed: {str(e)}"
            if 'out of memory' in str(e).lower():
                error_msg += (
                    "\n\nThis is likely due to insufficient GPU memory. "
                    f"Available: {device_info.get('gpu_memory_gb', 0):.2f} GB. "
                    "Try using a smaller audio file or running on CPU with use_ai_models=False."
                )
            raise RuntimeError(error_msg) from e

        if demucs_wrapper is not None:
            demucs_wrapper.ensure_model_loaded(
                lambda value, message: self._report_progress(
                    'model_loading',
                    0.05 + 0.25 * value,
                    f"Demucs: {message}"
                )
            )

        basic_pitch_wrapper.ensure_model_loaded(
            lambda value, message: self._report_progress(
                'model_loading',
                0.3 + 0.2 * value,
                f"Basic-Pitch: {message}"
            )
        )
        self._report_progress('model_loading', 0.5, 'AI models ready')

        midi_input: Dict[str, List[NoteEvent]] = {}
        stems: List[SeparatedStem] = []

        try:
            if self.enable_separation:
                if demucs_wrapper is None:
                    raise ValueError("Demucs model not available but separation was requested")
                    
                # Check memory before separation
                if hasattr(demucs_wrapper, 'estimate_memory_requirements'):
                    try:
                        req_mb = demucs_wrapper.estimate_memory_requirements(audio_data)
                        logger.info("Estimated memory required for separation: %.2f MB", req_mb)
                        
                        if device_info.get('gpu_memory_gb'):
                            available_mb = device_info['gpu_memory_gb'] * 1024  # Convert GB to MB
                            if req_mb > available_mb * 0.8:  # Use 80% threshold
                                logger.warning(
                                    "High memory usage warning: %.2f MB required (%.2f GB available). "
                                    "Separation may fail with out-of-memory error.",
                                    req_mb, device_info['gpu_memory_gb']
                                )
                    except Exception as e:
                        logger.warning("Could not estimate memory requirements: %s", str(e))
                
                self._report_progress('source_separation', 0.5, 'Separating sources with Demucs...')
                try:
                    stems = demucs_wrapper.separate(
                        audio_data,
                        progress_callback=lambda value, message: self._report_progress(
                            'source_separation',
                            0.5 + 0.2 * value,
                            message
                        ),
                    )
                except RuntimeError as e:
                    if 'out of memory' in str(e).lower():
                        error_msg = (
                            f"Out of GPU memory during source separation. "
                            f"Available: {device_info.get('gpu_memory_gb', 0):.2f} GB. "
                            "Try using a shorter audio file or disable separation."
                        )
                        raise RuntimeError(error_msg) from e
                    raise
                if not stems:
                    raise ValueError("Demucs returned no stems")
                result.separation_enabled = True
                result.stem_count = len(stems)
            else:
                stems = [SeparatedStem(
                    name='mix',
                    samples=audio_data.samples,
                    sample_rate=audio_data.metadata.sample_rate,
                )]
                result.separation_enabled = False
                result.stem_count = 1

            # Check memory before transcription
            if hasattr(basic_pitch_wrapper, 'estimate_memory_requirements'):
                try:
                    max_req_mb = 0
                    for stem in stems:
                        req_mb = basic_pitch_wrapper.estimate_memory_requirements(stem)
                        max_req_mb = max(max_req_mb, req_mb)
                    
                    logger.info("Estimated max memory required for transcription: %.2f MB", max_req_mb)
                    
                    if device_info.get('gpu_memory_gb'):
                        available_mb = device_info['gpu_memory_gb'] * 1024  # Convert GB to MB
                        if max_req_mb > available_mb * 0.8:  # Use 80% threshold
                            logger.warning(
                                "High memory usage warning: %.2f MB required (%.2f GB available). "
                                "Transcription may fail with out-of-memory error.",
                                max_req_mb, device_info['gpu_memory_gb']
                            )
                except Exception as e:
                    logger.warning("Could not estimate memory requirements: %s", str(e))
            
            self._report_progress('polyphonic_transcription', 0.7, 'Transcribing stems with Basic-Pitch...')
            
            # Process stems with memory monitoring
            stem_share = 0.2 / max(len(stems), 1)
            for index, stem in enumerate(stems):
                stem_start = 0.7 + stem_share * index
                stem_name = stem.name
                
                try:
                    transcription = basic_pitch_wrapper.transcribe_stem(
                        stem,
                        progress_callback=lambda value, message, stem_start=stem_start, stem_name=stem_name: self._report_progress(
                            'polyphonic_transcription',
                            min(0.9, stem_start + stem_share * value),
                            f"{stem_name}: {message}"
                        ),
                    )
                except RuntimeError as e:
                    if 'out of memory' in str(e).lower():
                        error_msg = (
                            f"Out of GPU memory during {stem_name} transcription. "
                            f"Available: {device_info.get('gpu_memory_gb', 0):.2f} GB. "
                            "Try using a shorter audio file or disable AI features."
                        )
                        raise RuntimeError(error_msg) from e
                    raise
                midi_input[stem_name] = transcription.note_events

            # Apply filtering and quantization to all stems
            total_filtered = 0
            quantization_applied = False
            
            # Tempo detection stage
            tempo_info: Optional[TempoInfo] = None
            if self.detect_tempo and self.tempo_detector:
                self._report_progress('tempo_detection', 0.92, 'Detecting tempo...')
                try:
                    tempo_info = self.tempo_detector.detect_tempo(audio_data)
                    self.midi_generator.tempo = tempo_info.tempo
                    result.detected_tempo = tempo_info.tempo
                    result.beat_times = tempo_info.beat_times.tolist()
                    logger.info(f"Detected tempo: {tempo_info.tempo:.1f} BPM")
                except Exception as e:
                    logger.warning(f"Tempo detection failed: {str(e)}, using default tempo")
                    tempo_info = None
            
            # Apply filtering and quantization to each stem
            for stem_name in midi_input:
                original_count = len(midi_input[stem_name])
                
                # Note filtering
                try:
                    midi_input[stem_name] = self.note_filter.filter_notes(midi_input[stem_name])
                    filtered_count = original_count - len(midi_input[stem_name])
                    total_filtered += filtered_count
                except Exception as e:
                    logger.warning(f"Note filtering failed for {stem_name}: {str(e)}")
                
                # Quantization
                if self.quantization_enabled:
                    try:
                        quantize_tempo = tempo_info.tempo if tempo_info else self.tempo
                        if not self.note_quantizer:
                            self.note_quantizer = NoteQuantizer(
                                grid=self.quantization_grid,
                                tempo=quantize_tempo
                            )
                        midi_input[stem_name] = self.note_quantizer.quantize_notes(midi_input[stem_name])
                        quantization_applied = True
                    except Exception as e:
                        logger.warning(f"Note quantization failed for {stem_name}: {str(e)}")
            
            result.notes_filtered = total_filtered
            result.quantization_applied = quantization_applied
            
            if quantization_applied:
                logger.info(f"Quantized all stems to {self.quantization_grid.name} grid")
            if total_filtered > 0:
                logger.info(f"Filtered {total_filtered} total notes across all stems")

            self._report_progress('midi_generation', 0.95, 'Generating multi-track MIDI (AI)...')
            output_path = self.midi_generator.create_multi_track_midi(midi_input, output_path)
            midi_info = self.midi_generator.get_midi_info(midi_input)

            result.success = True
            result.output_path = output_path
            result.note_count = midi_info['note_count']
            result.duration = midi_info['duration']
            result.transcription_method = 'polyphonic'
            result.model_info = {
                'demucs_model': demucs_wrapper.model_name if demucs_wrapper else None,
                'basic_pitch_model_path': str(getattr(basic_pitch_wrapper, 'model_path', None)) if getattr(basic_pitch_wrapper, 'model_path', None) else None,
                'basic_pitch_config': self.basic_pitch_config,
                'device': self._device_str or 'auto',
                'models_cache_dir': str(self.models_cache_dir) if self.models_cache_dir else None,
            }

            self._report_progress('complete', 1.0, 'AI conversion complete')
        except Exception as exc:
            logger.error("AI pipeline processing failed: %s", exc, exc_info=True)
            raise
    
    def _report_progress(self, stage: str, progress: float, message: str) -> None:
        """Report progress through the pipeline.
        
        Args:
            stage: Current processing stage.
            progress: Progress percentage (0.0 to 1.0).
            message: Human-readable status message.
        """
        # Clamp progress to [0, 1]
        progress = max(0.0, min(1.0, progress))
        
        # Log the progress
        logger.debug(f"[{stage.upper()}] {progress*100:.1f}% - {message}")
        
        # Call the progress callback if provided
        if self.progress_callback is not None:
            try:
                update = PipelineProgress(
                    stage=stage,
                    progress=progress,
                    message=message
                )
                self.progress_callback(update)
            except Exception as e:
                logger.warning(f"Progress callback failed: {str(e)}", exc_info=True)
