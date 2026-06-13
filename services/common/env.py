"""Load .env from project root (idempotent)."""

from __future__ import annotations

import os
from pathlib import Path

_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_dotenv() -> None:
    global _LOADED
    if _LOADED:
        return

    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

    _LOADED = True
