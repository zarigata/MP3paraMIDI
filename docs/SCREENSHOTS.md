# Visual Asset Guide for MP3paraMIDI

## Purpose
High-quality visuals showcase MP3paraMIDI’s polished GUI and help potential users understand the experience before downloading. Screenshots and demo assets improve the README, boost discoverability on GitHub, and increase user confidence.

## Required Screenshots
Save finalized images under `docs/images/` with the filenames below.

1. **Main Window** — `main-window.png`
   - Show the drag-and-drop area with a few example files loaded.
   - Ensure the Convert button is enabled and the interface looks tidy.

2. **Settings Dialog – General Tab** — `settings-general.png`
   - Display quantization, tempo detection, and note filtering options.
   - Highlight the tabbed interface and default configuration.

3. **Settings Dialog – AI Models Tab** — `settings-ai.png`
   - Capture AI toggles, presets, and configuration sliders.
   - Explain tooltips or contextual help if visible.

4. **Conversion in Progress** — `conversion-progress.png`
   - Show the progress bar mid-conversion with informative status text.
   - Include a realistic file list to demonstrate queue processing.

5. **Playback Controls** — `playback-controls.png`
   - Display the playback widget with a loaded MIDI file.
   - Show play/pause/stop buttons, position slider, and time indicators.

6. **About Dialog** — `about-dialog.png`
   - Highlight the about window featuring Zarigata’s credit and version details.

## Screenshot Guidelines
- **Resolution:** Capture at 1920×1080 or higher. Downscale to 1280×720 for web usage. For Retina displays, export at 2× resolution and label accordingly.
- **Format:** Use PNG for crisp, lossless images. Optimize with `pngquant` or TinyPNG. Target file size < 500 KB.
- **Content:** Use clean example filenames (e.g., `my_song.mp3`, `guitar_solo.wav`). Avoid personal or copyrighted material.
- **Framing:** Include full application window with OS chrome. Center on a neutral desktop background for consistency.
- **Color & Contrast:** Ensure readability. Prefer the default/light theme for uniformity unless demonstrating theme options.
- **Annotations:** Use minimal, consistent styling if highlighting elements. Avoid clutter.

## Demo GIF / Video
A short demo communicates the workflow effectively.

- **Storyboard:**
  1. Launch with empty window.
  2. Drag an audio file into the drop area.
  3. Show file in list, Convert button activates.
  4. Click Convert, display progress animation.
  5. Conversion completes; playback widget appears.
  6. Press Play to preview MIDI.

- **Recording Tools:**
  - Windows: Xbox Game Bar, OBS Studio.
  - macOS: QuickTime Player, ScreenFlow.
  - Linux: SimpleScreenRecorder, Kazam.

- **Settings:** 1280×720 resolution, 30 fps. Record as MP4/MOV, then convert to GIF using `ffmpeg` or gifski.

- **GIF Optimization:**
  - Trim to 15–30 seconds.
  - Reduce frame rate to 10–15 fps for smaller files.
  - Optimize with gifsicle or ezgif.com. Target < 5 MB.

- **File Name:** Save as `docs/images/demo.gif`. Provide alt text when embedding in README.

## Storage & Versioning
- Keep all assets in `docs/images/`.
- Commit images to the repository; use Git LFS only if individual files exceed ~1 MB.
- Document the UI version in commit messages or use versioned subfolders if visual changes are frequent.

## Updating Screenshots
- Refresh visuals after major UI changes or new features.
- Maintain consistent lighting, theme, and annotation style.
- Consider platform-specific captures if interfaces differ significantly (note this in captions).

## Accessibility Tips
- Provide descriptive alt text for each image (e.g., “MP3paraMIDI main window showing drag-and-drop file list”).
- Pair visuals with surrounding explanatory text; do not rely solely on imagery.
- Ensure screenshots show high-contrast UI elements for readability.

## Example Workflow
1. Launch MP3paraMIDI in a clean state.
2. Prepare sample audio files and configure settings as needed.
3. Record or capture at key stages following the storyboard.
4. Edit and optimize images/GIFs for size and clarity.
5. Place assets in `docs/images/`.
6. Update README and documentation references.
7. Commit assets and documentation with descriptive messages.

## Common Pitfalls
- Cropped windows or missing OS chrome.
- Cluttered desktops or distracting backgrounds.
- Inconsistent resolution or color profiles.
- Overly long or large GIF files.

High-quality visuals significantly improve project presentation and help MP3paraMIDI stand out. Aim for clarity, consistency, and professional polish throughout.
