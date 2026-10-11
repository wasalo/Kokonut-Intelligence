"""Encrypted private field-media files on a single-node filesystem."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from pathlib import Path

from services.mobile.media_storage import ALLOWED_CONTENT_TYPES, MAX_MEDIA_BYTES, MediaStorageNotConfigured

MAGIC = b"KKM1"


class LocalMediaStore:
    def __init__(self, directory: str, encryption_key: str):
        try:
            self._key = bytes.fromhex(encryption_key)
        except ValueError as exc:
            raise MediaStorageNotConfigured("Local media requires a 32-byte hex encryption key") from exc
        if len(self._key) != 32:
            raise MediaStorageNotConfigured("Local media requires a 32-byte hex encryption key")
        root = Path(directory)
        if not root.is_absolute() or root.is_symlink():
            raise MediaStorageNotConfigured("Local media directory must be an absolute private directory")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not root.is_dir() or root.stat().st_uid != os.getuid() or stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise MediaStorageNotConfigured("Local media directory must be owned by the app with mode 0700")
        self._root = root.resolve()
        try:
            from Crypto.Cipher import AES
        except ImportError as exc:
            raise MediaStorageNotConfigured("Local media encryption driver is unavailable") from exc
        self._aes = AES

    def _path(self, key: str) -> Path:
        if not key.startswith("private/field-collector/") or any(part in {"", ".", ".."} for part in key.split("/")):
            raise ValueError("Invalid private media key")
        return self._root / (hashlib.sha256(key.encode()).hexdigest() + ".bin")

    def _sync_directory(self):
        descriptor = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def put_private(self, key: str, body: bytes, content_type: str) -> None:
        if content_type not in ALLOWED_CONTENT_TYPES or not body or len(body) > MAX_MEDIA_BYTES:
            raise ValueError("Unsupported private media type or size")
        path = self._path(key)
        nonce = os.urandom(12)
        cipher = self._aes.new(self._key, self._aes.MODE_GCM, nonce=nonce)
        cipher.update(MAGIC + key.encode())
        ciphertext, tag = cipher.encrypt_and_digest(body)
        descriptor, temporary = tempfile.mkstemp(prefix=".upload-", dir=self._root)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(MAGIC + nonce + tag + ciphertext)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)  # Never overwrite an existing immutable object.
            self._sync_directory()
        finally:
            os.unlink(temporary)

    def head_private(self, key: str) -> dict:
        descriptor = os.open(self._path(key), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Invalid private media object")
            envelope = stream.read(MAX_MEDIA_BYTES + 33)
        if not 32 < len(envelope) <= MAX_MEDIA_BYTES + 32 or envelope[:4] != MAGIC:
            raise ValueError("Invalid private media envelope")
        cipher = self._aes.new(self._key, self._aes.MODE_GCM, nonce=envelope[4:16])
        cipher.update(MAGIC + key.encode())
        plaintext = cipher.decrypt_and_verify(envelope[32:], envelope[16:32])
        return {"ContentLength": len(plaintext), "ContentType": "image/jpeg"}

    def delete_private(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
        self._sync_directory()
