"""Load .env.sops (SOPS-encrypted) or .env from project root (idempotent)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

_LOADED = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PLACEHOLDER_RE = re.compile(r"^(replace-with|your[_-]|change[_-]me|todo|none|null|0x\.\.\.)", re.IGNORECASE)
_PRODUCTION_REQUIRED = ("PG_HOST", "PG_DB", "PG_USER", "PG_PASSWORD")


class SecretLoadError(RuntimeError):
    """Raised when runtime secret loading cannot satisfy its policy."""


def _parse_dotenv(content: str) -> None:
    """Parse dotenv content and set environment variables."""
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if not _KEY_RE.fullmatch(key):
                raise SecretLoadError("invalid dotenv variable name")
            value = value.strip()
            # Strip surrounding quotes ("..." or '...')
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)


def _load_via_sops(sops_path: Path) -> bool:
    """Decrypt .env.sops via sops CLI and load variables."""
    if not sops_path.exists():
        return False

    # Check sops is available
    try:
        result = subprocess.run(
            # No --input-type/--output-type: sops stores the original format in its
            # metadata and auto-detects it on decrypt. Forcing dotenv here makes
            # sops re-parse its own JSON envelope as dotenv and fail.
            ["sops", "-d", str(sops_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        _parse_dotenv(result.stdout)
        return True
    except FileNotFoundError as exc:
        raise SecretLoadError("sops is not installed") from exc
    except subprocess.CalledProcessError as exc:
        raise SecretLoadError("SOPS decryption failed") from exc
    except subprocess.TimeoutExpired as exc:
        raise SecretLoadError("SOPS decryption timed out") from exc


def _load_via_dotenv(env_path: Path) -> bool:
    """Load plaintext .env file."""
    if not env_path.exists():
        return False

    with open(env_path) as f:
        _parse_dotenv(f.read())
    return True


def _dotenv_flag(env_path: Path, key: str) -> str | None:
    """Read one non-secret policy flag without executing dotenv content."""
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip("\"'")
    return None


def _plaintext_allowed(env_path: Path) -> bool:
    """Return whether an explicit local/test plaintext opt-in is active."""
    explicit = os.environ.get("KOKONUT_ALLOW_PLAINTEXT_ENV")
    if explicit is None:
        explicit = _dotenv_flag(env_path, "KOKONUT_ALLOW_PLAINTEXT_ENV")
    if str(explicit).lower() == "true":
        return True
    return False


def _validate_production_environment() -> None:
    """Reject missing or example credentials in CI/production."""
    for key in _PRODUCTION_REQUIRED:
        value = os.environ.get(key, "").strip()
        if not value:
            raise SecretLoadError(f"required environment variable is missing: {key}")
        if _PLACEHOLDER_RE.match(value):
            raise SecretLoadError(f"placeholder environment value is not allowed: {key}")


def load_dotenv() -> None:
    global _LOADED
    if _LOADED:
        return

    sops_path = _PROJECT_ROOT / ".env.sops"
    env_path = _PROJECT_ROOT / ".env"

    # Prefer encrypted .env.sops. A failed decrypt never silently downgrades
    # to plaintext unless development/test explicitly opted into that mode.
    if sops_path.exists():
        try:
            _load_via_sops(sops_path)
        except SecretLoadError:
            if not _plaintext_allowed(env_path):
                raise
            if not _load_via_dotenv(env_path):
                raise SecretLoadError("SOPS failed and plaintext .env is unavailable")
    elif env_path.exists():
        if not _plaintext_allowed(env_path):
            raise SecretLoadError("plaintext .env requires explicit development opt-in")
        _load_via_dotenv(env_path)
    elif os.environ.get("KOKONUT_ENV", "development").lower() != "development":
        # Container runtimes commonly inject secrets directly rather than
        # mounting a dotenv file. The validation below still rejects missing
        # or placeholder credentials in CI and production.
        if not all(os.environ.get(key, "").strip() for key in _PRODUCTION_REQUIRED):
            raise SecretLoadError("no encrypted or plaintext environment source found")

    if os.environ.get("KOKONUT_ENV", "development").lower() in {"ci", "production"}:
        _validate_production_environment()
    _LOADED = True


def get_db():
    """Return a psycopg2 connection.

    Delegates to :func:`services.common.database.get_db` (the canonical
    connection factory).  This exists so that the ~50 modules which do
    ``from services.common.database import get_db`` resolve to a real
    connection factory without changing every import site.
    """
    from services.common.database import get_db as _canonical_get_db

    load_dotenv()  # ensure env vars are populated
    return _canonical_get_db()
