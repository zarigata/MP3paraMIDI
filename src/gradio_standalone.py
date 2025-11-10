"""Standalone launcher for the MP3paraMIDI Gradio interface.

The unified server (:mod:`src.main`) mounts the Gradio app alongside Flask, but
Gradio's ``share=True`` functionality is not available when mounted. This script
provides an alternative entry point that runs the interface independently with
optional public sharing and HTTP basic authentication.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from src.gradio_app import create_gradio_interface


logger = logging.getLogger(__name__)

HOST = os.getenv("GRADIO_HOST", "0.0.0.0")
PORT = int(os.getenv("GRADIO_PORT", "7860"))
SHARE = os.getenv("GRADIO_SHARE", "False").lower() == "true"
AUTH_RAW = os.getenv("GRADIO_AUTH", "")


def _parse_auth(raw: str) -> Optional[Tuple[str, str]]:
    """Return a ``(username, password)`` tuple parsed from ``raw`` if valid."""

    if raw and ":" in raw:
        username, password = raw.split(":", 1)
        return username.strip(), password.strip()
    return None


def main() -> None:
    """Launch the Gradio Blocks interface in standalone mode."""

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
    )

    demo = create_gradio_interface()
    auth = _parse_auth(AUTH_RAW)

    if SHARE:
        logger.info(
            "Public sharing enabled - a gradio.live URL will be displayed after launch."
        )
    else:
        logger.info("Share mode disabled - serving on http://%s:%s", HOST, PORT)

    if auth:
        logger.info("Authentication enabled for Gradio interface (user=%s)", auth[0])

    demo.launch(
        server_name=HOST,
        server_port=PORT,
        share=SHARE,
        auth=auth,
    )


if __name__ == "__main__":
    main()
