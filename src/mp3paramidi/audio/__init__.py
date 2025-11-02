"""Audio processing utilities for MP3paraMIDI."""

__all__ = [
    'AudioLoader',
    'AudioData',
    'AudioMetadata',
    'PitchDetector',
    'PitchFrame',
    'NoteEvent',
    'AudioToMidiPipeline',
    'PipelineResult',
    'PipelineProgress',
    'TempoDetector',
    'TempoInfo',
    'NoteFilter',
    'FilterConfig',
    'AudioLoadError',
    'UnsupportedFormatError',
    'FFmpegNotFoundError',
    'CorruptedFileError',
    'InvalidAudioDataError',
]


def __getattr__(name: str):
    if name in {'AudioLoader', 'AudioData', 'AudioMetadata'}:
        from .loader import AudioLoader, AudioData, AudioMetadata  # type: ignore
        return {
            'AudioLoader': AudioLoader,
            'AudioData': AudioData,
            'AudioMetadata': AudioMetadata,
        }[name]
    if name in {'PitchDetector', 'PitchFrame', 'NoteEvent'}:
        from .pitch_detector import PitchDetector, PitchFrame, NoteEvent  # type: ignore
        return {
            'PitchDetector': PitchDetector,
            'PitchFrame': PitchFrame,
            'NoteEvent': NoteEvent,
        }[name]
    if name in {'AudioToMidiPipeline', 'PipelineResult', 'PipelineProgress'}:
        from .pipeline import AudioToMidiPipeline, PipelineResult, PipelineProgress  # type: ignore
        return {
            'AudioToMidiPipeline': AudioToMidiPipeline,
            'PipelineResult': PipelineResult,
            'PipelineProgress': PipelineProgress,
        }[name]
    if name in {'TempoDetector', 'TempoInfo'}:
        from .tempo_detector import TempoDetector, TempoInfo  # type: ignore
        return {
            'TempoDetector': TempoDetector,
            'TempoInfo': TempoInfo,
        }[name]
    if name in {'NoteFilter', 'FilterConfig'}:
        from .note_filter import NoteFilter, FilterConfig  # type: ignore
        return {
            'NoteFilter': NoteFilter,
            'FilterConfig': FilterConfig,
        }[name]
    if name in {
        'AudioLoadError',
        'UnsupportedFormatError',
        'FFmpegNotFoundError',
        'CorruptedFileError',
        'InvalidAudioDataError',
    }:
        from .exceptions import (
            AudioLoadError,
            UnsupportedFormatError,
            FFmpegNotFoundError,
            CorruptedFileError,
            InvalidAudioDataError,
        )  # type: ignore
        return {
            'AudioLoadError': AudioLoadError,
            'UnsupportedFormatError': UnsupportedFormatError,
            'FFmpegNotFoundError': FFmpegNotFoundError,
            'CorruptedFileError': CorruptedFileError,
            'InvalidAudioDataError': InvalidAudioDataError,
        }[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
