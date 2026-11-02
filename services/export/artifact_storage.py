"""Private artifact storage ports for asynchronous exports.

The local implementation is intended for development and edge deployments.
It stores artifacts under opaque UUID names, never returns a path or URL, and
does not apply a retention policy. Callers must explicitly delete artifacts
only after an authorized disposition decision.
"""

from __future__ import annotations

import errno
import os
import secrets
import stat
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import UUID

MAX_PRIVATE_EXPORT_BYTES = 512 * 1024
_S3_EXPORT_PREFIX = "private/report-snapshot-exports/"


class ArtifactStorageError(RuntimeError):
    """A safe, path-free storage error suitable for application logs."""


class PrivateArtifactStore(Protocol):
    """Private artifact operations keyed by opaque UUID identifiers."""

    def write(self, artifact_id: UUID | str, content: bytes) -> None: ...

    def read(
        self, artifact_id: UUID | str, *, max_bytes: int | None = None
    ) -> bytes: ...

    def delete(self, artifact_id: UUID | str) -> None: ...


def _artifact_name(artifact_id: UUID | str) -> str:
    if isinstance(artifact_id, UUID):
        normalized = str(artifact_id)
    elif isinstance(artifact_id, str):
        try:
            parsed = UUID(artifact_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("artifact identifier must be a UUID") from exc
        if str(parsed) != artifact_id.lower():
            raise ValueError("artifact identifier must be a canonical UUID")
        normalized = str(parsed)
    else:
        raise ValueError("artifact identifier must be a UUID")
    return f"{normalized}.artifact"


class LocalPrivateArtifactStore:
    """Atomically store private files in an owner-only local directory.

    The artifact directory and each file are restricted to the current user
    (0700 and 0600 respectively). All object operations are relative to an
    opened directory descriptor and refuse symlinks and non-regular files.
    """

    _DIRECTORY_MODE = 0o700
    _FILE_MODE = 0o600

    def __init__(self, directory: str | os.PathLike[str]):
        if not isinstance(directory, (str, os.PathLike)):
            raise ValueError("artifact storage directory is required")
        raw_directory = os.fspath(directory)
        if not isinstance(raw_directory, str) or not raw_directory.strip():
            raise ValueError("artifact storage directory is required")

        root = Path(os.path.abspath(os.path.expanduser(raw_directory)))
        if root == Path(root.anchor):
            raise ValueError("artifact storage requires a dedicated directory")
        self._directory = root
        try:
            directory_fd = self._open_directory()
            os.close(directory_fd)
        except ArtifactStorageError:
            raise
        except OSError:
            raise ArtifactStorageError("artifact storage directory is unavailable") from None

    def __repr__(self) -> str:
        return "LocalPrivateArtifactStore(<private>)"

    def write(self, artifact_id: UUID | str, content: bytes) -> None:
        """Atomically create or replace an artifact; retries with the same ID are safe."""
        filename = _artifact_name(artifact_id)
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")

        directory_fd = self._open_directory()
        temporary_name = f".artifact-{secrets.token_hex(16)}.tmp"
        file_fd: int | None = None
        temporary_created = False
        try:
            self._require_safe_existing_file(directory_fd, filename, missing_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | self._nofollow_flag()
            file_fd = os.open(
                temporary_name,
                flags,
                self._FILE_MODE,
                dir_fd=directory_fd,
            )
            temporary_created = True
            os.fchmod(file_fd, self._FILE_MODE)
            view = memoryview(content)
            offset = 0
            while offset < len(view):
                written = os.write(file_fd, view[offset:])
                if written <= 0:
                    raise OSError("artifact write made no progress")
                offset += written
            os.fsync(file_fd)
            os.close(file_fd)
            file_fd = None
            os.replace(
                temporary_name,
                filename,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            temporary_created = False
            os.fsync(directory_fd)
        except ArtifactStorageError:
            raise
        except OSError:
            raise ArtifactStorageError("private artifact write failed") from None
        finally:
            if file_fd is not None:
                try:
                    os.close(file_fd)
                except OSError:
                    pass
            if temporary_created:
                self._remove_temporary(directory_fd, temporary_name)
            os.close(directory_fd)

    def read(
        self, artifact_id: UUID | str, *, max_bytes: int | None = None
    ) -> bytes:
        """Read an artifact, optionally enforcing a strict in-memory size cap."""
        filename = _artifact_name(artifact_id)
        _validate_read_limit(max_bytes)
        directory_fd = self._open_directory()
        file_fd: int | None = None
        try:
            file_fd = os.open(
                filename,
                os.O_RDONLY | self._nofollow_flag(),
                dir_fd=directory_fd,
            )
            self._require_private_regular_file(file_fd)
            if max_bytes is not None and os.fstat(file_fd).st_size > max_bytes:
                raise ArtifactStorageError("private artifact exceeds read limit")
            chunks: list[bytes] = []
            total = 0
            while True:
                remaining_with_overflow_byte = (
                    None if max_bytes is None else max_bytes + 1 - total
                )
                chunk_size = (
                    1024 * 1024
                    if remaining_with_overflow_byte is None
                    else min(64 * 1024, remaining_with_overflow_byte)
                )
                chunk = os.read(file_fd, chunk_size)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise ArtifactStorageError("private artifact exceeds read limit")
        except OSError:
            raise ArtifactStorageError("private artifact is unavailable") from None
        finally:
            if file_fd is not None:
                os.close(file_fd)
            os.close(directory_fd)

    def delete(self, artifact_id: UUID | str) -> None:
        """Explicitly remove one artifact; deleting an already absent ID is safe."""
        filename = _artifact_name(artifact_id)
        directory_fd = self._open_directory()
        try:
            if not self._require_safe_existing_file(
                directory_fd, filename, missing_ok=True
            ):
                return
            os.unlink(filename, dir_fd=directory_fd)
            os.fsync(directory_fd)
        except ArtifactStorageError:
            raise
        except OSError:
            raise ArtifactStorageError("private artifact deletion failed") from None
        finally:
            os.close(directory_fd)

    def _open_directory(self) -> int:
        directory_fd: int | None = None
        try:
            directory_flag = getattr(os, "O_DIRECTORY", None)
            if directory_flag is None:
                raise ArtifactStorageError("platform cannot enforce private artifact paths")
            flags = os.O_RDONLY | directory_flag | self._nofollow_flag()
            directory_fd = os.open(self._directory.anchor, flags)
            for component in self._directory.parts[1:]:
                try:
                    next_fd = os.open(component, flags, dir_fd=directory_fd)
                except FileNotFoundError:
                    try:
                        os.mkdir(component, self._DIRECTORY_MODE, dir_fd=directory_fd)
                    except FileExistsError:
                        pass
                    next_fd = os.open(component, flags, dir_fd=directory_fd)
                except OSError as exc:
                    try:
                        metadata = os.stat(component, dir_fd=directory_fd, follow_symlinks=False)
                    except OSError:
                        raise ArtifactStorageError(
                            "artifact storage directory is unavailable"
                        ) from None
                    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                        raise ArtifactStorageError(
                            "artifact storage directory is unsafe"
                        ) from None
                    if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                        raise ArtifactStorageError(
                            "artifact storage directory is unsafe"
                        ) from None
                    raise ArtifactStorageError(
                        "artifact storage directory is unavailable"
                    ) from None
                previous_fd = directory_fd
                directory_fd = next_fd
                os.close(previous_fd)
            if not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
                raise ArtifactStorageError("artifact storage directory is unsafe")
            os.fchmod(directory_fd, self._DIRECTORY_MODE)
            return directory_fd
        except ArtifactStorageError:
            if directory_fd is not None:
                os.close(directory_fd)
            raise
        except OSError:
            if directory_fd is not None:
                os.close(directory_fd)
            raise ArtifactStorageError("artifact storage directory is unavailable") from None

    @staticmethod
    def _nofollow_flag() -> int:
        flag = getattr(os, "O_NOFOLLOW", None)
        if flag is None:
            raise ArtifactStorageError("platform cannot enforce private artifact paths")
        return flag

    @classmethod
    def _require_safe_existing_file(
        cls, directory_fd: int, filename: str, *, missing_ok: bool = False
    ) -> bool:
        try:
            metadata = os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            if missing_ok:
                return False
            raise
        except OSError:
            raise ArtifactStorageError("private artifact is unsafe") from None
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise ArtifactStorageError("private artifact is unsafe")
        return True

    @classmethod
    def _require_private_regular_file(cls, file_fd: int) -> None:
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise ArtifactStorageError("private artifact is unsafe")

    @staticmethod
    def _remove_temporary(directory_fd: int, filename: str) -> None:
        try:
            os.unlink(filename, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        except OSError:
            # Do not replace the original error with cleanup details or paths.
            pass


class S3PrivateArtifactStore:
    """Private S3-compatible store for report exports, including Cloudflare R2.

    Object keys are derived only from canonical UUIDs. The adapter never
    returns URLs, bucket names, keys, or provider exception details.
    """

    def __init__(self, client: Any, bucket: str, *, read_only: bool = False):
        if client is None or not isinstance(bucket, str) or not bucket.strip():
            raise ValueError("private export object storage is not configured")
        self._client = client
        self._bucket = bucket.strip()
        self._read_only = read_only

    def __repr__(self) -> str:
        return "S3PrivateArtifactStore(<private>)"

    def write(self, artifact_id: UUID | str, content: bytes) -> None:
        if self._read_only:
            raise ArtifactStorageError("private artifact store is read-only")
        key = _S3_EXPORT_PREFIX + _artifact_name(artifact_id)
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")
        if not content or len(content) > MAX_PRIVATE_EXPORT_BYTES:
            raise ArtifactStorageError(
                "private artifact size is outside the allowed range"
            )
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ContentType="application/json",
            )
        except Exception:
            raise ArtifactStorageError("private artifact write failed") from None

    def read(
        self, artifact_id: UUID | str, *, max_bytes: int | None = None
    ) -> bytes:
        key = _S3_EXPORT_PREFIX + _artifact_name(artifact_id)
        _validate_read_limit(max_bytes)
        if max_bytes is None:
            raise ValueError("S3 artifact reads require a byte limit")
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception:
            raise ArtifactStorageError("private artifact is unavailable") from None
        if not isinstance(response, Mapping):
            raise ArtifactStorageError("private artifact is unavailable")
        body = response.get("Body")
        if body is None or not callable(getattr(body, "read", None)):
            raise ArtifactStorageError("private artifact is unavailable")
        content_length = response.get("ContentLength")
        if (
            isinstance(content_length, bool)
            or (content_length is not None and not isinstance(content_length, int))
            or (content_length is not None and content_length < 0)
        ):
            self._close_body(body)
            raise ArtifactStorageError("private artifact metadata is invalid")
        if max_bytes is not None and content_length is not None and content_length > max_bytes:
            self._close_body(body)
            raise ArtifactStorageError("private artifact exceeds read limit")

        chunks: list[bytes] = []
        total = 0
        try:
            while True:
                remaining_with_overflow_byte = (
                    None if max_bytes is None else max_bytes + 1 - total
                )
                chunk_size = (
                    64 * 1024
                    if remaining_with_overflow_byte is None
                    else min(64 * 1024, remaining_with_overflow_byte)
                )
                chunk = body.read(chunk_size)
                if not isinstance(chunk, bytes):
                    raise ArtifactStorageError("private artifact stream is invalid")
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise ArtifactStorageError("private artifact exceeds read limit")
            if content_length is not None and total != content_length:
                raise ArtifactStorageError("private artifact size is inconsistent")
            return b"".join(chunks)
        except ArtifactStorageError:
            raise
        except Exception:
            raise ArtifactStorageError("private artifact is unavailable") from None
        finally:
            self._close_body(body)

    def delete(self, artifact_id: UUID | str) -> None:
        if self._read_only:
            raise ArtifactStorageError("private artifact store is read-only")
        key = _S3_EXPORT_PREFIX + _artifact_name(artifact_id)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception:
            raise ArtifactStorageError("private artifact deletion failed") from None

    @staticmethod
    def _close_body(body: Any) -> None:
        close = getattr(body, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


def _validate_read_limit(max_bytes: int | None) -> None:
    if max_bytes is not None and (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or max_bytes < 0
    ):
        raise ValueError("artifact read limit must be a non-negative integer")


def _default_s3_client_factory(**kwargs):
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise ArtifactStorageError(
            "S3-compatible artifact storage client is unavailable"
        ) from exc
    return boto3.client("s3", config=Config(signature_version="s3v4"), **kwargs)


def create_private_artifact_store(
    environ: Mapping[str, str] | None = None,
    *,
    client_factory: Callable[..., Any] | None = None,
    access: str = "worker",
) -> PrivateArtifactStore:
    """Create the configured local or optional S3-compatible artifact adapter."""
    if access not in {"reader", "worker"}:
        raise ArtifactStorageError("unknown private export storage access role")
    source = os.environ if environ is None else environ
    provider = str(source.get("KOKONUT_PRIVATE_EXPORT_PROVIDER", "local")).strip().lower()
    if provider == "local":
        directory = str(source.get("KOKONUT_PRIVATE_EXPORT_DIR", "")).strip()
        if not directory:
            raise ArtifactStorageError("private export storage is not configured")
        return LocalPrivateArtifactStore(directory)
    if provider != "s3":
        raise ArtifactStorageError("unknown private export storage provider")

    access_key_name = f"KOKONUT_PRIVATE_EXPORT_S3_{access.upper()}_ACCESS_KEY_ID"
    secret_key_name = f"KOKONUT_PRIVATE_EXPORT_S3_{access.upper()}_SECRET_ACCESS_KEY"
    names = (
        "KOKONUT_PRIVATE_EXPORT_S3_ENDPOINT",
        "KOKONUT_PRIVATE_EXPORT_S3_BUCKET",
        access_key_name,
        secret_key_name,
        "KOKONUT_PRIVATE_EXPORT_S3_REGION",
    )
    values = {name: str(source.get(name, "")).strip() for name in names}
    if any(not value for value in values.values()):
        raise ArtifactStorageError("private export object storage is not configured")
    endpoint = urlsplit(values["KOKONUT_PRIVATE_EXPORT_S3_ENDPOINT"])
    local_http = endpoint.scheme == "http" and endpoint.hostname in {
        "localhost", "127.0.0.1", "::1"
    }
    if (
        not endpoint.hostname
        or (endpoint.scheme != "https" and not local_http)
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
    ):
        raise ArtifactStorageError("private export endpoint must use HTTPS")
    factory = client_factory or _default_s3_client_factory
    try:
        client = factory(
            endpoint_url=values["KOKONUT_PRIVATE_EXPORT_S3_ENDPOINT"],
            region_name=values["KOKONUT_PRIVATE_EXPORT_S3_REGION"],
            aws_access_key_id=values[access_key_name],
            aws_secret_access_key=values[secret_key_name],
        )
    except ArtifactStorageError:
        raise
    except Exception:
        raise ArtifactStorageError("private export object storage is unavailable") from None
    return S3PrivateArtifactStore(
        client,
        values["KOKONUT_PRIVATE_EXPORT_S3_BUCKET"],
        read_only=access == "reader",
    )
