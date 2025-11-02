"""Audio file generation utilities for testing."""

import os
import random
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import soundfile as sf
from pydub import AudioSegment


def generate_sine_wave(
    frequency: float = 440.0,
    duration: float = 1.0,
    sample_rate: int = 44100,
    channels: int = 1,
) -> np.ndarray:
    """Generate a sine wave audio signal.
    
    Args:
        frequency: Frequency of the sine wave in Hz.
        duration: Duration in seconds.
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels (1 for mono, 2 for stereo).
        
    Returns:
        numpy.ndarray: Audio samples as float32 in [-1, 1].
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    signal = np.sin(2 * np.pi * frequency * t)
    
    # Normalize to prevent clipping
    signal = signal.astype(np.float32) * 0.9
    
    # Convert to stereo if needed
    if channels == 2:
        signal = np.column_stack((signal, signal * 0.8))  # Slightly different amplitude for stereo
       
    return signal


def create_test_wav(
    output_path: Optional[Union[str, Path]] = None,
    frequency: float = 440.0,
    duration: float = 0.1,  # Short duration for tests
    sample_rate: int = 44100,
    channels: int = 1,
) -> Path:
    """Create a test WAV file.
    
    Args:
        output_path: Path to save the WAV file. If None, creates a temporary file.
        frequency: Frequency of the test tone in Hz.
        duration: Duration in seconds.
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels.
        
    Returns:
        Path to the created WAV file.
    """
    # Generate test signal
    signal = generate_sine_wave(frequency, duration, sample_rate, channels)
    
    # Create output path if not provided
    if output_path is None:
        fd, temp_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        output_path = Path(temp_path)
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save as WAV
    sf.write(str(output_path), signal, sample_rate, 'FLOAT')
    return output_path


def create_test_mp3(
    output_path: Optional[Union[str, Path]] = None,
    frequency: float = 440.0,
    duration: float = 0.1,  # Short duration for tests
    sample_rate: int = 44100,
    channels: int = 1,
) -> Optional[Path]:
    """Create a test MP3 file using pydub.
    
    Args:
        output_path: Path to save the MP3 file. If None, creates a temporary file.
        frequency: Frequency of the test tone in Hz.
        duration: Duration in seconds.
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels.
        
    Returns:
        Path to the created MP3 file, or None if FFmpeg is not available.
    """
    # Check if FFmpeg is available
    try:
        AudioSegment.converter = "ffmpeg"  # Use system FFmpeg
        AudioSegment.ffmpeg = "ffmpeg"
        AudioSegment.ffprobe = "ffprobe"
        
        # Create a temporary WAV file first
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
        
        try:
            # Create WAV file
            create_test_wav(
                output_path=temp_wav_path,
                frequency=frequency,
                duration=duration,
                sample_rate=sample_rate,
                channels=channels
            )
            
            # Create output path if not provided
            if output_path is None:
                fd, temp_path = tempfile.mkstemp(suffix='.mp3')
                os.close(fd)
                output_path = Path(temp_path)
            else:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to MP3
            audio = AudioSegment.from_wav(temp_wav_path)
            audio.export(str(output_path), format='mp3', bitrate='192k')
            
            return output_path
            
        finally:
            # Clean up temporary WAV file
            if os.path.exists(temp_wav_path):
                os.unlink(temp_wav_path)
                
    except Exception as e:
        print(f"Warning: Could not create test MP3 (FFmpeg may not be available): {e}")
        return None


def create_corrupted_file(output_path: Optional[Union[str, Path]] = None) -> Path:
    """Create a corrupted audio file for testing error handling.
    
    Args:
        output_path: Path to save the corrupted file. If None, creates a temporary file.
        
    Returns:
        Path to the created file.
    """
    if output_path is None:
        fd, temp_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        output_path = Path(temp_path)
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write random bytes to create a corrupted file
    with open(output_path, 'wb') as f:
        f.write(os.urandom(1024))  # 1KB of random data
    
    return output_path
