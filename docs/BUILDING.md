# Building MP3paraMIDI

This document explains how to build MP3paraMIDI locally, generate icons, and understand the cross-platform distribution pipeline.

## Prerequisites

| Platform | Required Tools |
| --- | --- |
| All | Python 3.10 or 3.11, pip, virtualenv, Git |
| Windows | Inkscape, ImageMagick (`magick`), PyInstaller (installed via pip), Optional: NSIS for installer creation |
| macOS | Inkscape, ImageMagick (`convert`), `iconutil`, Xcode command-line tools (for `codesign`/`notarytool`) |
| Linux | Inkscape, ImageMagick (`convert`), `wget`, FUSE2 (to run AppImages), Optional: `desktop-file-validate` |

> **Note:** AI builds require the additional dependencies listed in `requirements-ai.txt`. These increase the final bundle size significantly.

## Icon Generation Pipeline

Icons are generated from a single master SVG source located at `assets/master.svg`. The pipeline produces PNG, ICO, and ICNS assets for PyInstaller bundles.

1. **Generate icons on Linux/macOS**
   ```bash
   bash tools/build_icons.sh
   ```
2. **Generate icons on Windows**
   ```powershell
   pwsh tools/build_icons.ps1
   ```

The scripts output to `assets/icons/` with the following structure:

```
assets/icons/
  ├── png/
  │   ├── icon_16.png
  │   ├── icon_32.png
  │   └── ...
  ├── ico/mp3paramidi.ico
  └── icns/mp3paramidi.icns
```

These assets are required before running PyInstaller.

## Building Locally

### Common Steps

1. Create and activate a Python virtual environment.
2. Install dependencies:
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
3. (Optional) Install AI dependencies for the AI build variant:
   ```bash
   python -m pip install -r requirements-ai.txt
   ```
4. Generate icons as described above.

### Standard Build (Core Features)

```bash
pyinstaller build_configs/mp3paramidi.spec
```

Output appears in `dist/MP3paraMIDI/` (onedir layout).

### AI Build (AI Features)

```bash
pyinstaller build_configs/mp3paramidi-ai.spec
```

This produces `dist/MP3paraMIDI-AI/`. Expect ~1 GB output size.

PyInstaller uses `onedir` mode for faster startup and easier debugging. Use `--clean` to remove cached build artifacts when troubleshooting.

## Platform-Specific Packaging

### Windows

- The Windows build uses `build_configs/version_info.txt` for embedded metadata.
- Optional: Create an installer with NSIS or another packaging tool.
- Code signing can be performed with `signtool` or Azure Trusted Signing (see `docs/RELEASE.md`).

### macOS

- The `.app` bundle is produced via PyInstaller. Additional packaging into a `.dmg` can be done using `create-dmg` or `hdiutil`.
- Code signing and notarization require Apple Developer credentials and are automated in CI when secrets are provided.

### Linux

- The AppImage workflow uses `build_configs/linux/build_appimage.sh`.
- Run the script after PyInstaller completes to produce `MP3paraMIDI-<version>-Linux-x86_64.AppImage`.
- Ensure `linuxdeploy` is present; the script downloads it if missing.

## Build Variants

| Variant | Description | Approx. Size |
| --- | --- | --- |
| Standard | Core functionality without AI dependencies | 200 MB |
| AI | Includes torch, torchaudio, demucs, basic-pitch for advanced transcription | 1 GB |

AI models are downloaded at runtime to `models/`, keeping the installer size manageable.

## Troubleshooting

- **Missing Hidden Imports:** Run PyInstaller with `--debug=imports` to identify missing modules. Update spec files or hooks as needed.
- **Qt Plugin Errors:** Ensure PyInstaller collected PyQt6 plugins. Use `--collect-all PyQt6` if necessary.
- **Pygame MIDI Issues:** Linux/macOS users may need to install a SoundFont and configure `timidity`.
- **Large Bundle Size:** Use PyInstaller exclusions or optimize dependencies. AI builds are expected to be large.
- **Slow Startup:** Stick to `onedir` mode and avoid unnecessary files in the distribution.

## CI/CD Overview

- `.github/workflows/build.yml` performs matrix builds for Windows, macOS, and Linux, covering both standard and AI variants.
- `.github/workflows/test-builds.yml` runs smoke tests on pull requests to catch build regressions early.
- Artifacts are uploaded per platform/variant and used for releases.
- Git tags (`v*`) trigger release packaging and publication.

## Testing Builds

- **Windows:** Run the generated `.exe` directly; use `sigcheck` or `Get-AuthenticodeSignature` to validate signatures when available.
- **macOS:** Launch the `.app` bundle via Finder or `open dist/MP3paraMIDI.app`. Use `codesign --verify --deep` for validation.
- **Linux:** Make the AppImage executable (`chmod +x`) and run it. Use `--appimage-extract` to inspect contents if needed.
- Smoke tests should ensure the GUI launches, audio files load, and MIDI playback works.

Refer to `docs/RELEASE.md` for release-specific procedures.
