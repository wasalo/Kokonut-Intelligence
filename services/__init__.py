"""Shared package metadata for Kokonut Intelligence services."""

import os
from pathlib import Path


_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
__version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
__git_sha__ = os.environ.get("KOKONUT_GIT_SHA", "unknown")
