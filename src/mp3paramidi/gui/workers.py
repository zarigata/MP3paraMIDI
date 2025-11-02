"""
Background workers for the MP3paraMIDI GUI.

This module provides worker classes that run in separate threads to perform
long-running tasks without freezing the GUI.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ..audio import AudioData, AudioToMidiPipeline, PipelineResult, PipelineProgress
from ..models.exceptions import ModelDownloadError, ModelLoadError, InferenceError

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class ConversionConfig:
    """Configuration for audio-to-MIDI conversion."""
    fmin: str = 'C2'  # Minimum frequency or note name
    fmax: str = 'C7'  # Maximum frequency or note name
    tempo: float = 120.0  # Tempo in BPM
    min_note_duration: float = 0.05  # Minimum note duration in seconds
    output_dir: Optional[Path] = None  # Optional custom output directory
    use_ai_models: bool = False
    enable_separation: bool = False
    demucs_model: str = "htdemucs"
    basic_pitch_config: Optional[Dict[str, Any]] = None
    device: Optional[str] = None
    models_cache_dir: Optional[Path] = None
    # New settings for advanced features
    detect_tempo: bool = True
    quantization_enabled: bool = False
    quantization_grid: str = 'SIXTEENTH'  # Stored as string for serialization
    filter_config: Optional[Dict[str, Any]] = None
    sensitivity_preset: str = 'balanced'


class ConversionWorker(QObject):
    """Worker for converting audio files to MIDI in a background thread.
    
    Signals:
        progress: Emitted with (percentage, message) during conversion.
        file_completed: Emitted when a file is processed (file_path, result).
        all_completed: Emitted when all files are processed (success_count, error_count).
        error: Emitted when an error occurs (file_path, error_message).
        finished: Emitted when the worker has finished all processing.
    """
    
    # Signals
    progress = pyqtSignal(int, str)  # percentage (0-100), message
    file_completed = pyqtSignal(str, object)  # file_path (as string), PipelineResult
    all_completed = pyqtSignal(int, int)  # success_count, error_count
    error = pyqtSignal(str, str)  # file_path (as string), error_message
    finished = pyqtSignal()
    model_download_progress = pyqtSignal(str, int)  # model_name, progress_percentage
    
    def __init__(
        self,
        audio_data_list: List[AudioData],
        config: Dict[str, Any],
        parent: Optional[QObject] = None
    ) -> None:
        """Initialize the worker.
        
        Args:
            audio_data_list: List of AudioData objects to process.
            config: Configuration dictionary with keys:
                - fmin: Minimum frequency or note name (default: 'C2')
                - fmax: Maximum frequency or note name (default: 'C7')
                - tempo: Tempo in BPM (default: 120.0)
                - min_note_duration: Minimum note duration in seconds (default: 0.05)
                - output_dir: Optional custom output directory
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.audio_data_list = audio_data_list
        self.config = ConversionConfig(**config)
        self.is_cancelled = False
    
    @pyqtSlot()
    def run(self) -> None:
        """Process all audio files in the background.
        
        This method runs in a separate thread and processes each audio file
        sequentially, emitting signals to report progress and results.
        """
        success_count = 0
        error_count = 0
        
        try:
            total_files = len(self.audio_data_list)
            
            for i, audio_data in enumerate(self.audio_data_list, 1):
                if self.is_cancelled:
                    logger.info("Conversion cancelled by user")
                    break
                
                # Get file path as Path object or default to unknown
                file_path = Path(audio_data.metadata.file_path) if audio_data.metadata.file_path else Path("<unknown>")
                display_name = file_path.name if file_path.name != "<unknown>" else "<unknown>"
                
                try:
                    # Update progress
                    progress_percent = int((i - 1) / total_files * 100)
                    self.progress.emit(
                        progress_percent,
                        f"Processing {display_name}..."
                    )
                    
                    # Determine output path
                    if self.config.output_dir:
                        output_dir = self.config.output_dir
                    else:
                        output_dir = file_path.parent
                    
                    # Create output filename with .mid extension
                    if str(file_path) == "<unknown>":
                        output_path = Path("output.mid")
                    else:
                        output_path = file_path.with_suffix('.mid')
                    
                    # If output directory is specified, use it
                    if self.config.output_dir:
                        output_path = self.config.output_dir / output_path.name
                    
                    # Create and configure the pipeline
                    # Convert quantization grid string to enum
                    from ..midi.quantizer import QuantizationGrid
                    quantization_grid_enum = QuantizationGrid[self.config.quantization_grid]
                    
                    # Create filter config if provided
                    from ..audio.note_filter import FilterConfig
                    filter_config_obj = None
                    if self.config.filter_config:
                        filter_config_obj = FilterConfig(**self.config.filter_config)
                    
                    pipeline = AudioToMidiPipeline(
                        fmin=self.config.fmin,
                        fmax=self.config.fmax,
                        tempo=self.config.tempo,
                        min_note_duration=self.config.min_note_duration,
                        progress_callback=self._create_progress_callback(i, total_files),
                        use_ai_models=self.config.use_ai_models,
                        enable_separation=self.config.enable_separation,
                        demucs_model=self.config.demucs_model,
                        basic_pitch_config=self.config.basic_pitch_config or {},
                        device=self.config.device,
                        models_cache_dir=self.config.models_cache_dir,
                        # New parameters
                        detect_tempo=self.config.detect_tempo,
                        quantization_enabled=self.config.quantization_enabled,
                        quantization_grid=quantization_grid_enum,
                        filter_config=filter_config_obj,
                    )
                    
                    # Process the audio file with error handling for AI models
                    try:
                        result = pipeline.process(audio_data, output_path)
                        
                        # Emit the result
                        if result.success:
                            success_count += 1
                            self.file_completed.emit(display_name, result)
                        else:
                            error_count += 1
                            self.error.emit(display_name, result.error_message or "Unknown error")
                            
                    except ModelDownloadError as e:
                        error_count += 1
                        error_msg = (
                            f"Failed to download AI model: {str(e)}\n\n"
                            "This may be due to network connectivity issues.\n"
                            "Please check your internet connection and try again."
                        )
                        logger.error(f"Model download error: {str(e)}", exc_info=True)
                        self.error.emit(display_name, error_msg)
                        
                    except ModelLoadError as e:
                        error_count += 1
                        error_msg = (
                            f"Failed to load AI model: {str(e)}\n\n"
                            "The model files may be corrupted.\n"
                            "Try deleting the model cache and restarting the application."
                        )
                        logger.error(f"Model load error: {str(e)}", exc_info=True)
                        self.error.emit(display_name, error_msg)
                        
                    except InferenceError as e:
                        error_count += 1
                        error_msg = (
                            f"AI model error: {str(e)}\n\n"
                            "This may be due to insufficient system resources.\n"
                            "Try closing other applications or using a smaller audio file."
                        )
                        logger.error(f"Inference error: {str(e)}", exc_info=True)
                        self.error.emit(display_name, error_msg)
                    
                except Exception as e:
                    error_count += 1
                    error_msg = str(e) or "Unknown error"
                    logger.error(f"Error processing {file_path}: {error_msg}", exc_info=True)
                    self.error.emit(display_name, error_msg)
                
                # Check for cancellation between files
                if self.is_cancelled:
                    logger.info("Conversion cancelled by user")
                    break
            
            # Emit final results
            self.all_completed.emit(success_count, error_count)
            
        except Exception as e:
            logger.error(f"Unexpected error in worker thread: {str(e)}", exc_info=True)
            self.error.emit("<unknown>", f"Unexpected error: {str(e)}")
        finally:
            # Ensure finished signal is always emitted
            self.finished.emit()
    
    def _create_progress_callback(self, file_index: int, total_files: int) -> Callable[[PipelineProgress], None]:
        """Create a progress callback function for the pipeline.
        
        Args:
            file_index: 1-based index of the current file.
            total_files: Total number of files to process.
            
        Returns:
            A function that can be passed to AudioToMidiPipeline.
        """
        if self.config.use_ai_models:
            stage_order = [
                'loading',
                'model_loading',
                'model_download',
                'source_separation',
                'polyphonic_transcription',
                'tempo_detection',
                'note_filtering',
                'quantization',
                'midi_generation',
                'saving',
                'complete',
            ]
            stage_weights = {
                'loading': 5,
                'model_loading': 15,
                'model_download': 0,
                'source_separation': 25,
                'polyphonic_transcription': 25,
                'tempo_detection': 5,
                'note_filtering': 5,
                'quantization': 5,
                'midi_generation': 10,
                'saving': 5,
                'complete': 0,
            }
        else:
            stage_order = [
                'loading',
                'pitch_detection',
                'note_segmentation',
                'tempo_detection',
                'note_filtering',
                'quantization',
                'midi_generation',
                'saving',
                'complete',
            ]
            stage_weights = {
                'loading': 5,
                'pitch_detection': 15,
                'note_segmentation': 15,
                'tempo_detection': 5,
                'note_filtering': 5,
                'quantization': 5,
                'midi_generation': 40,
                'saving': 5,
                'complete': 5,
            }

        cumulative_weights: Dict[str, float] = {}
        cumulative = 0.0
        for stage in stage_order:
            cumulative_weights[stage] = cumulative
            cumulative += stage_weights.get(stage, 0)
        
        def callback(progress: PipelineProgress) -> None:
            if self.is_cancelled:
                return
            
            # Handle model download progress
            if progress.stage == 'model_download':
                model_name = progress.message.split(':')[0] if ':' in progress.message else 'model'
                self.model_download_progress.emit(model_name, int(progress.progress * 100))
                return
                
            # Calculate progress within the current stage
            stage_weight = stage_weights.get(progress.stage, 0)
            stage_progress = progress.progress * stage_weight / 100
            
            # Calculate overall progress (0-100)
            file_progress = (file_index - 1) / total_files * 100  # Progress of previous files (0 to 100)
            current_file_progress = (cumulative_weights.get(progress.stage, 0) + stage_progress) / total_files
            overall_progress = int(file_progress + current_file_progress)
            
            # Emit progress update with stage context
            stage_label = progress.stage.replace('_', ' ').title()
            self.progress.emit(overall_progress, f"[{stage_label}] {progress.message}")
        
        return callback
        
    def _handle_model_download(self, model_name: str, progress: int) -> None:
        """Handle model download progress updates.
        
        Args:
            model_name: Name of the model being downloaded
            progress: Download progress percentage (0-100)
        """
        self.progress.emit(
            -1,  # Special value to indicate indeterminate progress
            f"Downloading {model_name} model: {progress}%"
        )
        
        return callback
    
    @pyqtSlot()
    def cancel(self) -> None:
        """Request cancellation of the current conversion."""
        self.is_cancelled = True
