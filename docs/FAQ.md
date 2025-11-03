# MP3paraMIDI Frequently Asked Questions

## General Questions
**Q: What is MP3paraMIDI?**  
A: MP3paraMIDI is a cross-platform desktop application that converts MP3 and WAV audio files into MIDI using signal processing and optional AI models. It was created by Zarigata.

**Q: Is MP3paraMIDI free?**  
A: Yes. The project is open source under the MIT License.

**Q: Which platforms are supported?**  
A: Windows, macOS, and Linux. Pre-built binaries are provided for each platform.

**Q: Do I need Python installed to use it?**  
A: No if you use the pre-built binaries. Yes if you run from source.

**Q: Is my audio sent to the cloud?**  
A: No. All processing happens locally on your device.

## Installation and Setup
**Q: How do I install MP3paraMIDI?**  
A: Download the latest release from GitHub or follow the source installation instructions in the README.

**Q: Why do I need FFmpeg?**  
A: FFmpeg handles MP3 decoding. WAV files work without it.

**Q: How do I install FFmpeg?**  
A: See platform-specific steps in the README (package manager or official installers).

**Q: Where are AI models stored?**  
A: Under the `models/` directory, downloaded automatically on first use.

**Q: How much disk space do I need?**  
A: ~500 MB for the application plus ~500 MB–2 GB for AI models if enabled.

## Usage
**Q: Which audio formats are supported?**  
A: MP3 and WAV. Additional formats are planned.

**Q: Can I convert multiple files at once?**  
A: Yes. Drag-drop or select multiple files; they are processed sequentially.

**Q: Where are MIDI files saved?**  
A: In the same directory as the input audio with a `.mid` extension.

**Q: How long does conversion take?**  
A: Typically 10–60 seconds per minute of audio depending on settings and hardware.

**Q: Can I preview MIDI output?**  
A: Yes. Use the built-in playback controls after conversion finishes.

## Features
**Q: What is the difference between monophonic and polyphonic modes?**  
A: Monophonic detects a single note at a time (melodies). Polyphonic detects chords and multiple instruments via AI.

**Q: When should I enable AI models?**  
A: For complex music, chords, or multi-instrument recordings.

**Q: What is source separation?**  
A: Demucs separates audio into stems (vocals, drums, bass, other) for multi-track MIDI output.

**Q: What is quantization?**  
A: Snapping notes to a rhythmic grid for cleaner timing.

**Q: How accurate is the conversion?**  
A: Accuracy depends on audio quality; clean recordings can achieve 80–95% accuracy.

## Troubleshooting
**Q: Conversion feels slow.**  
A: Use GPU acceleration, reduce audio quality, disable AI features, or enable monophonic mode.

**Q: I hit an out-of-memory error.**  
A: Close other apps, reduce Demucs segment duration, switch to CPU mode, or process shorter files.

**Q: AI models refuse to download.**  
A: Check network access, disk space, and firewall settings.

**Q: MIDI playback is silent.**  
A: Ensure system MIDI is configured (install a SoundFont on Linux/macOS). Verify pygame support.

**Q: Notes are missing or wrong.**  
A: Adjust sensitivity settings, try different presets, or use cleaner audio input.

**Q: The application will not start.**  
A: Verify system requirements, check Python version when running from source, and inspect logs for errors.

## Advanced
**Q: Can I use custom AI models?**  
A: Not yet, but the architecture allows future integrations.

**Q: Can I edit MIDI inside MP3paraMIDI?**  
A: Not currently. Use a DAW such as Ableton, Logic, or FL Studio for editing.

**Q: Does it support batch or parallel conversion?**  
A: Multiple files run sequentially today. Parallel processing is on the roadmap.

**Q: Is real-time conversion available?**  
A: No, but it is a long-term goal.

**Q: How can I improve accuracy?**  
A: Use clean high-quality audio, adjust thresholds, and ensure settings match the material (mono vs. poly).

## Contributing
**Q: How can I contribute?**  
A: See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines.

**Q: I found a bug. What should I do?**  
A: Open a GitHub issue using the bug report template with detailed information.

**Q: Can I request new features?**  
A: Yes. Use the feature request issue template or join GitHub Discussions.

**Q: How can I support the project?**  
A: Star the repository, report bugs, contribute code or docs, and share it with others.

## Technical
**Q: Which AI models are used?**  
A: Spotify’s Basic-Pitch and Meta’s Demucs. See [AI Models](AI_MODELS.md) for details.

**Q: Why PyQt6?**  
A: Modern, cross-platform, and provides native look-and-feel.

**Q: Can I use MP3paraMIDI as a library?**  
A: Yes. Import modules from `mp3paramidi` for custom workflows.

**Q: Where can I learn about the architecture?**  
A: Read [docs/ARCHITECTURE.md](ARCHITECTURE.md).

---
Have a question not answered here? Ask in [GitHub Discussions](https://github.com/zarigata/mp3paramidi/discussions)! – Zarigata
