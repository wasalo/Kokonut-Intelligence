"""Authenticated envelope for private Field Collector media objects."""

from __future__ import annotations

import re
from collections.abc import Callable

MEDIA_ENVELOPE_MAGIC = b"KKM1"
MEDIA_ENVELOPE_OVERHEAD = 32  # magic, 96-bit nonce, and 128-bit GCM tag


class MediaEnvelopeError(ValueError):
    """A private media envelope is malformed or fails authentication."""


def parse_media_encryption_key(value: str) -> bytes:
    """Parse the SOPS-managed 256-bit media key without exposing its value."""
    if not isinstance(value, str):
        raise MediaEnvelopeError("media encryption key is invalid")
    if re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
        raise MediaEnvelopeError("media encryption key is invalid")
    return bytes.fromhex(value)


def _aes_module():
    try:
        from Crypto.Cipher import AES
    except ImportError:
        raise MediaEnvelopeError("media encryption driver is unavailable") from None
    return AES


def encrypt_media_envelope(
    plaintext: bytes,
    key: bytes,
    object_key: str,
    *,
    random_bytes: Callable[[int], bytes],
) -> bytes:
    """Encrypt one object; authenticate its immutable private object key."""
    if (
        not isinstance(plaintext, bytes)
        or not isinstance(key, bytes)
        or len(key) != 32
        or not isinstance(object_key, str)
    ):
        raise MediaEnvelopeError("private media input is invalid")
    nonce = random_bytes(12)
    if not isinstance(nonce, bytes) or len(nonce) != 12:
        raise MediaEnvelopeError("private media nonce is invalid")
    aes = _aes_module()
    cipher = aes.new(key, aes.MODE_GCM, nonce=nonce)
    cipher.update(MEDIA_ENVELOPE_MAGIC + object_key.encode("utf-8"))
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return MEDIA_ENVELOPE_MAGIC + nonce + tag + ciphertext


def decrypt_media_envelope(envelope: bytes, key: bytes, object_key: str) -> bytes:
    """Authenticate and decrypt one object for storage verification/recovery."""
    if (
        not isinstance(envelope, bytes)
        or not isinstance(key, bytes)
        or len(key) != 32
        or not isinstance(object_key, str)
        or len(envelope) <= MEDIA_ENVELOPE_OVERHEAD
        or envelope[:4] != MEDIA_ENVELOPE_MAGIC
    ):
        raise MediaEnvelopeError("private media envelope is invalid")
    try:
        aes = _aes_module()
        cipher = aes.new(key, aes.MODE_GCM, nonce=envelope[4:16])
        cipher.update(MEDIA_ENVELOPE_MAGIC + object_key.encode("utf-8"))
        return cipher.decrypt_and_verify(envelope[32:], envelope[16:32])
    except MediaEnvelopeError:
        raise
    except Exception:
        raise MediaEnvelopeError("private media envelope authentication failed") from None
