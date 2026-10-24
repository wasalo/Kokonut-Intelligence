"""Keyed integrity helpers for encrypted Kernel backup manifests."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

_ALGORITHM = "pbkdf2-hmac-sha256+hmac-sha256"
_ITERATIONS = 600_000
_MIN_ITERATIONS = 100_000
_MAX_ITERATIONS = 2_000_000


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Serialize a manifest deterministically for signatures and transport."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _signing_key(secret: str, salt: bytes, iterations: int) -> bytes:
    if not secret:
        raise ValueError("BACKUP_ENCRYPTION_KEY must be set to authenticate the manifest")
    if not _MIN_ITERATIONS <= iterations <= _MAX_ITERATIONS:
        raise ValueError("Backup manifest key-derivation work factor is outside supported bounds")
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations, dklen=32)


def sign_manifest(manifest: dict[str, Any], secret: str) -> dict[str, Any]:
    """Return a signed copy; the signature covers every field except itself."""
    unsigned = dict(manifest)
    unsigned.pop("integrity", None)
    salt = secrets.token_bytes(32)
    key = _signing_key(secret, salt, _ITERATIONS)
    signature = hmac.new(key, canonical_manifest_bytes(unsigned), hashlib.sha256).hexdigest()
    unsigned["integrity"] = {
        "algorithm": _ALGORITHM,
        "iterations": _ITERATIONS,
        "salt": salt.hex(),
        "hmac_sha256": signature,
    }
    return unsigned


def verify_manifest_signature(manifest: dict[str, Any], secret: str, *, required: bool = False) -> bool:
    """Verify a signed manifest, accepting unsigned legacy manifests only when optional."""
    integrity = manifest.get("integrity")
    if integrity is None:
        if required:
            raise ValueError("Backup manifest is unsigned; recreate it before remote upload")
        return False
    if not isinstance(integrity, dict) or integrity.get("algorithm") != _ALGORITHM:
        raise ValueError("Unsupported backup manifest integrity format")
    iterations = integrity.get("iterations")
    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise ValueError("Invalid backup manifest key-derivation work factor")
    try:
        salt = bytes.fromhex(integrity["salt"])
        supplied = integrity["hmac_sha256"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid backup manifest integrity record") from error
    if len(salt) != 32 or not isinstance(supplied, str) or len(supplied) != 64:
        raise ValueError("Invalid backup manifest integrity record")
    unsigned = dict(manifest)
    unsigned.pop("integrity", None)
    key = _signing_key(secret, salt, iterations)
    expected = hmac.new(key, canonical_manifest_bytes(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("Backup manifest authentication failed")
    return True
