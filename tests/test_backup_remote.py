"""Offline S3-compatible checkpoint transport acceptance."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import backup_remote  # noqa: E402
from backup_manifest import sign_manifest, verify_manifest_signature  # noqa: E402

BACKUP_KEY = "offline-test-backup-key"


class FakeS3Error(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.delete_calls = 0

    def get_object(self, *, Bucket: str, Key: str):
        try:
            value = self.objects[(Bucket, Key)]
        except KeyError as error:
            raise FakeS3Error("NoSuchKey") from error
        return {"Body": io.BytesIO(value)}

    def upload_file(self, filename: str, bucket: str, key: str, *, ExtraArgs: dict):
        assert ExtraArgs["ContentType"] == "application/octet-stream"
        self.objects[(bucket, key)] = Path(filename).read_bytes()

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, IfNoneMatch: str, ContentType: str):
        assert IfNoneMatch == "*"
        assert ContentType == "application/json"
        object_key = (Bucket, Key)
        if object_key in self.objects:
            raise FakeS3Error("PreconditionFailed")
        self.objects[object_key] = Body

    def download_file(self, bucket: str, key: str, filename: str):
        try:
            value = self.objects[(bucket, key)]
        except KeyError as error:
            raise FakeS3Error("NoSuchKey") from error
        Path(filename).write_bytes(value)


def _checkpoint(path: Path, *, backup_id: str = "offline-checkpoint", content: bytes = b"encrypted archive") -> Path:
    artifact = path / "postgres" / "testdb.dump.enc"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(content)
    manifest = {
        "backup_id": backup_id,
        "providers": {
            "postgres": {"included": True, "databases": ["testdb"]},
            "clickhouse": {"included": False, "database": None},
        },
        "files": [
            {
                "path": "postgres/testdb.dump.enc",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        ],
    }
    signed = sign_manifest(manifest, BACKUP_KEY)
    (path / "manifest.json").write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
    return path


def test_signed_manifest_detects_metadata_tampering_and_requires_key():
    signed = sign_manifest({"backup_id": "signed", "files": []}, BACKUP_KEY)

    assert verify_manifest_signature(signed, BACKUP_KEY, required=True)
    signed["backup_id"] = "rewritten"
    with pytest.raises(ValueError, match="authentication failed"):
        verify_manifest_signature(signed, BACKUP_KEY, required=True)


def test_remote_upload_commits_after_verifying_bytes_and_downloads_atomically(tmp_path):
    source = _checkpoint(tmp_path / "source")
    store = FakeS3()

    uploaded = backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", source, BACKUP_KEY)
    restored = backup_remote.download_checkpoint(
        store, "kokonut-backups", "kernel", "offline-checkpoint", tmp_path / "restores", BACKUP_KEY
    )

    assert uploaded == {"status": "committed", "backup_id": "offline-checkpoint", "artifact_count": 1}
    assert restored["status"] == "restored"
    restored_path = Path(restored["destination"])
    assert (restored_path / "postgres" / "testdb.dump.enc").read_bytes() == b"encrypted archive"
    assert (restored_path / "postgres" / "testdb.dump.enc").stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / "restores" / ".offline-checkpoint-").exists()
    assert store.delete_calls == 0


def test_remote_upload_is_idempotent_and_refuses_backup_id_rebinding(tmp_path):
    source = _checkpoint(tmp_path / "source")
    store = FakeS3()

    first = backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", source, BACKUP_KEY)
    second = backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", source, BACKUP_KEY)
    different = _checkpoint(tmp_path / "different", content=b"other archive")

    assert first["status"] == "committed"
    assert second["status"] == "already_committed"
    with pytest.raises(backup_remote.BackupTransferError, match="different checkpoint"):
        backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", different, BACKUP_KEY)


def test_remote_upload_rejects_unsigned_legacy_checkpoint(tmp_path):
    source = _checkpoint(tmp_path / "legacy")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("integrity")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    store = FakeS3()

    with pytest.raises(backup_remote.BackupTransferError, match="unsigned"):
        backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", source, BACKUP_KEY)
    assert store.objects == {}


def test_upload_leaves_uncommitted_stage_when_marker_write_fails(tmp_path):
    source = _checkpoint(tmp_path / "source")

    class MarkerFailure(FakeS3):
        def put_object(self, **kwargs):
            raise OSError("simulated transport interruption")

    store = MarkerFailure()
    with pytest.raises(OSError, match="interruption"):
        backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", source, BACKUP_KEY)
    assert any("/objects/" in key for _, key in store.objects)
    assert not any(key.endswith("/manifest.json") for _, key in store.objects)
    assert store.delete_calls == 0


def test_download_tampering_rejects_restore_and_removes_partial_directory(tmp_path):
    source = _checkpoint(tmp_path / "source")
    store = FakeS3()
    backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", source, BACKUP_KEY)
    object_key = next(key for _, key in store.objects if "/objects/" in key)
    store.objects[("kokonut-backups", object_key)] = b"tampered"
    destination = tmp_path / "restores"

    with pytest.raises(backup_remote.BackupTransferError, match="integrity verification"):
        backup_remote.download_checkpoint(
            store, "kokonut-backups", "kernel", "offline-checkpoint", destination, BACKUP_KEY
        )
    assert list(destination.iterdir()) == []


def test_download_refuses_to_overwrite_existing_checkpoint(tmp_path):
    source = _checkpoint(tmp_path / "source")
    store = FakeS3()
    backup_remote.upload_checkpoint(store, "kokonut-backups", "kernel", source, BACKUP_KEY)
    destination = tmp_path / "restores"
    existing = destination / "offline-checkpoint"
    existing.mkdir(parents=True)
    sentinel = existing / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")

    with pytest.raises(backup_remote.BackupTransferError, match="refusing to overwrite"):
        backup_remote.download_checkpoint(
            store, "kokonut-backups", "kernel", "offline-checkpoint", destination, BACKUP_KEY
        )
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_remote_checkpoint_id_and_paths_are_validated(tmp_path):
    source = _checkpoint(tmp_path / "source", backup_id="../escape")

    with pytest.raises(backup_remote.BackupTransferError, match="invalid backup ID"):
        backup_remote._checkpoint_manifest(source, BACKUP_KEY)

    with pytest.raises(backup_remote.BackupTransferError, match="unsafe artifact path"):
        backup_remote._safe_relative_path("../outside")


def test_cli_requires_apply_for_remote_mutation_and_prints_dry_run(tmp_path):
    source = _checkpoint(tmp_path / "source")
    env = {
        **__import__("os").environ,
        "BACKUP_ENCRYPTION_KEY": BACKUP_KEY,
        "KOKONUT_BACKUP_S3_ENDPOINT_URL": "https://example.invalid",
        "KOKONUT_BACKUP_S3_BUCKET": "kokonut-backups",
    }
    import subprocess

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "backup_remote.py"), "upload", str(source)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == "dry_run"
    assert output["remote_deletes_supported"] is False
