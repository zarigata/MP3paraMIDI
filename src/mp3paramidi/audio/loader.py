"""Audio loading and processing utilities for MP3paraMIDI."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

import librosa
import numpy as np
import soundfile as sf
from pydub import AudioSegment

from .exceptions import (
    AudioLoadError,
    CorruptedFileError,
    FFmpegNotFoundError,
    FileNotFoundError,
    InvalidAudioDataError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)

# Type aliases
NpFloatArray = np.ndarray  # Shape: (n_samples,) or (n_samples, n_channels)


@dataclass
class AudioMetadata:
    """Metadata for an audio file."""
    duration: float  # in seconds
    sample_rate: int  # in Hz
    channels: int  # 1 for mono, 2 for stereo
    bit_depth: Optional[int] = None  # bits per sample, if known
    format: Optional[str] = None  # 'MP3', 'WAV', etc.


@dataclass
class AudioData:
    """Container for audio samples and metadata."""
    file_path: Path
    samples: NpFloatArray  # float32 in [-1, 1], shape (n_samples,) or (n_samples, n_channels)
    metadata: AudioMetadata

    @property
    def duration_samples(self) -> int:
        """Get the duration in samples."""
        return len(self.samples)


class FFmpegDetector:
    """Detects and configures FFmpeg for audio processing."""
    
    @staticmethod
    def find_ffmpeg() -> Optional[str]:
        """Find FFmpeg binary in system PATH or common locations."""
        # Check common environment variables first
        for var in ['FFMPEG_BINARY', 'IMAGEIO_FFMPEG_EXE']:
            if var in os.environ and os.path.isfile(os.environ[var]):
                return os.environ[var]
        
        # Check system PATH
        ffmpeg_exe = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
        return shutil.which(ffmpeg_exe)
    
    @staticmethod
    def is_available() -> bool:
        """Check if FFmpeg is installed and working."""
        ffmpeg_path = FFmpegDetector.find_ffmpeg()
        if not ffmpeg_path:
            return False
            
        try:
            # Try to get version info
            result = subprocess.run(
                [ffmpeg_path, '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                check=True,
                text=True
            )
            return 'ffmpeg version' in result.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    @classmethod
    def configure_pydub(cls) -> bool:
        """Configure pydub to use the detected FFmpeg binary."""
        ffmpeg_path = cls.find_ffmpeg()
        if not ffmpeg_path:
            return False
            
        AudioSegment.converter = str(ffmpeg_path)
        return True


class AudioValidator:
    """Validates audio files and their metadata."""
    
    SUPPORTED_EXTENSIONS = {'.mp3', '.wav'}
    
    @classmethod
    def is_supported_extension(cls, path: Union[str, Path]) -> bool:
        """Check if the file extension is supported (case-insensitive)."""
        return Path(path).suffix.lower() in cls.SUPPORTED_EXTENSIONS
    
    @staticmethod
    def validate_file_exists(path: Union[str, Path]) -> None:
        """Raise FileNotFoundError if the file doesn't exist."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
    
    @staticmethod
    def validate_metadata(metadata: AudioMetadata, file_path: Optional[Path] = None) -> None:
        """Validate audio metadata.
        
        Args:
            metadata: The audio metadata to validate
            file_path: Optional file path to include in error messages
        """
        if metadata.duration <= 0:
            raise InvalidAudioDataError(
                file_path,
                f"Invalid duration: {metadata.duration} seconds"
            )
            
        if not (8000 <= metadata.sample_rate <= 192000):
            raise InvalidAudioDataError(
                file_path,
                f"Sample rate {metadata.sample_rate} Hz is outside valid range (8k-192k)"
            )
            
        if metadata.channels not in (1, 2):
            raise InvalidAudioDataError(
                file_path,
                f"Unsupported number of channels: {metadata.channels} (must be 1 or 2)"
            )


class AudioLoader:
    """Loads and validates audio files with support for multiple formats."""
    
    def __init__(self, preserve_stereo: bool = True, target_sample_rate: Optional[int] = None):
        """Initialize the audio loader.
        
        Args:
            preserve_stereo: If True, keeps stereo files as stereo. If False, converts to mono.
            target_sample_rate: If specified, resamples audio to this rate. If None, uses native rate.
        """
        self.preserve_stereo = preserve_stereo
        self.target_sample_rate = target_sample_rate
        
        # Configure pydub to use FFmpeg if available
        self._ffmpeg_available = FFmpegDetector.is_available()
        if self._ffmpeg_available:
            FFmpegDetector.configure_pydub()
    
    def load(self, file_path: Union[str, Path]) -> AudioData:
        """Load an audio file and return AudioData.
        
        Args:
            file_path: Path to the audio file.
            
        Returns:
            AudioData containing the loaded audio and metadata.
            
        Raises:
            FileNotFoundError: If the file doesn't exist.
            UnsupportedFormatError: If the file format is not supported.
            CorruptedFileError: If the file is corrupted or cannot be read.
            FFmpegNotFoundError: If FFmpeg is required but not found.
        """
        file_path = Path(file_path).resolve()
        logger.info(f"Loading audio file: {file_path}")
        
        # Basic validation
        AudioValidator.validate_file_exists(file_path)
        
        if not AudioValidator.is_supported_extension(file_path):
            raise UnsupportedFormatError(
                file_path,
                f"Unsupported file extension: {file_path.suffix}"
            )
        
        # Determine format and load accordingly
        try:
            if file_path.suffix.lower() == '.wav':
                return self._load_wav(file_path)
            else:  # MP3
                return self._load_mp3(file_path)
        except Exception as e:
            if not isinstance(e, AudioLoadError):
                # Wrap unexpected errors
                raise CorruptedFileError(file_path, str(e)) from e
            raise
    
    def _load_wav(self, file_path: Path) -> AudioData:
        """Load a WAV file using librosa."""
        try:
            samples, sample_rate = librosa.load(
                str(file_path),
                sr=self.target_sample_rate,
                mono=not self.preserve_stereo,
                dtype=np.float32
            )
            
            # Handle channel orientation: librosa returns (channels, n_samples) for multi-channel
            if samples.ndim == 2 and samples.shape[0] == 2:  # If (2, n_samples)
                samples = samples.T  # Convert to (n_samples, 2)
            
            # Get metadata
            with sf.SoundFile(str(file_path)) as snd_file:
                duration = len(snd_file) / snd_file.samplerate
                
                # Map soundfile subtypes to bit depths
                subtype = snd_file.subtype
                if 'PCM_16' in subtype:
                    bit_depth = 16
                elif 'PCM_24' in subtype:
                    bit_depth = 24
                elif 'PCM_32' in subtype:
                    bit_depth = 32
                elif 'PCM_U8' in subtype or 'PCM_S8' in subtype:
                    bit_depth = 8
                elif 'FLOAT' in subtype:
                    bit_depth = 32
                elif 'DOUBLE' in subtype:
                    bit_depth = 64
                else:
                    bit_depth = None
            
            # Derive channels from samples shape
            channels = 1 if samples.ndim == 1 else samples.shape[1]
            
            metadata = AudioMetadata(
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=bit_depth,
                format='WAV'
            )
            
            AudioValidator.validate_metadata(metadata, file_path=file_path)
            
            return AudioData(
                file_path=file_path,
                samples=samples,
                metadata=metadata
            )
            
        except (librosa.util.exceptions.ParameterError, sf.LibsndfileError) as e:
            raise CorruptedFileError(file_path, str(e)) from e
    
    def _load_mp3(self, file_path: Path) -> AudioData:
        """Load an MP3 file, trying librosa first, then pydub as fallback."""
        if not self._ffmpeg_available:
            raise FFmpegNotFoundError(file_path)
        
        # Try librosa first
        try:
            samples, sample_rate = librosa.load(
                str(file_path),
                sr=self.target_sample_rate,
                mono=not self.preserve_stereo,
                dtype=np.float32
            )
            
            # Handle channel orientation: librosa returns (channels, n_samples) for multi-channel
            if samples.ndim == 2 and samples.shape[0] == 2:  # If (2, n_samples)
                samples = samples.T  # Convert to (n_samples, 2)
            
            # Get duration and channels from samples
            duration = len(samples) / sample_rate
            channels = 1 if samples.ndim == 1 else samples.shape[1]
            
            metadata = AudioMetadata(
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=None,  # MP3 doesn't have a fixed bit depth
                format='MP3'
            )
            
            AudioValidator.validate_metadata(metadata, file_path=file_path)
            
            return AudioData(
                file_path=file_path,
                samples=samples,
                metadata=metadata
            )
            
        except (librosa.util.exceptions.ParameterError, sf.LibsndfileError) as e:
            logger.warning(f"librosa failed to load {file_path}, falling back to pydub: {e}")
            return self._load_mp3_with_pydub(file_path)
    
    def _load_mp3_with_pydub(self, file_path: Path) -> AudioData:
        """Fallback MP3 loader using pydub."""
        if not self._ffmpeg_available:
            raise FFmpegNotFoundError(file_path)
        
        try:
            # Load with pydub
            audio = AudioSegment.from_file(str(file_path))
            
            # Convert to target sample rate if needed
            if self.target_sample_rate and audio.frame_rate != self.target_sample_rate:
                audio = audio.set_frame_rate(self.target_sample_rate)
            
            # Convert to mono if needed
            if not self.preserve_stereo and audio.channels > 1:
                audio = audio.set_channels(1)
            
            # Convert to numpy array
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Reshape for multi-channel
            if audio.channels > 1:
                samples = samples.reshape(-1, audio.channels)
            
            # Normalize to [-1, 1] based on sample width
            max_val = 2 ** (8 * audio.sample_width - 1)
            samples = samples / max_val
            
            # Create metadata
            metadata = AudioMetadata(
                duration=len(audio) / 1000.0,  # pydub reports duration in ms
                sample_rate=audio.frame_rate,
                channels=audio.channels,
                bit_depth=audio.sample_width * 8,
                format='MP3'
            )
            
            AudioValidator.validate_metadata(metadata, file_path=file_path)
            
            return AudioData(
                file_path=file_path,
                samples=samples,
                metadata=metadata
            )
            
        except Exception as e:
            raise CorruptedFileError(file_path, str(e)) from e
