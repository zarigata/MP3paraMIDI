"""
MIDI file generation, quantization, and playback for MP3paraMIDI.

This package provides functionality for creating and working with MIDI files,
including note generation, quantization, tempo control, and playback capabilities.
"""

__all__ = [
    'MidiGenerator',
    'MidiGenerationError',
    'NoteQuantizer',
    'QuantizationGrid',
    'MidiPlayer',
    'PlaybackState',
    'PlaybackError'
]


def __getattr__(name: str):
    if name in {'MidiGenerator', 'MidiGenerationError'}:
        from .generator import MidiGenerator, MidiGenerationError  # type: ignore
        return {'MidiGenerator': MidiGenerator, 'MidiGenerationError': MidiGenerationError}[name]
    if name in {'NoteQuantizer', 'QuantizationGrid'}:
        from .quantizer import NoteQuantizer, QuantizationGrid  # type: ignore
        return {'NoteQuantizer': NoteQuantizer, 'QuantizationGrid': QuantizationGrid}[name]
    if name in {'MidiPlayer', 'PlaybackState', 'PlaybackError'}:
        from .playback import MidiPlayer, PlaybackState, PlaybackError  # type: ignore
        return {
            'MidiPlayer': MidiPlayer,
            'PlaybackState': PlaybackState,
            'PlaybackError': PlaybackError,
        }[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
