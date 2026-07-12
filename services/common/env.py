"""Load .env.sops (SOPS-encrypted) or .env from project root (idempotent)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _parse_dotenv(content: str) -> None:
    """Parse dotenv content and set environment variables."""
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            value = value.strip()
            # Strip surrounding quotes ("..." or '...')
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


def _load_via_sops(sops_path: Path) -> bool:
    """Decrypt .env.sops via sops CLI and load variables."""
    if not sops_path.exists():
        return False

    # Check sops is available
    try:
        result = subprocess.run(
            ["sops", "-d", "--input-type", "dotenv", "--output-type", "dotenv", str(sops_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        _parse_dotenv(result.stdout)
        return True
    except FileNotFoundError:
        # sops not installed — fall back to plaintext .env
        return False
    except subprocess.CalledProcessError:
        # Decryption failed (missing key, etc.)
        return False
    except subprocess.TimeoutExpired:
        return False


def _load_via_dotenv(env_path: Path) -> bool:
    """Load plaintext .env file."""
    if not env_path.exists():
        return False

    with open(env_path) as f:
        _parse_dotenv(f.read())
    return True


def load_dotenv() -> None:
    global _LOADED
    if _LOADED:
        return

    sops_path = _PROJECT_ROOT / ".env.sops"
    env_path = _PROJECT_ROOT / ".env"

    # Prefer encrypted .env.sops, fall back to plaintext .env
    if not _load_via_sops(sops_path):
        _load_via_dotenv(env_path)

    _LOADED = True
