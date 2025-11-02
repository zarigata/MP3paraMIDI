# MP3paraMIDI

**Transform Audio to MIDI with Advanced Features**

**Created by Zarigata**

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows | macOS | Linux](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/zarigata/mp3paramidi)

## Description

MP3paraMIDI is a cross-platform application that converts MP3 and WAV audio files into MIDI format with advanced features including note quantization, automatic tempo detection, enhanced filtering, and MIDI playback. It features both monophonic pitch detection using the pYIN algorithm and optional polyphonic detection using AI models, with background processing to keep the UI responsive. All processing happens 100% locally on your machine with no cloud dependencies.

## ✨ Features

### Core Features
- 🖥️ **Cross-platform** - Works on Windows, macOS, and Linux
- 🎛️ **User-friendly GUI** - Simple interface with progress tracking and comprehensive settings
- 🎵 **Monophonic Pitch Detection** - Accurate note detection using librosa's pYIN algorithm
- 🤖 **AI-Powered Polyphonic Detection** - Optional Basic-Pitch model for complex music
- 🎼 **Source Separation** - Optional Demucs model for isolating instruments
- ⏱️ **Automatic Note Segmentation** - Detects note onsets and durations
- 🎹 **MIDI Export** - Saves as standard MIDI files with proper timing and velocity
- 🔄 **Background Processing** - Conversion happens in a separate thread to keep the UI responsive
- 🔒 **100% Local Processing** - No audio data leaves your computer
- 🆓 **Free & Open Source** - MIT Licensed

### Advanced Features
- 📏 **Note Quantization** - Snap notes to musical grids (quarter, eighth, sixteenth, 32nd notes)
- 🥁 **Automatic Tempo Detection** - Detect BPM and beat positions using librosa beat tracking
- 🔍 **Enhanced Note Filtering** - Remove spurious detections with configurable filters
- 🎮 **MIDI Playback** - Preview converted MIDI files with play/pause/stop controls
- ⚙️ **Comprehensive Settings** - Customize all conversion parameters with persistent preferences
- 🎚️ **Improved Velocity Detection** - Enhanced amplitude analysis for more realistic dynamics
- 📊 **Conversion Statistics** - Track notes filtered, quantization applied, and tempo detected

## 🚀 Requirements

- Python 3.10 or 3.11
- FFmpeg (for MP3 support)
- pygame (for MIDI playback)
- Recommended: 4GB+ RAM for processing audio files
- Optional: GPU with 4GB+ VRAM for AI features

## 💻 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/zarigata/mp3paramidi.git
   cd mp3paramidi
   ```

2. **Install FFmpeg**
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

3. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   For AI features (optional):
   ```bash
   pip install -r requirements-ai.txt
   ```

   Note: On first run, AI models will be automatically downloaded (500MB-2GB).

## 🎮 Quick Start

1. Launch the application:
   ```bash
   python -m mp3paramidi
   ```
2. Load an audio file (MP3 or WAV) by dragging and dropping or using the Browse button
3. **Optional**: Open Settings (Ctrl+,) to configure advanced features:
   - Enable note quantization and select grid size
   - Turn on automatic tempo detection
   - Configure note filtering thresholds
   - Enable AI models for polyphonic detection
4. Click "Convert to MIDI" - the MIDI file will be saved alongside your input file
5. The conversion runs in the background with progress updates
6. Once complete, use the playback controls to preview your MIDI file

## ⚙️ Advanced Features

### Note Quantization
Snap detected notes to a musical grid for cleaner timing:
- **Quarter notes** - Basic rhythmic quantization
- **Eighth notes** - Medium precision
- **Sixteenth notes** - High precision (default)
- **Thirty-second notes** - Maximum precision
- **None** - Disable quantization

### Tempo Detection
Automatically detect the tempo and beat positions:
- Uses librosa's beat tracking algorithm
- Provides confidence scores
- Works with both monophonic and polyphonic audio
- Detected tempo is used for quantization if enabled

### Note Filtering
Remove spurious or unwanted note detections:
- **Confidence threshold** - Filter low-confidence notes
- **Duration threshold** - Remove very short notes
- **Velocity range** - Filter notes outside dynamic range
- **Outlier removal** - Remove pitch outliers using statistical analysis

### MIDI Playback
Preview your converted MIDI files:
- Play/pause/stop controls
- Volume adjustment
- Position scrubbing
- Real-time playback status

### Settings Management
All settings are automatically saved and persist between sessions:
- Access via Settings → Preferences (Ctrl+,)
- Reset to defaults available
- Settings stored in platform-specific locations

## 🛠️ Technology Stack

- **GUI**: PyQt6 with modern widgets and layouts
- **Audio Processing**: librosa, numpy, soundfile
- **MIDI**: pretty-midi for generation, pygame for playback
- **Pitch Detection**: librosa pYIN algorithm (monophonic), Basic-Pitch (polyphonic)
- **Source Separation**: Demucs for instrument isolation
- **Threading**: QThread for background processing
- **Settings**: QSettings for persistent configuration
- **Quantization**: Custom grid-based timing correction
- **Tempo Detection**: librosa beat tracking with confidence estimation
- **Filtering**: Statistical outlier detection and threshold-based filtering

## ⚠️ Limitations

### Core Limitations
- Monophonic detection works best with single-note melodies
- Complex polyphonic music requires AI models (optional)
- Best results with clean recordings of solo instruments or voice
- Tempo detection accuracy depends on rhythmic clarity
- Quantization may alter musical expression

### System Requirements
- AI features require significant RAM (4GB+ recommended)
- GPU acceleration requires CUDA-compatible GPU
- Large audio files may take considerable processing time

## 🛣️ Roadmap

### Completed Features ✅
- [x] Basic monophonic audio to MIDI conversion
- [x] Note quantization with configurable grids
- [x] Automatic tempo detection
- [x] Enhanced note filtering
- [x] MIDI playback functionality
- [x] Comprehensive settings management
- [x] AI-powered polyphonic detection
- [x] Source separation capabilities
- [x] Improved velocity detection
- [x] Cross-platform compatibility

### Future Features 🚧
- [ ] Batch processing of multiple files
- [ ] Real-time audio input conversion
- [ ] Advanced MIDI editing tools
- [ ] Support for more audio formats (FLAC, OGG)
- [ ] MusicXML export functionality
- [ ] Plugin support for DAW integration
- [ ] Cloud-based AI model options
- [ ] Mobile application
- [ ] Web-based interface
- [ ] Advanced audio visualization

## 💡 Usage Examples

### Basic Conversion
```python
from mp3paramidi.audio import AudioToMidiPipeline
from mp3paramidi.audio.loader import AudioLoader

# Load audio file
loader = AudioLoader()
audio_data = loader.load("my_song.wav")

# Create pipeline and convert
pipeline = AudioToMidiPipeline()
result = pipeline.process(audio_data, "output.mid")

if result.success:
    print(f"Conversion complete! MIDI saved to {result.output_path}")
else:
    print(f"Conversion failed: {result.error_message}")
```

### Advanced Features
```python
from mp3paramidi.audio import AudioToMidiPipeline
from mp3paramidi.audio.note_filter import FilterConfig
from mp3paramidi.midi.quantizer import QuantizationGrid

# Configure advanced features
filter_config = FilterConfig(
    min_confidence=0.5,
    min_duration=0.1,
    remove_outliers=True
)

pipeline = AudioToMidiPipeline(
    detect_tempo=True,
    quantization_enabled=True,
    quantization_grid=QuantizationGrid.SIXTEENTH,
    filter_config=filter_config
)

result = pipeline.process(audio_data, "advanced_output.mid")

print(f"Detected tempo: {result.detected_tempo} BPM")
print(f"Notes filtered: {result.notes_filtered}")
print(f"Quantization applied: {result.quantization_applied}")
```

### MIDI Playback
```python
from mp3paramidi.midi.playback import MidiPlayer
from pathlib import Path

# Create player and load MIDI
player = MidiPlayer()
player.load_midi(Path("output.mid"))

# Play with controls
player.play()
player.set_volume(0.8)

# Pause and resume
player.pause()
player.play()  # Resume

# Stop playback
player.stop()
```

## 🧪 Testing

The project includes comprehensive test coverage:
- Unit tests for all core modules
- Integration tests for advanced features
- GUI testing with pytest-qt
- Performance and memory usage tests

Run tests with:
```bash
# Basic tests
pytest tests/

# Including GUI tests
pytest tests/ --gui-tests

# Coverage report
pytest tests/ --cov=mp3paramidi
```

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Zarigata**

- GitHub: [@zarigata](https://github.com/zarigata)

## 🙏 Acknowledgments

- [librosa](https://librosa.org/) for the pYIN pitch detection algorithm
- [pretty_midi](https://github.com/craffel/pretty-midi) for MIDI file generation
