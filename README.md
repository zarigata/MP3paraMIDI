# MP3paraMIDI - Audio to MIDI Converter

AI-powered toolkit that separates full-length songs into stems and translates them into expressive MIDI files through a RESTful API.

**Developed by [zarigata](https://github.com/zarigata)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features
- 🎚️ Demucs HTDemucs-based source separation for drums, bass, vocals, and other stems
- 🎼 Audio-to-MIDI transcription via Spotify Basic Pitch, Melodia, and PrettyMIDI
- 🌐 Job-centric Flask API with UUID tracking and structured storage hierarchy
- 🎧 Supports MP3, WAV, FLAC, and OGG uploads up to 100 MB by default
- 📦 JSON-first responses with download URLs and metadata ready for UI consumption

## Tech Stack
- Python 3.10+
- Flask 3.x
- FastAPI 0.115+
- PyTorch, Demucs
- Spotify Basic Pitch + Melodia (audio2midi)
- PrettyMIDI
- Gradio 5.x (interactive ML interfaces)
- uvicorn (ASGI server)
- a2wsgi (ASGI↔WSGI adapter)
- **Frontend**:
  - Vanilla JavaScript (ES6+)
  - HTML5 (semantic markup, audio API)
  - CSS3 (glassmorphism, Grid/Flexbox, backdrop-filter)
  - RealGlass v1.0.1 (liquid glass effects)

### Deployment
- Docker (multi-stage builds for CPU and GPU targets)
- Docker Compose (development, production, and GPU overrides)
- uvicorn (multi-worker ASGI server)
- nginx (reverse proxy, optional)

## Installation

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/zarigata/MP3paraMIDI.git
cd MP3paraMIDI

# Launch using Docker
./run.sh --mode=docker   # Linux / macOS
run.bat --mode=docker    # Windows
```

The launcher scripts validate prerequisites, ensure `.env` exists, build the container, and start the unified server automatically. See [DOCKER.md](DOCKER.md) for GPU support, production overrides, troubleshooting, and performance tuning.

### Option 2: Local Installation

**Prerequisites**

- Python 3.10 or higher
- FFmpeg (audio conversion)
- libsndfile (audio I/O)

**Install system packages**

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg libsndfile1

# macOS (Homebrew)
brew install python@3.11 ffmpeg libsndfile

# Windows
# Install Python from https://python.org
# Install FFmpeg from https://ffmpeg.org or via Chocolatey:
choco install ffmpeg
```

**Set up the project**

```bash
git clone https://github.com/zarigata/MP3paraMIDI.git
cd MP3paraMIDI

python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate     # Windows

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

cp .env.example .env       # Linux / macOS
copy .env.example .env     # Windows
```

Run the unified server locally:

```bash
python src/main.py
```

Or use the launcher scripts in virtual-environment mode:

```bash
./run.sh --mode=venv   # Linux / macOS
run.bat --mode=venv    # Windows
```

## API Documentation
**Base URLs:**
- Flask dev server: `http://localhost:5000`
- Unified/Docker: `http://localhost:8000`

> Ports depend on run mode; see Configuration for `FLASK_PORT` and `APP_PORT`.

Use `<BASE_URL>` from the list above in the requests that follow.

### POST /api/separate
Upload audio and trigger stem separation.
- **Request:** `multipart/form-data` with `file=<audio>`
- **Response:**
  ```json
  {
    "status": "success",
    "message": "Audio separated successfully",
    "data": {
      "job_id": "8d6f3f7c-46a5-4d02-9240-ef7d63fb1d06",
      "original_filename": "mix.mp3",
      "stems": [
        {
          "name": "vocals",
          "filename": "mix_stem_vocals.wav",
          "size": 12345678,
          "download_url": "/api/download/8d6f3f7c-46a5-4d02-9240-ef7d63fb1d06/stems/mix_stem_vocals.wav",
          "download_url_encoded": "/api/download/eyJqb2JfaWQiOiI4ZDZmM2Y3Yy00NmE1LTRkMDItOTI0MC1lZjdkNjNmYjFkMDYiLCJjYXRlZ29yeSI6InN0ZW1zIiwiZmlsZW5hbWUiOiJtaXhfc3RlbV92b2NhbHMud2F2In0"
        }
      ]
    }
  }
  ```
- **Example:**
  ```bash
  curl -X POST "<BASE_URL>/api/separate" \
       -F "file=@song.mp3"
  ```

### POST /api/convert-to-midi
Convert separated stems to a combined MIDI file.
- **Request:** JSON body `{ "job_id": "<uuid>", "stem_names": ["vocals"] }` (stem_names optional)
- **Response:**
  ```json
  {
    "status": "success",
    "message": "Stems converted to MIDI successfully",
    "data": {
      "job_id": "8d6f3f7c-46a5-4d02-9240-ef7d63fb1d06",
      "midi_file": {
        "filename": "combined.mid",
        "size": 987654,
        "download_url": "/api/download/8d6f3f7c-46a5-4d02-9240-ef7d63fb1d06/midi/combined.mid",
        "download_url_encoded": "/api/download/eyJqb2JfaWQiOiI4ZDZmM2Y3Yy00NmE1LTRkMDItOTI0MC1lZjdkNjNmYjFkMDYiLCJjYXRlZ29yeSI6Im1pZGkiLCJmaWxlbmFtZSI6ImNvbWJpbmVkLm1pZCJ9"
      },
      "stems_converted": ["vocals", "drums", "bass", "other"]
    }
  }
  ```
- **Example:**
  ```bash
  curl -X POST "<BASE_URL>/api/convert-to-midi" \
       -H "Content-Type: application/json" \
       -d '{"job_id": "8d6f3f7c-46a5-4d02-9240-ef7d63fb1d06"}'
  ```

### GET /api/download/{file_id}
Preferred download route that accepts a URL-safe Base64 encoded payload containing `job_id`, `category`, and `filename`.
- **Example:**
  ```bash
  curl -O "<BASE_URL>/api/download/eyJqb2JfaWQiOiI4ZDZmM2Y3Yy00NmE1LTRkMDItOTI0MC1lZjdkNjNmYjFkMDYiLCJjYXRlZ29yeSI6Im1pZGkiLCJmaWxlbmFtZSI6ImNvbWJpbmVkLm1pZCJ9"
  ```
- The encoded URLs are returned alongside the legacy form in API responses. They avoid path-manipulation edge cases and align with the latest contract (`/api/download/<file_id>`).

### GET /api/download/{job_id}/{category}/{filename}
Legacy download route retained for backwards compatibility.
- **Path Params:**
  - `job_id`: UUID returned by `/api/separate`
  - `category`: `uploads`, `stems`, or `midi`
  - `filename`: File name from response metadata
- **Example:**
  ```bash
  curl -O "<BASE_URL>/api/download/8d6f3f7c-46a5-4d02-9240-ef7d63fb1d06/midi/combined.mid"
  ```

### GET /health
Health check for monitoring / orchestration.
- **Response:**
  ```json
  {
    "status": "healthy",
    "storage_root": "C:/path/to/storage",
    "directories": {
      "uploads": {"exists": true, "writable": true, "path": "..."},
      "stems": {"exists": true, "writable": true, "path": "..."},
      "midi": {"exists": true, "writable": true, "path": "..."}
    },
    "available_models": ["htdemucs"],
    "supported_stems": ["vocals", "drums", "bass", "other"]
  }
  ```

## Web UI

MP3paraMIDI includes a modern glassmorphism-inspired interface for uploading audio, previewing stems, and generating MIDI files without touching the API.

### Accessing the Web UI

1. Start the Flask application:
   ```bash
   python src/app.py
   ```
2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

### Features

- **Drag-and-drop file upload** for MP3, WAV, FLAC, and OGG sources
- **Real-time stem playback** with custom HTML5 audio controls
- **One-click MIDI conversion** for all separated stems
- **Glassmorphism design** powered by CSS and RealGlass for liquid glass effects
- **Responsive layout** that adapts to phones, tablets, and desktops
- **Accessibility** support with ARIA labels, keyboard navigation, and reduced-motion handling

### Browser Compatibility

- **Recommended:** Chrome 90+, Edge 90+, Safari 15+, Firefox 90+
- **Required features:** Fetch API, HTML5 audio, CSS `backdrop-filter`
- **Progressive enhancement:** Gracefully degrades if RealGlass fails to load

### UI Workflow

1. **Upload** an audio file via drag-and-drop or the file picker
2. **Separate** the stems by clicking <kbd>Separate Audio</kbd>
3. **Listen** to each stem with the integrated player controls
4. **Download** individual stems directly from the UI
5. **Convert** all stems to MIDI with <kbd>Convert All to MIDI</kbd>
6. **Download MIDI** for use in your DAW or sequencer

## Gradio Interface

MP3paraMIDI also ships with an interactive Gradio interface that delivers a notebook-style experience with built-in audio players, download buttons, and status indicators.

### Accessing the Gradio Interface

**Option 1: Unified Server (Recommended)**

```bash
python src/main.py
```

Then open:
- **Flask Web UI**: http://localhost:8000/
- **Flask API**: http://localhost:8000/api/
- **Gradio Interface**: http://localhost:8000/gradio

**Option 2: Standalone Gradio with Public Sharing**

```bash
GRADIO_SHARE=True python src/gradio_standalone.py
```

Gradio will print a public URL such as `https://abc123.gradio.live` that remains active for up to 72 hours.

> **Note:** `share=True` is unavailable when Gradio is mounted via FastAPI. For public URLs in unified mode, use ngrok as described below.

### Gradio Features

- **Three-tab layout**:
  1. **🎚️ Separate Audio** – Upload and separate stems with Demucs
  2. **🎼 Convert to MIDI** – Turn the latest stems into a multitrack MIDI file
  3. **⚡ Quick Workflow** – Single-step upload → separate → convert → download
- **Model selection** dropdown with all supported Demucs variants
- **Embedded audio players** for each separated stem
- **Direct download** links for stems and combined MIDI
- **Optional authentication** via the `GRADIO_AUTH` environment variable
- **Real-time status updates** during model inference and MIDI generation

### Public URL Sharing with ngrok (Unified Server)

`share=True` is unavailable when Gradio is mounted. Use ngrok to create a tunnel instead:

1. Install ngrok from https://ngrok.com/download and authenticate (`ngrok config add-authtoken <token>`)
2. Start the unified server:
   ```bash
   python src/main.py
   ```
3. In a separate terminal run:
   ```bash
   ngrok http 8000
   ```
4. Use the public URL printed by ngrok (e.g., `https://abc-123.ngrok-free.app`)
5. Access Gradio at `https://abc-123.ngrok-free.app/gradio`

#### Programmatic ngrok (Python SDK)

```bash
pip install ngrok
```

```python
import ngrok
import uvicorn
from src.main import create_unified_app

listener = ngrok.forward(8000, authtoken_from_env=True)
print(f"Public URL: {listener.url()}")
print(f"Gradio Interface: {listener.url()}/gradio")

uvicorn.run(create_unified_app(), host="0.0.0.0", port=8000)
```

#### Alternative: pyngrok

```bash
pip install pyngrok
```

Refer to the pyngrok documentation for equivalent tunnelling code.

### Gradio vs. Web UI

| Feature | Gradio Interface | Flask Web UI |
|---------|------------------|--------------|
| **Styling** | Gradio themes (Soft/Glass) | Custom glassmorphism design |
| **Audio playback** | Built-in components | Custom HTML5 players |
| **Public sharing** | `share=True` (standalone only) | Requires ngrok / reverse proxy |
| **Authentication** | `GRADIO_AUTH` environment variable | Custom implementation required |
| **Customization** | Limited to Gradio building blocks | Full control over HTML/CSS/JS |
| **Best for** | Demos, notebooks, quick experiments | Production deployments, branding |

### Gradio Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_HOST` | `0.0.0.0` | Host for unified FastAPI server |
| `APP_PORT` | `8000` | Port for unified FastAPI server |
| `GRADIO_SHARE` | `False` | Enable `share=True` (standalone only) |
| `GRADIO_AUTH` |  | Optional `username:password` for basic auth |
| `GRADIO_HOST` | `0.0.0.0` | Host for standalone Gradio |
| `GRADIO_PORT` | `7860` | Port for standalone Gradio |

**Example with auth:**

```bash
GRADIO_AUTH=admin:secret123 python src/main.py
```

Users will be prompted for credentials when accessing `/gradio`.

## Docker Deployment

MP3paraMIDI ships with production-ready Docker images (CPU and GPU) and Compose files for development, production, and GPU overrides.

### Quick Start with Docker

**Using launcher scripts (recommended):**

```bash
# Linux / macOS
chmod +x run.sh
./run.sh --mode=docker

# Windows
run.bat --mode=docker
```

**Using Docker Compose directly:**

```bash
docker-compose up -d          # Start the application
docker-compose logs -f        # View logs
docker-compose down           # Stop containers
```

**Access the application:**
- Flask Web UI: http://localhost:8000/
- Flask API: http://localhost:8000/api/
- Gradio Interface: http://localhost:8000/gradio

### Docker Images

- **CPU-only (default):** `Dockerfile`, ~2 GB, optimized multi-stage build
- **GPU-accelerated:** `Dockerfile.gpu`, ~4 GB, CUDA-enabled PyTorch (5–10× faster)

```bash
# Run with GPU support
./run.sh --mode=gpu

# Or use docker-compose override
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### Compose Overrides & Production

- `docker-compose.yml`: Local development (single worker)
- `docker-compose.prod.yml`: Production overrides (4 workers, resource limits, log rotation)
- `docker-compose.gpu.yml`: NVIDIA runtime and GPU resources

Launch production stack:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Production Checklist

1. Set `CORS_ORIGINS` to trusted domains (not `*`).
2. Enable Gradio authentication via `GRADIO_AUTH`.
3. Place an HTTPS-capable reverse proxy (nginx / Traefik) in front.
4. Configure backups for the `storage_data` volume.
5. Enable monitoring and log aggregation (Prometheus, Grafana, ELK).
6. Adjust worker count and resource limits based on hardware capacity.

For end-to-end deployment details, GPU setup, and troubleshooting guidance, see **[DOCKER.md](DOCKER.md)**.

## Usage Example

### Using the Web UI (Recommended for most users)

The easiest way to use MP3paraMIDI is through the web interface:

1. Start the unified server: `python src/main.py`
2. Open http://localhost:8000 in your browser (web UI at `/`, Gradio at `/gradio`)
3. Upload an audio file and follow the on-screen instructions

### Using the API (For developers and automation)

1. **Separate:** `POST /api/separate`
2. **Convert:** `POST /api/convert-to-midi`
3. **Download:** `GET /api/download/...`

## Configuration
| Variable | Default | Description |
| --- | --- | --- |
| `FLASK_HOST` | `0.0.0.0` | Host interface for Flask dev server |
| `FLASK_PORT` | `5000` | Listening port |
| `FLASK_DEBUG` | `False` | Enables Flask debug mode |
| `APP_HOST` | `0.0.0.0` | Host interface for unified server |
| `APP_PORT` | `8000` | Port for unified server |
| `GRADIO_SHARE` | `False` | Enable Gradio `share=True` (standalone only) |
| `GRADIO_AUTH` | `` | Optional `username:password` basic auth for Gradio |
| `GRADIO_HOST` | `0.0.0.0` | Host for standalone Gradio launcher |
| `GRADIO_PORT` | `7860` | Port for standalone Gradio launcher |
| `APP_STORAGE_ROOT` | `storage` | Root directory for uploads, stems, MIDI |
| `MAX_UPLOAD_SIZE_MB` | `100` | Maximum upload size in MB |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed origins |
| `RETAIN_UPLOADS` | `True` | Keep original uploads after successful separation |
| `RETAIN_STEMS` | `True` | Keep separated stems after MIDI conversion |
| `ABSOLUTE_URLS` | `False` | When `True`, download URLs are returned with scheme/host (e.g., `http://localhost:5000/...`) |

### Storage cleanup controls
- Set `RETAIN_UPLOADS=False` to remove uploaded files once stems are generated.
- Set `RETAIN_STEMS=False` to prune intermediate stems after MIDI conversion.
- Both flags default to `True` for safety; enabling cleanup keeps storage usage minimal.

### Download URL format
- Responses include both relative and encoded download URLs. Absolute URLs can be enabled globally with `ABSOLUTE_URLS=True` (useful for browser clients behind proxies).

## Development
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Coverage report
pytest --cov=src

# Format & lint
black src/ tests/
flake8 src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

## Project Structure
```
MP3paraMIDI/
├── src/
│   ├── __init__.py
│   ├── app.py               # Flask API
│   ├── main.py              # Unified server (FastAPI + Flask + Gradio)
│   ├── gradio_app.py        # Gradio interface definitions
│   ├── gradio_standalone.py # Standalone Gradio launcher
│   ├── audio_separation.py  # Demucs integration
│   └── audio_to_midi.py     # MIDI conversion
├── static/                 # Frontend assets
├── templates/              # HTML templates
├── tests/
│   ├── test_app.py          # Flask API tests
│   ├── test_audio_separation.py
│   ├── test_audio_to_midi.py
│   ├── test_gradio_app.py   # Gradio test scaffolding
│   └── test_main.py         # Unified server test scaffolding
├── storage/                # Generated assets (gitignored)
├── Dockerfile              # CPU-optimized image
├── Dockerfile.gpu          # CUDA-enabled image
├── docker-compose.yml      # Development Compose stack
├── docker-compose.gpu.yml  # GPU override
├── docker-compose.prod.yml # Production overrides
├── run.sh                  # Launcher script (Linux / macOS)
├── run.bat                 # Launcher script (Windows)
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── LICENSE                 # MIT License
├── CONTRIBUTING.md         # Contribution guidelines
├── DOCKER.md               # Complete Docker deployment guide
└── README.md
```

## License

MP3paraMIDI is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for full details. Attribution is appreciated; see `NOTICE` for recommended credit.

### What You Can Do

✅ **Use** – Use MP3paraMIDI for personal, academic, or commercial projects  
✅ **Modify** – Adapt and customize the code for your needs  
✅ **Distribute** – Share the software with others  
✅ **Sublicense** – Include it in proprietary software  

### Recommended Attribution

When using MP3paraMIDI in public projects, derivative works, or commercial applications, consider crediting the project:

1. Credit the original author: **[zarigata](https://github.com/zarigata)**
2. Include a link to this repository: `https://github.com/zarigata/MP3paraMIDI`
3. Provide a reference similar to the example below

Example attribution:
```
Powered by MP3paraMIDI by zarigata
https://github.com/zarigata/MP3paraMIDI
```

### Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Reporting bugs and requesting features
- Code style and testing requirements
- Pull request process
- Licensing terms for contributions

By contributing, you agree that your contributions will be licensed under the same MIT License.

## Community & Support

- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines
- **Issues:** Report bugs or request features via [GitHub Issues](https://github.com/zarigata/MP3paraMIDI/issues)
- **License:** [MIT License](LICENSE) with attribution requirement
- **Author:** [zarigata](https://github.com/zarigata)

## Roadmap / Future Phases
1. ✅ Glassmorphism-inspired web UI for the API endpoints
2. ✅ Gradio interface with public sharing support
3. 🔄 Docker images for GPU and CPU deployments
4. 📋 Batch processing and queue-based job orchestration

## Troubleshooting
- **CUDA out of memory:** Reduce audio length or set `CUDA_VISIBLE_DEVICES=""` to force CPU.
- **File too large:** Increase `MAX_UPLOAD_SIZE_MB` in `.env`.
- **Model downloads fail:** Ensure internet access for first-time Demucs download.
- **Gradio not available at `/gradio`:** Run `python src/main.py` instead of `python src/app.py`.
- **`share=True` does nothing:** Only supported in standalone mode (`python src/gradio_standalone.py`). Use ngrok with the unified server.
- **Port already in use:** Override `APP_PORT`, e.g., `APP_PORT=8080 python src/main.py`.

## Credits
- [Demucs](https://github.com/facebookresearch/demucs) by Meta Research
- [Basic Pitch](https://github.com/spotify/basic-pitch) by Spotify
- [Melodia](https://github.com/MTG/essentia) by MTG-UPF
- [PrettyMIDI](https://github.com/craffel/pretty-midi)
- Developed by [zarigata](https://github.com/zarigata)

### Design
- Glassmorphism effects powered by RealGlass
- Inspired by Apple's iOS visual language
- Custom audio player controls with Media Session API foundations
