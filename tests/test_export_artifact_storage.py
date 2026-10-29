"""Private local artifact storage behavior for the future export worker."""

import stat
from uuid import uuid4

import pytest

from services.export import artifact_storage
from services.export.artifact_storage import (
    ArtifactStorageError,
    LocalPrivateArtifactStore,
)


def test_local_store_round_trips_private_artifact_without_exposing_path(tmp_path):
    directory = tmp_path / "private-exports"
    store = LocalPrivateArtifactStore(directory)
    artifact_id = uuid4()
    payload = b'{"report":"private"}'

    store.write(artifact_id, payload)

    assert store.read(str(artifact_id)) == payload
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / f"{artifact_id}.artifact").stat().st_mode) == 0o600
    assert str(directory) not in repr(store)


@pytest.mark.parametrize(
    "artifact_id",
    [
        "",
        "../outside",
        "nested/00000000-0000-0000-0000-000000000000",
        "00000000000000000000000000000000",
        "not-a-uuid",
        b"00000000-0000-0000-0000-000000000000",
        7,
    ],
)
def test_store_rejects_noncanonical_or_path_like_artifact_ids(tmp_path, artifact_id):
    store = LocalPrivateArtifactStore(tmp_path / "private-exports")

    with pytest.raises(ValueError, match="artifact identifier must be"):
        store.write(artifact_id, b"data")
    with pytest.raises(ValueError, match="artifact identifier must be"):
        store.read(artifact_id)
    with pytest.raises(ValueError, match="artifact identifier must be"):
        store.delete(artifact_id)

    assert list((tmp_path / "private-exports").iterdir()) == []


def test_store_refuses_symlink_root_and_symlink_artifacts(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    external_file = outside / "private-data"
    external_file.write_bytes(b"keep")

    root_link = tmp_path / "root-link"
    root_link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ArtifactStorageError, match="artifact storage directory is unsafe"):
        LocalPrivateArtifactStore(root_link)

    directory = tmp_path / "private-exports"
    store = LocalPrivateArtifactStore(directory)
    artifact_id = uuid4()
    artifact_path = directory / f"{artifact_id}.artifact"
    artifact_path.symlink_to(external_file)

    with pytest.raises(ArtifactStorageError, match="private artifact is unsafe"):
        store.write(artifact_id, b"replacement")
    with pytest.raises(ArtifactStorageError):
        store.read(artifact_id)
    with pytest.raises(ArtifactStorageError, match="private artifact is unsafe"):
        store.delete(artifact_id)

    assert external_file.read_bytes() == b"keep"
    assert artifact_path.is_symlink()


def test_store_refuses_symlinked_ancestor_without_creating_outside_directory(tmp_path):
    actual_parent = tmp_path / "actual-parent"
    actual_parent.mkdir()
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(actual_parent, target_is_directory=True)

    with pytest.raises(ArtifactStorageError, match="artifact storage directory is unsafe"):
        LocalPrivateArtifactStore(parent_link / "private-exports")

    assert not (actual_parent / "private-exports").exists()


def test_repeated_writes_are_idempotent_and_replacements_are_atomic(tmp_path):
    directory = tmp_path / "private-exports"
    store = LocalPrivateArtifactStore(directory)
    artifact_id = uuid4()

    store.write(artifact_id, b"first")
    store.write(artifact_id, b"first")
    assert store.read(artifact_id) == b"first"

    store.write(artifact_id, b"replacement")
    assert store.read(artifact_id) == b"replacement"
    assert [entry.name for entry in directory.iterdir()] == [f"{artifact_id}.artifact"]


def test_failed_atomic_replace_preserves_prior_artifact_and_cleans_temporary_file(
    tmp_path, monkeypatch
):
    directory = tmp_path / "private-exports"
    store = LocalPrivateArtifactStore(directory)
    artifact_id = uuid4()
    store.write(artifact_id, b"prior")

    def fail_replace(*_args, **_kwargs):
        raise OSError("synthetic failure")

    monkeypatch.setattr(artifact_storage.os, "replace", fail_replace)
    with pytest.raises(ArtifactStorageError, match="private artifact write failed") as error:
        store.write(artifact_id, b"next")

    assert str(directory) not in str(error.value)
    assert store.read(artifact_id) == b"prior"
    assert [entry.name for entry in directory.iterdir()] == [f"{artifact_id}.artifact"]


def test_delete_is_explicit_idempotent_and_does_not_remove_other_artifacts(tmp_path):
    directory = tmp_path / "private-exports"
    store = LocalPrivateArtifactStore(directory)
    first_id, second_id = uuid4(), uuid4()
    store.write(first_id, b"delete me")
    store.write(second_id, b"keep me")

    store.delete(first_id)
    store.delete(first_id)

    with pytest.raises(ArtifactStorageError):
        store.read(first_id)
    assert store.read(second_id) == b"keep me"

    # Constructing a new adapter does not run a retention or cleanup policy.
    LocalPrivateArtifactStore(directory)
    assert store.read(second_id) == b"keep me"


def test_directory_creation_rejects_an_existing_file(tmp_path):
    non_directory = tmp_path / "file"
    non_directory.write_text("not a directory")

    with pytest.raises(ArtifactStorageError, match="artifact storage directory is unsafe"):
        LocalPrivateArtifactStore(non_directory)


def test_store_rejects_filesystem_root_as_artifact_directory():
    with pytest.raises(ValueError, match="dedicated directory"):
        LocalPrivateArtifactStore("/")
