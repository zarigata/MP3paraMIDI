"""MP3paraMIDI Flask API.

This module exposes a job-based REST API for the MP3paraMIDI project. Each
incoming audio separation request is tracked via a UUID-backed job directory and
stored in a structured hierarchy under ``storage/{uploads,stems,midi}/<job_id>``.
The API integrates the existing ``audio_separation`` and ``audio_to_midi``
modules to provide two-phase processing: first, Demucs-powered stem separation;
second, MIDI transcription via Basic Pitch, Melodia, and PrettyMIDI. All routes
respond with JSON envelopes and are guarded by strict validation, file size
limits, and configurable CORS policies.

Configuration is sourced from environment variables (see ``.env.example``):
``APP_STORAGE_ROOT``, ``MAX_UPLOAD_SIZE_MB``, ``CORS_ORIGINS``, ``FLASK_HOST``,
``FLASK_PORT``, and ``FLASK_DEBUG``. For production deployments, point
``APP_STORAGE_ROOT`` at durable storage (e.g., S3-mounted volume) and scope
``CORS_ORIGINS`` to trusted domains. Example workflow:

1. ``POST /api/separate`` with an audio file (MP3/WAV/FLAC/OGG)
2. ``POST /api/convert-to-midi`` with the returned ``job_id``
3. ``GET /api/download/<job_id>/<category>/<filename>`` to retrieve assets

Security considerations include extension whitelisting, path sanitisation via
``secure_filename``, 100 MB upload limits (modifiable), and JSON-only error
responses to ease UI integration.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flask import (
    Blueprint,
    Flask,
    current_app,
    has_request_context,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from flask_cors import CORS
from werkzeug.exceptions import NotFound
from werkzeug.utils import secure_filename

from src.audio_separation import get_available_models, separate_audio
from src.audio_to_midi import (
    combine_midi_files,
    convert_stem_to_midi,
    convert_stems_to_combined_midi,
    get_supported_stem_types,
)

try:  # pragma: no cover - torch is heavy but required for OOM handling
    import torch
except ModuleNotFoundError:  # pragma: no cover - fallback for CPU-only envs
    torch = None

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

DEFAULT_ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg"}


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _load_base_config() -> Dict[str, object]:
    storage_root = Path(os.getenv("APP_STORAGE_ROOT", "storage"))
    upload_dir = storage_root / "uploads"
    stems_dir = storage_root / "stems"
    midi_dir = storage_root / "midi"

    raw_cors_origins = os.getenv("CORS_ORIGINS", "*")
    cors_origins = [origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()] or ["*"]

    config: Dict[str, object] = {
        "STORAGE_ROOT": storage_root,
        "UPLOAD_DIR": upload_dir,
        "STEMS_DIR": stems_dir,
        "MIDI_DIR": midi_dir,
        "ALLOWED_AUDIO_EXTENSIONS": DEFAULT_ALLOWED_AUDIO_EXTENSIONS,
        "MAX_CONTENT_LENGTH": int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")) * 1024 * 1024,
        "CORS_ORIGINS": cors_origins,
        "RETAIN_UPLOADS": _parse_bool_env("RETAIN_UPLOADS", True),
        "RETAIN_STEMS": _parse_bool_env("RETAIN_STEMS", True),
        "ABSOLUTE_URLS": _parse_bool_env("ABSOLUTE_URLS", False),
    }

    return config


def create_app(config_overrides: Optional[Dict[str, object]] = None) -> Flask:
    """Return a configured Flask application instance."""

    config = _load_base_config()
    if config_overrides:
        config.update(config_overrides)

    project_root = Path(__file__).resolve().parents[1]

    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.update(config)

    _configure_logging()
    _ensure_storage_directories(
        Path(app.config["UPLOAD_DIR"]),
        Path(app.config["STEMS_DIR"]),
        Path(app.config["MIDI_DIR"]),
    )

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": app.config["CORS_ORIGINS"],
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type"],
                "expose_headers": ["Content-Disposition"],
                "max_age": 600,
            }
        },
    )

    app.config.setdefault("MAX_CONTENT_LENGTH", config["MAX_CONTENT_LENGTH"])

    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        """Serve the main web UI."""

        return render_template("index.html")

    _register_error_handlers(app)

    @app.get("/health")
    def health_endpoint():
        """Return service health information for monitoring and orchestration."""

        upload_dir = Path(app.config["UPLOAD_DIR"])
        stems_dir = Path(app.config["STEMS_DIR"])
        midi_dir = Path(app.config["MIDI_DIR"])

        directories = {
            "uploads": upload_dir,
            "stems": stems_dir,
            "midi": midi_dir,
        }

        directory_status: Dict[str, Dict[str, object]] = {}
        healthy = True
        for name, directory in directories.items():
            exists = directory.exists()
            writable = os.access(directory, os.W_OK) if exists else False
            directory_status[name] = {
                "path": str(directory.resolve()),
                "exists": exists,
                "writable": writable,
            }
            if not exists or not writable:
                healthy = False

        health_data = {
            "status": "healthy" if healthy else "degraded",
            "storage_root": str(Path(app.config["STORAGE_ROOT"]).resolve()),
            "directories": directory_status,
            "available_models": get_available_models(),
            "supported_stems": get_supported_stem_types(),
        }

        status_code = 200 if healthy else 503
        return jsonify(health_data), status_code

    return app


__all__ = [
    "create_app",
    "api_bp",
    "separate_audio",
    "convert_stem_to_midi",
    "convert_stems_to_combined_midi",
    "combine_midi_files",
]


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)


def _ensure_storage_directories(*directories: Path) -> None:
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def handle_bad_request(error):  # type: ignore[override]
        description = getattr(error, "description", "Bad request")
        return _create_error_response(
            "Bad request",
            400,
            {"detail": description},
        )

    @app.errorhandler(404)
    def handle_not_found(error):  # type: ignore[override]
        logger.debug("404 encountered: %s", error)
        return _create_error_response("Resource not found", 404)

    @app.errorhandler(413)
    def handle_request_entity_too_large(error):  # type: ignore[override]
        max_mb = app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
        message = f"File too large. Maximum size: {max_mb:.0f}MB"
        return _create_error_response(message, 413)

    @app.errorhandler(500)
    def handle_internal_server_error(error):  # type: ignore[override]
        logger.error("Internal server error: %s", error, exc_info=True)
        return _create_error_response("Internal server error", 500)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):  # type: ignore[override]
        logger.exception("Unhandled exception: %s", error)
        return _create_error_response("An unexpected error occurred", 500)


@api_bp.post("/separate")
def separate_endpoint():
    """Separate an uploaded audio file into stems.

    Expects ``multipart/form-data`` with a ``file`` field pointing to an audio
    file (MP3, WAV, FLAC, or OGG). Returns a JSON object containing the
    ``job_id`` and metadata (name, filename, file size, download URL) for each
    generated stem.
    """

    if "file" not in request.files:
        return _create_error_response("No file provided", 400)

    upload_file = request.files["file"]
    if not upload_file or not upload_file.filename:
        return _create_error_response("Invalid file upload", 400)

    if not _validate_audio_file(upload_file.filename):
        return _create_error_response(
            "Unsupported file type",
            400,
            {"supported_formats": sorted(current_app.config["ALLOWED_AUDIO_EXTENSIONS"])}
        )

    job_id = str(uuid.uuid4())
    upload_dir = Path(current_app.config["UPLOAD_DIR"]) / job_id
    stems_dir = Path(current_app.config["STEMS_DIR"]) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stems_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = secure_filename(upload_file.filename)
    upload_path = upload_dir / safe_filename

    try:
        upload_file.save(str(upload_path))
        stem_paths = separate_audio(str(upload_path), str(stems_dir))
    except ValueError as exc:
        logger.warning("Validation error during separation: %s", exc)
        return _create_error_response(str(exc), 400)
    except RuntimeError as exc:
        logger.error("Runtime error during separation: %s", exc, exc_info=True)
        return _create_error_response("Failed to separate audio", 500)
    except Exception as exc:  # noqa: BLE001
        if torch is not None and isinstance(exc, torch.cuda.OutOfMemoryError):
            logger.error("CUDA OOM during separation for job %s", job_id, exc_info=True)
            return _create_error_response(
                "Insufficient GPU memory to process this request",
                507,
            )
        logger.exception("Unexpected error during separation for job %s", job_id)
        return _create_error_response("An unexpected error occurred", 500)

    stems: List[Dict[str, object]] = []
    for stem_name, stem_file_path in sorted(stem_paths.items()):
        stem_path = Path(stem_file_path)
        file_name = stem_path.name
        stems.append(
            {
                "name": stem_name,
                "filename": file_name,
                "size": _get_file_size(stem_path),
                "download_url": _build_download_url(job_id, "stems", file_name),
                "download_url_encoded": _build_encoded_download_url(job_id, "stems", file_name),
                "stream_url": _build_stream_url(job_id, "stems", file_name),
            }
        )

    response_payload = {
        "job_id": job_id,
        "original_filename": safe_filename,
        "stems": stems,
    }

    if not current_app.config.get("RETAIN_UPLOADS", True):
        _cleanup_path(upload_path)
        _cleanup_directory(upload_dir)

    return _create_success_response(response_payload, "Audio separated successfully")


@api_bp.post("/convert-to-midi")
def convert_to_midi_endpoint():
    """Convert previously separated stems into a combined MIDI file.

    Expects a JSON payload containing ``job_id`` (UUID string) and optionally
    ``stem_names`` (list of stem identifiers). The response includes the
    download metadata for the combined MIDI file and the list of stems that were
    converted.
    """

    data = request.get_json(silent=True)
    if data is None:
        return _create_error_response("Invalid or missing JSON body", 400)

    job_id = data.get("job_id")
    if not job_id:
        return _create_error_response("'job_id' is required", 400)

    try:
        uuid.UUID(job_id)
    except ValueError:
        return _create_error_response("'job_id' must be a valid UUID", 400)

    stems_dir = Path(current_app.config["STEMS_DIR"]) / job_id
    if not stems_dir.exists():
        return _create_error_response("Job not found", 404)

    requested_stems: Optional[List[str]] = data.get("stem_names")
    if requested_stems is not None and not isinstance(requested_stems, list):
        return _create_error_response("'stem_names' must be a list", 400)

    stem_glob_patterns = ["*.wav", "*.flac", "*.ogg", "*.mp3"]
    stem_files = []
    for pattern in stem_glob_patterns:
        stem_files.extend(stems_dir.glob(pattern))
    if not stem_files:
        return _create_error_response(
            "No stems found for this job",
            404,
            {"expected_extensions": stem_glob_patterns},
        )

    stem_paths: Dict[str, str] = {}
    for stem_file in stem_files:
        # Expected naming convention: <base>_stem_<name>.wav
        parts = stem_file.stem.split("_stem_")
        stem_name = parts[-1] if len(parts) == 2 else stem_file.stem
        stem_paths[stem_name] = str(stem_file)

    if requested_stems:
        missing = sorted(set(requested_stems) - set(stem_paths))
        if missing:
            return _create_error_response(
                "Requested stems not found",
                404,
                {"missing": missing},
            )
        stem_paths = {name: stem_paths[name] for name in requested_stems}

    midi_dir = Path(current_app.config["MIDI_DIR"]) / job_id
    midi_dir.mkdir(parents=True, exist_ok=True)
    output_midi_path = midi_dir / "combined.mid"

    try:
        convert_stems_to_combined_midi(stem_paths, str(output_midi_path))
    except ValueError as exc:
        logger.warning("Validation error during MIDI conversion: %s", exc)
        return _create_error_response(str(exc), 400)
    except (RuntimeError, IOError) as exc:
        logger.error("Operational error during MIDI conversion: %s", exc, exc_info=True)
        return _create_error_response("Failed to convert stems to MIDI", 500)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during MIDI conversion for job %s", job_id)
        return _create_error_response("An unexpected error occurred", 500)

    midi_filename = output_midi_path.name
    response_payload = {
        "job_id": job_id,
        "midi_file": {
            "filename": midi_filename,
            "size": _get_file_size(output_midi_path),
            "download_url": _build_download_url(job_id, "midi", midi_filename),
            "download_url_encoded": _build_encoded_download_url(job_id, "midi", midi_filename),
        },
        "stems_converted": list(stem_paths.keys()),
    }
    if not current_app.config.get("RETAIN_STEMS", True):
        _cleanup_directory(stems_dir)

    return _create_success_response(response_payload, "Stems converted to MIDI successfully")


@api_bp.get("/download/<job_id>/<category>/<path:filename>")
def download_endpoint(job_id: str, category: str, filename: str):
    """Serve generated files (uploads, stems, or MIDI) as attachments."""

    try:
        uuid.UUID(job_id)
    except ValueError:
        return _create_error_response("'job_id' must be a valid UUID", 400)

    valid_categories = {
        "uploads": Path(current_app.config["UPLOAD_DIR"]),
        "stems": Path(current_app.config["STEMS_DIR"]),
        "midi": Path(current_app.config["MIDI_DIR"]),
    }
    if category not in valid_categories:
        return _create_error_response("Invalid download category", 400)

    base_dir = valid_categories[category] / job_id
    try:
        return send_from_directory(
            directory=str(base_dir),
            path=filename,
            as_attachment=True,
            download_name=secure_filename(filename),
        )
    except NotFound:
        return _create_error_response("File not found", 404)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Unexpected error while serving download (job=%s, category=%s, filename=%s)",
            job_id,
            category,
            filename,
        )
        return _create_error_response("An unexpected error occurred", 500)


@api_bp.get("/stream/<job_id>/<category>/<path:filename>")
def stream_endpoint(job_id: str, category: str, filename: str):
    """Serve files for inline streaming without forcing download prompts."""

    try:
        uuid.UUID(job_id)
    except ValueError:
        return _create_error_response("'job_id' must be a valid UUID", 400)

    if category != "stems":
        return _create_error_response("Streaming is only supported for stems", 400)

    base_dir = Path(current_app.config["STEMS_DIR"]) / job_id

    try:
        return send_from_directory(
            directory=str(base_dir),
            path=filename,
            as_attachment=False,
            conditional=True,
        )
    except NotFound:
        return _create_error_response("File not found", 404)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Unexpected error while streaming file (job=%s, filename=%s)",
            job_id,
            filename,
        )
        return _create_error_response("An unexpected error occurred", 500)


@api_bp.get("/download/<path:file_id>")
def download_encoded_endpoint(file_id: str):
    """Serve files using encoded identifier containing job metadata."""

    padding = "=" * (-len(file_id) % 4)
    try:
        decoded = base64.urlsafe_b64decode(file_id + padding)
        payload = json.loads(decoded)
    except (binascii.Error, json.JSONDecodeError) as exc:
        logger.debug("Failed to decode file identifier %s: %s", file_id, exc)
        return _create_error_response("Invalid file identifier", 400)

    job_id = payload.get("job_id")
    category = payload.get("category")
    filename = payload.get("filename")

    if not all(isinstance(value, str) for value in (job_id, category, filename)):
        return _create_error_response("Invalid file identifier", 400)

    return download_endpoint(job_id, category, filename)


def _validate_audio_file(filename: str) -> bool:
    """Return ``True`` if ``filename`` has a supported audio extension."""

    allowed_extensions = current_app.config["ALLOWED_AUDIO_EXTENSIONS"]
    return Path(filename).suffix.lower() in allowed_extensions


def _get_file_size(file_path: Path) -> int:
    """Return file size in bytes, or ``0`` if the file does not exist."""

    try:
        return file_path.stat().st_size
    except FileNotFoundError:
        return 0


def _build_download_url(job_id: str, category: str, filename: str) -> str:
    """Construct a download URL based on configuration."""

    safe_filename = secure_filename(filename)
    safe_category = secure_filename(category)
    relative_url = f"/api/download/{job_id}/{safe_category}/{safe_filename}"

    if current_app.config.get("ABSOLUTE_URLS", False) and has_request_context():
        return url_for("api.download_endpoint", job_id=job_id, category=safe_category, filename=safe_filename, _external=True)

    return relative_url


def _build_stream_url(job_id: str, category: str, filename: str) -> str:
    """Construct a streaming URL that keeps content inline."""

    safe_filename = secure_filename(filename)
    safe_category = secure_filename(category)
    relative_url = f"/api/stream/{job_id}/{safe_category}/{safe_filename}"

    if current_app.config.get("ABSOLUTE_URLS", False) and has_request_context():
        return url_for(
            "api.stream_endpoint",
            job_id=job_id,
            category=safe_category,
            filename=safe_filename,
            _external=True,
        )

    return relative_url


def _build_encoded_download_url(job_id: str, category: str, filename: str) -> str:
    payload = json.dumps({"job_id": job_id, "category": category, "filename": filename})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    relative_url = f"/api/download/{encoded}"
    if current_app.config.get("ABSOLUTE_URLS", False) and has_request_context():
        return request.host_url.rstrip("/") + relative_url
    return relative_url


def _create_success_response(data: Dict[str, object], message: str = "Success") -> Tuple[object, int]:
    """Wrap ``data`` in the canonical success JSON envelope."""

    return jsonify({"status": "success", "data": data, "message": message}), 200


def _create_error_response(
    message: str,
    status_code: int,
    details: Optional[Dict[str, object]] = None,
) -> Tuple[object, int]:
    """Return a JSON error response tuple suitable for Flask."""

    payload: Dict[str, object] = {"status": "error", "message": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def _cleanup_path(file_path: Path) -> None:
    try:
        file_path.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to delete file %s: %s", file_path, exc)


def _cleanup_directory(directory: Path) -> None:
    try:
        if not directory.exists():
            return
        if any(directory.iterdir()):
            shutil.rmtree(directory)
        else:
            directory.rmdir()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to delete directory %s: %s", directory, exc)


if __name__ == "__main__":
    app = create_app()

    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    logger.info(
        "Starting MP3paraMIDI Flask app on %s:%s (debug=%s)",
        host,
        port,
        debug,
    )

    # For production use a WSGI server like Gunicorn or uWSGI instead of the Flask dev server.
    app.run(host=host, port=port, debug=debug)
