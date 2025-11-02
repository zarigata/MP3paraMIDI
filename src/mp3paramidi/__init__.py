"""
MP3paraMIDI - Audio to MIDI conversion tool with advanced features.
Created by Zarigata.

Features include:
- Note quantization with configurable grid sizes
- Automatic tempo detection using librosa beat tracking
- Enhanced note filtering to remove spurious detections
- MIDI preview playback with play/pause/stop controls
- Comprehensive settings for customizing conversion parameters
- Improved velocity detection based on audio amplitude analysis
- AI-powered instrument separation and polyphonic note detection
"""

__version__ = "0.1.0"
__author__ = "Zarigata"

# Import main components lazily to avoid mandatory optional dependencies
__all__ = [
    'MainWindow',
    'AudioToMidiPipeline',
    'PipelineResult',
    'MidiGenerator',
    'NoteQuantizer',
    'MidiPlayer'
]


def __getattr__(name: str):
    """Provide lazy attribute access for top-level package exports."""
    if name == 'MainWindow':
        from .gui import MainWindow  # type: ignore
        return MainWindow
    if name in {'AudioToMidiPipeline', 'PipelineResult'}:
        from .audio import AudioToMidiPipeline, PipelineResult  # type: ignore
        return {'AudioToMidiPipeline': AudioToMidiPipeline, 'PipelineResult': PipelineResult}[name]
    if name in {'MidiGenerator', 'NoteQuantizer', 'MidiPlayer'}:
        from .midi import MidiGenerator, NoteQuantizer, MidiPlayer  # type: ignore
        return {
            'MidiGenerator': MidiGenerator,
            'NoteQuantizer': NoteQuantizer,
            'MidiPlayer': MidiPlayer,
        }[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
