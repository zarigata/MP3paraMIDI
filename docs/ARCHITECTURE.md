# MP3paraMIDI Architecture Guide

## Overview
MP3paraMIDI is a cross-platform desktop application built with **PyQt6** that converts audio files (MP3 or WAV) into MIDI. The architecture follows a layered design that separates the GUI, background worker threads, audio processing pipeline, and MIDI generation. Optional AI models extend the conversion quality while keeping the system modular and maintainable.

## System Architecture Diagram
```mermaid
graph LR
    GUI[GUI Layer\n(MainWindow, Dialogs, Widgets)] --> Worker[Worker Thread Layer\n(ConversionWorker, Signals)]
    Worker --> Pipeline[Processing Layer\n(AudioToMidiPipeline)]
    Pipeline --> Audio[Audio Module]
    Pipeline --> Midi[MIDI Module]
    Pipeline --> Models[AI Models]
```

## Core Components

### Audio Module — `src/mp3paramidi/audio/`
- **AudioLoader** (`audio/loader.py`): Detects FFmpeg, loads MP3/WAV files via librosa or pydub, normalizes audio data.
- **PitchDetector** (`audio/pitch_detector.py`): Runs monophonic detection with `librosa.pyin`, manages note segmentation and velocity estimation.
- **TempoDetector** (`audio/tempo_detector.py`): Uses `librosa.beat.beat_track` to infer BPM and beat positions with confidence scoring.
- **NoteFilter** (`audio/note_filter.py`): Filters notes based on confidence, duration, velocity, and statistical outlier analysis.
- **AudioToMidiPipeline** (`audio/pipeline.py`): Orchestrates the conversion flow, supports monophonic and AI-enhanced pipelines, exposes progress callbacks, and aggregates results.

### MIDI Module — `src/mp3paramidi/midi/`
- **MidiGenerator** (`midi/generator.py`): Builds MIDI files using pretty_midi, handles multi-track output, instrument mapping, and metadata.
- **NoteQuantizer** (`midi/quantizer.py`): Provides grid-based timing correction (quarter through thirty-second notes) with tempo-aware quantization.
- **MidiPlayer** (`midi/playback.py`): Wraps pygame for playback with play/pause/stop, volume, and position tracking.

### Models Module — `src/mp3paramidi/models/`
- **DeviceManager** (`models/device_manager.py`): Detects GPU/CPU capabilities using PyTorch, manages memory checks, and chooses execution device.
- **DemucsWrapper** (`models/demucs_wrapper.py`): Downloads and caches Meta’s Demucs model, performs source separation into stems, streams audio chunks to manage memory.
- **BasicPitchWrapper** (`models/basic_pitch_wrapper.py`): Interfaces with Spotify’s Basic-Pitch for polyphonic transcription, exposes sensitivity/threshold configuration, converts events to the internal note format.

### GUI Module — `src/mp3paramidi/gui/`
- **MainWindow** (`gui/main_window.py`): Central application window; manages menus, status bar, settings, file list, and integrates playback controls.
- **FileDropWidget** (`gui/file_drop_widget.py`): Drag-and-drop interface for loading audio files, displays queue status, and triggers conversions.
- **SettingsDialog** (`gui/settings_dialog.py`): Tabbed configuration UI using QSettings for persistence across sessions.
- **PlaybackWidget** (`gui/playback_widget.py`): Provides transport controls and visual feedback for converted MIDI files.
- **ConversionWorker** (`gui/workers.py`): Runs the pipeline on a `QThread`, emits progress/status/error signals, and handles lifecycle management.

## Data Flow
1. **Load Files:** Users drag-and-drop audio or use the file dialog; `AudioLoader` validates and creates `AudioData` objects.
2. **Start Conversion:** MainWindow instantiates `ConversionWorker` with current `ConversionConfig` and moves it to a background thread.
3. **Pipeline Execution:**
   - Load and preprocess audio
   - Optional tempo detection
   - Pitch detection (monophonic or AI-assisted)
   - Note filtering and optional quantization
   - MIDI generation and saving
4. **Progress Reporting:** Worker emits Qt signals (percentage, stage messages, errors) consumed by the GUI.
5. **Result Handling:** On completion, MIDI paths return to MainWindow; PlaybackWidget loads the result for preview.

## Threading Model
- GUI operations stay on the main thread (Qt event loop).
- `ConversionWorker` runs on a dedicated `QThread`, ensuring lengthy processing does not freeze the UI.
- Communication uses Qt signals/slots for thread-safe updates, with cleanup performed when the worker finishes or the conversion is canceled.

## AI Model Integration
- AI features are optional and configured via Settings.
- On first use, Demucs and Basic-Pitch models download to `models/` and are cached for subsequent runs.
- **Demucs** separates stems (vocals, drums, bass, other) for higher-fidelity MIDI generation.
- **Basic-Pitch** transcribes polyphonic content per stem or full mix, providing note onset/offset/pitch/velocity data.
- GPU acceleration is enabled via PyTorch when available; CPU fallback ensures broad compatibility.

## Configuration and Settings
- **QSettings** stores user preferences per platform (registry on Windows, plist on macOS, INI on Linux).
- `SettingsData` and `ConversionConfig` (defined in `gui/settings_data.py` or related modules) enforce type safety and encapsulate runtime options.
- Adjusted settings apply to subsequent conversions, maintaining reproducibility between runs.

## Error Handling
- Custom exception hierarchy (e.g., `AudioLoadError`, `ModelError`, `ConversionError`) communicates issues clearly.
- GUI surfaces user-friendly dialogs while logging detailed traces for debugging.
- Graceful degradation ensures conversions continue even if optional components (FFmpeg, AI models) are unavailable.

## Testing Strategy
- **Unit Tests:** Validate audio processing, MIDI generation, and utility modules (`tests/audio/`, `tests/midi/`).
- **Integration Tests:** Exercise end-to-end pipeline scenarios and edge cases.
- **GUI Tests:** Use `pytest-qt` to verify widgets, signals, and dialogs.
- **Fixtures:** `tests/fixtures/audio_generators.py` provides synthetic audio for deterministic testing.
- **Build Validation:** Scripts ensure PyInstaller packaging works across platforms.

## Performance Considerations
- Audio analysis and AI inference are CPU/GPU intensive; worker threads keep the GUI responsive.
- Demucs requires 2–4 GB RAM; segmenting reduces peak memory usage.
- Model caching avoids repeated downloads; progress callbacks provide continuous feedback.

## Extension Points
- Additional audio formats (FLAC, OGG, AAC) via extended loader modules.
- Alternative AI models (CREPE, Omnizart, Spleeter) integrated through new wrappers.
- Batch or parallel processing strategies for large collections.
- DAW integration via plugin architecture or OSC/MIDI routing.
- Enhanced MIDI editing UI or post-processing filters.

## Dependencies
- **PyQt6:** GUI framework and event loop.
- **librosa, numpy, scipy:** Audio analysis and signal processing.
- **pretty_midi:** MIDI file creation and manipulation.
- **pygame:** MIDI playback with cross-platform support.
- **torch, demucs, basic-pitch:** Optional AI-based transcription and separation.
- **soundfile, pydub:** Audio I/O and format handling.

## Build and Packaging
- Packaging is handled with PyInstaller specs in `build_configs/`.
- Icons generated via platform scripts (`tools/build_icons.{sh,ps1}`).
- Platform-specific packaging instructions reside in [docs/BUILDING.md](BUILDING.md).

## References
- Core pipeline: `src/mp3paramidi/audio/pipeline.py`
- Main window UI: `src/mp3paramidi/gui/main_window.py`
- Demucs integration: `src/mp3paramidi/models/demucs_wrapper.py`
- AI overview and model usage: [docs/AI_MODELS.md](AI_MODELS.md)

For additional information, explore the source files referenced above or open a discussion in the repository. Contributions that expand or refine this architecture are welcome!
