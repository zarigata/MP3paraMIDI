"""Test configuration for MP3paraMIDI test suite."""
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    """Prepend the repository src directory to sys.path for imports."""
    root = Path(__file__).resolve().parent.parent
    src_path = root / "src"
    if src_path.exists():
        src_str = str(src_path)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)


_ensure_src_on_path()
