"""Offline contract tests for the optional ML wheel lock generator."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.generate_ml_anomaly_runtime_lock import (
    build_lock,
    read_resolved,
    wheel_hashes,
)


def _wheel(directory: Path, filename: str, name: str, version: str) -> str:
    path = directory / filename
    metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{name}-{version}.dist-info/METADATA", metadata)
        archive.writestr(f"{name}-{version}.dist-info/WHEEL", filename)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lock_uses_the_union_of_both_architecture_wheel_hashes(tmp_path: Path) -> None:
    resolved = tmp_path / "resolved.txt"
    resolved.write_text(
        "# generated\n"
        "demo-pkg==1.2.3\n"
        "other_pkg==4.5.6 ; python_version >= \"3.11\"\n",
        encoding="utf-8",
    )
    amd64 = tmp_path / "amd64"
    arm64 = tmp_path / "arm64"
    amd64.mkdir()
    arm64.mkdir()
    amd64_hash = _wheel(amd64, "demo_pkg-1.2.3-cp311-cp311-manylinux_x86_64.whl", "demo-pkg", "1.2.3")
    arm64_hash = _wheel(arm64, "demo_pkg-1.2.3-cp311-cp311-manylinux_aarch64.whl", "demo-pkg", "1.2.3")
    _wheel(amd64, "other_pkg-4.5.6-py3-none-any.whl", "other_pkg", "4.5.6")
    _wheel(arm64, "other_pkg-4.5.6-py3-none-any.whl", "other_pkg", "4.5.6")

    requirements = read_resolved(resolved)
    lines = build_lock(requirements, wheel_hashes(amd64), wheel_hashes(arm64))
    lock = "\n".join(lines)

    demo_entry = lock.split("demo-pkg==1.2.3 \\\n", 1)[1].split("\nother_pkg==", 1)[0]
    assert f"--hash=sha256:{amd64_hash}" in demo_entry
    assert f"--hash=sha256:{arm64_hash}" in demo_entry
    assert amd64_hash != arm64_hash
    assert "other_pkg==4.5.6 ; python_version >= \"3.11\"" in lock
    assert lock.count("other_pkg==4.5.6") == 1


def test_lock_rejects_packages_without_a_wheel_for_each_architecture(tmp_path: Path) -> None:
    resolved = tmp_path / "resolved.txt"
    resolved.write_text("demo==1.2.3\n", encoding="utf-8")
    amd64 = tmp_path / "amd64"
    arm64 = tmp_path / "arm64"
    amd64.mkdir()
    arm64.mkdir()
    _wheel(amd64, "demo-1.2.3-cp311-cp311-manylinux_x86_64.whl", "demo", "1.2.3")

    with pytest.raises(ValueError, match="ARM64"):
        build_lock(read_resolved(resolved), wheel_hashes(amd64), {})


def test_lock_rejects_wheel_versions_that_disagree_with_the_resolved_pin(tmp_path: Path) -> None:
    amd64 = tmp_path / "amd64"
    arm64 = tmp_path / "arm64"
    amd64.mkdir()
    arm64.mkdir()
    _wheel(amd64, "demo-1.2.3-cp311-cp311-manylinux_x86_64.whl", "demo", "1.2.3")
    _wheel(arm64, "demo-1.2.4-cp311-cp311-manylinux_aarch64.whl", "demo", "1.2.4")

    with pytest.raises(ValueError, match="expected pinned 1.2.3"):
        build_lock(
            {"demo": ("demo", "1.2.3", None)},
            wheel_hashes(amd64),
            wheel_hashes(arm64),
        )
