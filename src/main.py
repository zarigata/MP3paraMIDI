"""Unified FastAPI server that mounts the existing Flask app and Gradio interface.

This entry point creates a FastAPI application, mounts the Flask web/API server
via ``a2wsgi.WSGIMiddleware``, and mounts the Gradio Blocks interface using
``gradio.mount_gradio_app``. Running this module with ``python src/main.py``
starts a single uvicorn process that serves:

* Flask web UI at ``/``
* Flask API at ``/api``
* Gradio interface at ``/gradio``

Rationale
---------
``gradio.mount_gradio_app`` only supports FastAPI parents. By wrapping the
existing Flask app inside FastAPI we can provide a unified deployment target
without rewriting existing routes. ``a2wsgi`` is used instead of Starlette's
legacy adapter because it supports more WSGI features and modern async patterns.

Environment variables
---------------------
``APP_HOST``
    Host interface for uvicorn (default ``0.0.0.0``).
``APP_PORT``
    Port for uvicorn (default ``8000``).
``GRADIO_SHARE``
    Boolean flag indicating whether share mode is requested (informational only;
    sharing is not available in mounted mode).
``GRADIO_AUTH``
    Optional ``username:password`` pair for HTTP basic auth on the Gradio route.

Usage
-----
Run locally:

>>> python src/main.py

Production example (uvicorn CLI):

>>> uvicorn src.main:create_unified_app --factory --host 0.0.0.0 --port 8000 --workers 4

For public access in mounted mode use a tunneling service such as ngrok.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from gradio import mount_gradio_app

from src.app import create_app
from src.gradio_app import create_gradio_interface

logger = logging.getLogger(__name__)

HOST = os.getenv("APP_HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", "8000"))
GRADIO_SHARE = os.getenv("GRADIO_SHARE", "False").lower() == "true"
GRADIO_AUTH_RAW = os.getenv("GRADIO_AUTH", "")


def _parse_auth(raw: str) -> Optional[Tuple[str, str]]:
    """Parse ``username:password`` from *raw* and return ``None`` if invalid."""

    if raw and ":" in raw:
        username, password = raw.split(":", 1)
        return username.strip(), password.strip()
    return None


def create_unified_app() -> FastAPI:
    """Create and return the FastAPI parent application."""

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
    )

    app = FastAPI(
        title="MP3paraMIDI",
        description="AI-powered audio separation and MIDI conversion",
        version="1.0.0",
    )

    flask_app = create_app()
    gradio_interface = create_gradio_interface()

    @app.get("/api/health-fastapi", tags=["health"])
    async def fastapi_healthcheck() -> JSONResponse:  # pragma: no cover - simple response
        return JSONResponse({"status": "ok", "framework": "fastapi"})

    app.mount("/", WSGIMiddleware(flask_app))

    auth = _parse_auth(GRADIO_AUTH_RAW)
    mount_gradio_app(app, gradio_interface, path="/gradio", auth=auth)

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_unified_app()

    logger.info("Starting MP3paraMIDI unified server")
    logger.info("Flask Web UI: http://%s:%s/", HOST, PORT)
    logger.info("Flask API: http://%s:%s/api/", HOST, PORT)
    logger.info("Gradio Interface: http://%s:%s/gradio", HOST, PORT)

    if GRADIO_SHARE:
        logger.warning(
            "share=True requested but unsupported in mounted mode. Use ngrok or the "
            "standalone launcher for public URLs."
        )

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
