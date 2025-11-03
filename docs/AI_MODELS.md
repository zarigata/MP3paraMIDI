# AI Models in MP3paraMIDI

## Overview
MP3paraMIDI includes optional AI-enhanced features powered by two state-of-the-art models:

- **Basic-Pitch** for polyphonic note transcription.
- **Demucs** for music source separation.

Both models download automatically on first use, operate entirely offline, and can be enabled or disabled from the Settings dialog.

## Basic-Pitch

### What It Is
Basic-Pitch is an open-source model developed by Spotify for polyphonic pitch detection. Introduced at ICASSP 2022, it is trained on a large and diverse collection of music recordings.

### How It Works
- Analyzes audio spectrograms using convolutional neural networks.
- Detects simultaneous notes (polyphony) and outputs note events with start times, end times, MIDI pitch values, and velocities.
- Converts predictions into the internal note format consumed by MP3paraMIDI’s pipeline.

### When to Use Basic-Pitch
- Piano, guitar, or other chord-rich recordings.
- Songs featuring multiple instruments or rich harmonies.
- Vocal harmonies and choral arrangements.

### Configuration Options
Adjust these from the Settings dialog:
- **Onset Threshold:** Lower values detect more note starts; higher values reduce noise.
- **Frame Threshold:** Controls continuation sensitivity; lower values produce longer sustained notes.
- **Minimum Note Length:** Filters out extremely short notes to reduce artifacts.

### Performance
- Approximately real-time (≈30 seconds of audio per second) on modern CPUs; significantly faster with GPU acceleration.
- Accuracy depends on audio quality, instrument diversity, and mix clarity.

### Model Size and Storage
- ~50 MB download stored in `models/basic_pitch/`.
- Cached for reuse; delete the folder to trigger re-download.

### Citation
> Bittner, R. M., McFee, B., Salamon, J., Li, P., & Bello, J. P. (2022). *A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch Estimation*. ICASSP 2022.

## Demucs

### What It Is
Demucs is a state-of-the-art source separation model from Meta AI Research. It has ranked highly in Music Demixing Challenges and is widely used for stem separation tasks.

### How It Works
- Combines time-domain convolutions with spectrogram-based transformers.
- Separates tracks into vocals, drums, bass, and other instruments (additional stems available in extended variants).
- Processed stems feed the transcription pipeline for multi-track MIDI generation.

### When to Use Demucs
- Full-band recordings with vocals and accompaniment.
- Sessions where stems are needed for further mixing or per-instrument MIDI.
- Preparing multi-track MIDI projects for DAWs.

### Configuration Options
Available in Settings → AI tab:
- **Model Variant:** Choose between `htdemucs`, `htdemucs_ft`, or `htdemucs_6s`.
- **Segment Duration:** Shorter segments reduce memory usage at the cost of quality.
- **Shifts:** Enables test-time augmentation for improved separation (increases compute time).

### Performance
- Processes ~10 seconds of audio per second on CPU; GPUs offer 3–5× speedups.
- Requires 2–4 GB RAM depending on audio length and model variant.

### Model Size and Storage
- ~350 MB download stored in `models/demucs/`.
- Cached persistently; manual deletion forces re-download.

### Citation
> Défossez, A., Fender, T., Lavoie, M., & Grangier, D. (2021). *Hybrid Spectrogram and Waveform Source Separation*. ISMIR 2021.

## Integration in MP3paraMIDI
1. User enables AI features in Settings.
2. On first conversion, models download and cache locally.
3. Demucs (if enabled) separates the audio into stems.
4. Basic-Pitch transcribes each stem or the full mix.
5. `MidiGenerator` creates multi-track MIDI with instrument labels.

## System Requirements
- **Minimum:** 4 GB RAM, 2 GB free disk space, modern CPU (2015+).
- **Recommended:** 8+ GB RAM, CUDA-capable GPU with 4+ GB VRAM, SSD storage.

### GPU Acceleration
- Requires CUDA-compatible hardware and a PyTorch build with CUDA support.
- Acceleration typically yields 3–10× speed improvements for both models.

## Model Storage
- Stored under the repository’s `models/` directory.
- Safe to delete when reclaiming disk space; models re-download on demand.
- Total footprint for both models is ~400–500 MB.

## Troubleshooting
- **Models won’t download:** Check internet connectivity, ensure 2 GB free disk space, verify firewall permissions, consider manual download from the official repositories.
- **Out of memory errors:** Reduce Demucs segment duration, close other applications, switch to CPU mode, process shorter files.
- **Slow performance:** Enable GPU acceleration, lower audio sample rate/quality, disable source separation, use monophonic mode.
- **Accuracy issues:** Adjust sensitivity thresholds, pick a suitable preset (balanced/sensitive/conservative), ensure clean audio input, perform manual MIDI refinement if needed.

## Privacy and Ethics
- All processing remains on the user’s machine—no audio leaves the local environment.
- Models are open-source and distributed via official channels.
- Respect copyright when working with commercial recordings.
- Model outputs may reflect training data biases; review results critically.

## Future Models
Potential future expansions include:
- **Spleeter** for a lightweight alternative to Demucs.
- **Omnizart** for multi-instrument transcription.
- **CREPE** for high-accuracy monophonic pitch detection.
- Custom fine-tuned models targeting niche instruments or styles.

## References
- Basic-Pitch: https://github.com/spotify/basic-pitch
- Demucs: https://github.com/facebookresearch/demucs
- PyTorch: https://pytorch.org/
- MP3paraMIDI Architecture: [docs/ARCHITECTURE.md](ARCHITECTURE.md)

For best results, experiment with settings, understand each model’s strengths, and combine AI outputs with musical judgment. Contributions that improve or extend AI integrations are welcome!
