"""Custom exceptions for audio processing in MP3paraMIDI."""

from pathlib import Path
from typing import Optional


class AudioLoadError(Exception):
    """Base exception for all audio loading errors."""
    
    def __init__(self, file_path: Path, message: str):
        self.file_path = file_path
        self.message = message
        super().__init__(self.message)
        
    def __str__(self) -> str:
        return f"Failed to load {self.file_path}: {self.message}"


class UnsupportedFormatError(AudioLoadError):
    """Raised when an unsupported file format is encountered."""
    
    def __init__(self, file_path: Path, format: Optional[str] = None):
        message = f"Unsupported audio format: {format}" if format else "Unsupported audio format"
        super().__init__(file_path, message)


class CorruptedFileError(AudioLoadError):
    """Raised when a file appears to be corrupted or malformed."""
    
    def __init__(self, file_path: Path, details: str = "File may be corrupted or incomplete"):
        super().__init__(file_path, f"Corrupted audio file: {details}")


class FFmpegNotFoundError(AudioLoadError):
    """Raised when FFmpeg is required but not found."""
    
    def __init__(self, file_path: Path):
        super().__init__(
            file_path,
            "FFmpeg is required for MP3 support. Please install FFmpeg and ensure it's in your PATH."
        )


class InvalidAudioDataError(AudioLoadError):
    """Raised when loaded audio data fails validation."""
    
    def __init__(self, file_path: Path, details: str):
        super().__init__(file_path, f"Invalid audio data: {details}")


# Re-export FileNotFoundError for consistent error handling
FileNotFoundError = FileNotFoundError
