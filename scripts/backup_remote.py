#!/usr/bin/env python3
"""Transfer signed, encrypted Kernel checkpoints to an S3-compatible store.

This command intentionally supports upload and download only. It has no remote
delete operation and requires --apply for either a remote write or local restore.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from backup_manifest import canonical_manifest_bytes, verify_manifest_signature

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
BUCKET_PATTERN = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z")
PREFIX_COMPONENT_PATTERN = re.compile(r"[A-Za-z0-9._-]+\Z")
FORMAT = "kokonut-s3-checkpoint-v1"


class BackupTransferError(RuntimeError):
    """A safe, user-facing transfer error without credential details."""


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _safe_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BackupTransferError("Checkpoint manifest contains an invalid artifact path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(part in {"", ".", ".."} for part in path.parts):
        raise BackupTransferError("Checkpoint manifest contains an unsafe artifact path")
    if value == "manifest.json":
        raise BackupTransferError("Checkpoint manifest must not list itself as an artifact")
    return path.as_posix()


def _checkpoint_manifest(
    checkpoint: Path, backup_key: str
) -> tuple[dict[str, Any], bytes, list[tuple[str, Path, str, int]]]:
    checkpoint = checkpoint.resolve(strict=True)
    if not checkpoint.is_dir():
        raise BackupTransferError("Checkpoint path must be a directory")
    verifier = subprocess.run(  # noqa: S603 - fixed verifier executable; path is a data argument
        [str(ROOT / "scripts" / "verify-backup.sh"), str(checkpoint)],
        cwd=ROOT,
        env={**os.environ, "BACKUP_ENCRYPTION_KEY": backup_key},
        capture_output=True,
        text=True,
        check=False,
    )
    if verifier.returncode:
        message = verifier.stderr.strip().splitlines()
        raise BackupTransferError(message[-1] if message else "Local checkpoint verification failed")
    try:
        manifest = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BackupTransferError("Checkpoint manifest could not be read") from error
    if not isinstance(manifest, dict):
        raise BackupTransferError("Checkpoint manifest is invalid")
    backup_id = manifest.get("backup_id")
    if not isinstance(backup_id, str) or not BACKUP_ID_PATTERN.fullmatch(backup_id):
        raise BackupTransferError("Checkpoint manifest has an invalid backup ID")
    try:
        verify_manifest_signature(manifest, backup_key, required=True)
    except ValueError as error:
        raise BackupTransferError(str(error)) from error
    records = manifest.get("files")
    if not isinstance(records, list):
        raise BackupTransferError("Checkpoint manifest has no valid artifact inventory")
    files: list[tuple[str, Path, str, int]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise BackupTransferError("Checkpoint manifest contains an invalid artifact record")
        relative = _safe_relative_path(record.get("path"))
        if relative in seen:
            raise BackupTransferError("Checkpoint manifest contains duplicate artifact paths")
        seen.add(relative)
        path = checkpoint / relative
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(checkpoint):
            raise BackupTransferError("Checkpoint artifact escapes its directory")
        digest, size = _sha256_file(path)
        if digest != record.get("sha256") or size != record.get("size"):
            raise BackupTransferError("Checkpoint artifact differs from its signed manifest")
        files.append((relative, path, digest, size))
    if not files:
        raise BackupTransferError("Checkpoint manifest has no artifacts")
    return manifest, canonical_manifest_bytes(manifest), files


def _read_body(body: BinaryIO) -> bytes:
    try:
        return body.read()
    finally:
        close = getattr(body, "close", None)
        if close:
            close()


def _optional_object(client: Any, bucket: str, key: str) -> bytes | None:
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except Exception as error:
        response_body = getattr(error, "response", {})
        code = str(response_body.get("Error", {}).get("Code", ""))
        status = response_body.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"NoSuchKey", "NotFound", "404"} or status == 404:
            return None
        raise
    return _read_body(response["Body"])


def _remote_hash(client: Any, bucket: str, key: str) -> tuple[str, int] | None:
    try:
        response = client.get_object(Bucket=bucket, Key=key)
    except Exception as error:
        response_body = getattr(error, "response", {})
        code = str(response_body.get("Error", {}).get("Code", ""))
        status = response_body.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"NoSuchKey", "NotFound", "404"} or status == 404:
            return None
        raise
    body = response["Body"]
    digest = hashlib.sha256()
    size = 0
    try:
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    finally:
        body.close()
    return digest.hexdigest(), size


def _validate_envelope(
    raw: bytes, backup_id: str, backup_key: str, stable_prefix: str
) -> tuple[dict[str, Any], str, bytes]:
    try:
        envelope = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise BackupTransferError("Remote checkpoint marker is invalid") from error
    if not isinstance(envelope, dict) or envelope.get("format") != FORMAT:
        raise BackupTransferError("Remote checkpoint marker uses an unsupported format")
    if envelope.get("backup_id") != backup_id:
        raise BackupTransferError("Remote checkpoint marker has a mismatched backup ID")
    manifest = envelope.get("manifest")
    object_prefix = envelope.get("object_prefix")
    if not isinstance(manifest, dict) or manifest.get("backup_id") != backup_id:
        raise BackupTransferError("Remote checkpoint manifest has a mismatched backup ID")
    try:
        verify_manifest_signature(manifest, backup_key, required=True)
    except ValueError as error:
        raise BackupTransferError(str(error)) from error
    canonical = canonical_manifest_bytes(manifest)
    if hashlib.sha256(canonical).hexdigest() != envelope.get("manifest_sha256"):
        raise BackupTransferError("Remote checkpoint manifest digest does not match")
    expected_parent = f"{stable_prefix}/{backup_id}/objects/"
    if (
        not isinstance(object_prefix, str)
        or not object_prefix.startswith(expected_parent)
        or not re.fullmatch(re.escape(expected_parent) + r"[0-9a-f]{32}", object_prefix)
    ):
        raise BackupTransferError("Remote checkpoint object prefix is invalid")
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise BackupTransferError("Remote checkpoint manifest has no artifacts")
    return envelope, object_prefix, canonical


def _assert_existing_transfer_matches(client: Any, bucket: str, envelope: dict[str, Any], object_prefix: str) -> None:
    for record in envelope["manifest"]["files"]:
        relative = _safe_relative_path(record.get("path") if isinstance(record, dict) else None)
        expected = record.get("sha256"), record.get("size")
        actual = _remote_hash(client, bucket, f"{object_prefix}/{relative}")
        if actual != expected:
            raise BackupTransferError("A committed remote checkpoint artifact is missing or changed")


def upload_checkpoint(
    client: Any,
    bucket: str,
    stable_prefix: str,
    checkpoint: Path,
    backup_key: str,
) -> dict[str, Any]:
    manifest, manifest_bytes, files = _checkpoint_manifest(checkpoint, backup_key)
    backup_id = manifest["backup_id"]
    marker_key = f"{stable_prefix}/{backup_id}/manifest.json"
    existing_raw = _optional_object(client, bucket, marker_key)
    expected_manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if existing_raw is not None:
        envelope, object_prefix, _ = _validate_envelope(existing_raw, backup_id, backup_key, stable_prefix)
        if envelope["manifest_sha256"] != expected_manifest_digest:
            raise BackupTransferError("Remote backup ID already commits to a different checkpoint")
        _assert_existing_transfer_matches(client, bucket, envelope, object_prefix)
        return {"status": "already_committed", "backup_id": backup_id, "artifact_count": len(files)}

    object_prefix = f"{stable_prefix}/{backup_id}/objects/{uuid.uuid4().hex}"
    for relative, path, digest, size in files:
        key = f"{object_prefix}/{relative}"
        client.upload_file(str(path), bucket, key, ExtraArgs={"ContentType": "application/octet-stream"})
        if _remote_hash(client, bucket, key) != (digest, size):
            raise BackupTransferError("Uploaded checkpoint artifact failed remote byte verification")

    envelope = {
        "format": FORMAT,
        "backup_id": backup_id,
        "manifest_sha256": expected_manifest_digest,
        "manifest": manifest,
        "object_prefix": object_prefix,
    }
    marker_bytes = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        client.put_object(
            Bucket=bucket,
            Key=marker_key,
            Body=marker_bytes,
            ContentType="application/json",
            IfNoneMatch="*",
        )
    except Exception as error:
        # A competing upload may have committed, or the response may have been
        # lost after the write. Accept only the exact same signed checkpoint.
        committed = _optional_object(client, bucket, marker_key)
        if committed is None:
            raise error
        saved, saved_prefix, _ = _validate_envelope(committed, backup_id, backup_key, stable_prefix)
        if saved["manifest_sha256"] != expected_manifest_digest:
            raise BackupTransferError("Remote backup ID was committed by another checkpoint") from error
        _assert_existing_transfer_matches(client, bucket, saved, saved_prefix)
        return {"status": "already_committed", "backup_id": backup_id, "artifact_count": len(files)}
    return {"status": "committed", "backup_id": backup_id, "artifact_count": len(files)}


def download_checkpoint(
    client: Any,
    bucket: str,
    stable_prefix: str,
    backup_id: str,
    destination: Path,
    backup_key: str,
) -> dict[str, Any]:
    if not BACKUP_ID_PATTERN.fullmatch(backup_id):
        raise BackupTransferError("Invalid backup ID")
    marker_key = f"{stable_prefix}/{backup_id}/manifest.json"
    marker_bytes = _optional_object(client, bucket, marker_key)
    if marker_bytes is None:
        raise BackupTransferError("Remote checkpoint was not found")
    envelope, object_prefix, manifest_bytes = _validate_envelope(marker_bytes, backup_id, backup_key, stable_prefix)
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.is_symlink() or not destination.is_dir():
        raise BackupTransferError("Restore destination must be a real directory")
    final_path = destination / backup_id
    if final_path.exists() or final_path.is_symlink():
        raise BackupTransferError("Restore destination already exists; refusing to overwrite it")
    temporary = Path(tempfile.mkdtemp(prefix=f".{backup_id}-", dir=destination))
    os.chmod(temporary, 0o700)
    try:
        for record in envelope["manifest"]["files"]:
            if not isinstance(record, dict):
                raise BackupTransferError("Remote checkpoint has an invalid artifact record")
            relative = _safe_relative_path(record.get("path"))
            target = temporary.joinpath(*PurePosixPath(relative).parts)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            remote_key = f"{object_prefix}/{relative}"
            client.download_file(bucket, remote_key, str(target))
            digest, size = _sha256_file(target)
            if digest != record.get("sha256") or size != record.get("size"):
                raise BackupTransferError("Downloaded checkpoint artifact failed integrity verification")
            os.chmod(target, 0o600)
        manifest_path = temporary / "manifest.json"
        manifest_path.write_bytes(manifest_bytes)
        os.chmod(manifest_path, 0o600)
        verifier = subprocess.run(  # noqa: S603 - fixed verifier executable; path is a data argument
            [str(ROOT / "scripts" / "verify-backup.sh"), str(temporary)],
            cwd=ROOT,
            env={**os.environ, "BACKUP_ENCRYPTION_KEY": backup_key},
            capture_output=True,
            text=True,
            check=False,
        )
        if verifier.returncode:
            raise BackupTransferError("Downloaded checkpoint failed local verification")
        os.replace(temporary, final_path)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"status": "restored", "backup_id": backup_id, "destination": str(final_path)}


def _configuration() -> tuple[str, str, str, str]:
    endpoint = os.environ.get("KOKONUT_BACKUP_S3_ENDPOINT_URL", "").strip()
    bucket = os.environ.get("KOKONUT_BACKUP_S3_BUCKET", "").strip()
    prefix = os.environ.get("KOKONUT_BACKUP_S3_PREFIX", "kokonut-kernel-backups").strip("/")
    region = os.environ.get("KOKONUT_BACKUP_S3_REGION", "auto").strip()
    if not endpoint.startswith("https://") or not bucket or not BUCKET_PATTERN.fullmatch(bucket):
        raise BackupTransferError("Set an HTTPS backup endpoint and valid backup bucket in the environment")
    if not prefix or any(
        not PREFIX_COMPONENT_PATTERN.fullmatch(part) or part in {".", ".."} for part in prefix.split("/")
    ):
        raise BackupTransferError("Invalid backup object prefix")
    if not region:
        raise BackupTransferError("Backup object region must not be empty")
    return endpoint, bucket, prefix, region


def _s3_client(endpoint: str, region: str) -> Any:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:
        raise BackupTransferError("Install the project's boto3 dependency before applying remote transfers") from error
    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        raise BackupTransferError("S3-compatible access credentials are required for --apply")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    upload = subparsers.add_parser("upload", help="upload one verified checkpoint")
    upload.add_argument("checkpoint", type=Path)
    upload.add_argument("--apply", action="store_true", help="write artifacts and commit the remote marker")
    download = subparsers.add_parser("download", help="restore one committed checkpoint to a new local directory")
    download.add_argument("backup_id")
    download.add_argument("--destination", type=Path, required=True)
    download.add_argument("--apply", action="store_true", help="write the verified checkpoint locally")
    args = parser.parse_args()

    sdk_errors: tuple[type[BaseException], ...] = ()
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        pass
    else:
        sdk_errors = (BotoCoreError, ClientError)

    try:
        backup_key = os.environ.get("BACKUP_ENCRYPTION_KEY", "")
        endpoint, bucket, prefix, region = _configuration()
        if args.operation == "upload":
            manifest, _, files = _checkpoint_manifest(args.checkpoint, backup_key)
            if not args.apply:
                result = {
                    "status": "dry_run",
                    "operation": "upload",
                    "backup_id": manifest["backup_id"],
                    "artifact_count": len(files),
                    "bucket": bucket,
                    "remote_deletes_supported": False,
                }
            else:
                client = _s3_client(endpoint, region)
                result = upload_checkpoint(client, bucket, prefix, args.checkpoint, backup_key)
                result["bucket"] = bucket
        else:
            if not BACKUP_ID_PATTERN.fullmatch(args.backup_id):
                raise BackupTransferError("Invalid backup ID")
            if not args.apply:
                result = {
                    "status": "dry_run",
                    "operation": "download",
                    "backup_id": args.backup_id,
                    "destination": str(args.destination / args.backup_id),
                    "remote_deletes_supported": False,
                }
            else:
                if not backup_key:
                    raise BackupTransferError("BACKUP_ENCRYPTION_KEY is required for restore")
                client = _s3_client(endpoint, region)
                result = download_checkpoint(client, bucket, prefix, args.backup_id, args.destination, backup_key)
                result["bucket"] = bucket
        print(json.dumps(result, sort_keys=True))
        return 0
    except (BackupTransferError, OSError, ValueError) as error:
        print(f"backup-remote: {error}", file=sys.stderr)
        return 1
    except sdk_errors as error:
        response = getattr(error, "response", {})
        service_code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
        safe_detail = service_code if isinstance(service_code, str) else type(error).__name__
        print(f"backup-remote: object-storage operation failed ({safe_detail})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
