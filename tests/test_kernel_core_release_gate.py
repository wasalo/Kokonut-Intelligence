"""Hash-lock and package-inventory contracts for the additive core image."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_kernel_release_inputs", ROOT / "scripts" / "check-kernel-release-inputs.py"
)
assert SPEC is not None and SPEC.loader is not None
release_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_gate)


def _pins(filename: str) -> dict[str, str]:
    return release_gate._lock_versions(ROOT / "requirements" / filename)


def test_core_locks_are_hash_locked_and_optional_closures_are_additive() -> None:
    core = _pins("kernel-core.lock")
    web3 = _pins("kernel-core-web3.lock")
    exports = _pins("kernel-core-exports.lock")
    storage = _pins("kernel-core-storage.lock")

    assert core
    for overlay in (web3, exports, storage):
        assert all(core[name] == overlay[name] for name in core.keys() & overlay.keys())
    assert "web3" in web3
    assert "boto3" in exports and "openpyxl" in exports
    assert set(storage) == {"pycryptodome"}
    for lock_name in (
        "kernel-core.lock",
        "kernel-core-web3.lock",
        "kernel-core-exports.lock",
        "kernel-core-storage.lock",
    ):
        text = (ROOT / "requirements" / lock_name).read_text()
        package_blocks = re.split(r"(?m)(?=^[A-Za-z0-9_.-]+==)", text)
        for block in package_blocks:
            if re.match(r"^[A-Za-z0-9_.-]+==", block):
                assert "--hash=sha256:" in block, f"missing hashes in {lock_name}"


def test_core_oci_inventory_must_match_locked_base_and_exclude_optional_groups() -> None:
    expected = {
        **_pins("kernel-core.lock"),
        **release_gate.CORE_BASE_TOOLING,
    }
    inventories = {"amd64": dict(expected), "arm64": dict(expected)}

    release_gate._verify_core_package_inventories(inventories, _pins("kernel-core.lock"))

    inventories["amd64"]["boto3"] = "1.42.0"
    with pytest.raises(release_gate.LockError, match="unexpected installed package"):
        release_gate._verify_core_package_inventories(inventories, _pins("kernel-core.lock"))


def test_multiarch_capability_inventory_matches_union_of_all_four_locks() -> None:
    capabilities = release_gate._core_capability_lock_versions()
    assert capabilities == _pins("kernel-runtime.lock")
    expected = {**capabilities, **release_gate.CORE_BASE_TOOLING}
    inventories = {"amd64": dict(expected), "arm64": dict(expected)}

    release_gate._verify_core_package_inventories(inventories, capabilities)

    del inventories["arm64"]["openpyxl"]
    with pytest.raises(release_gate.LockError, match="openpyxl: installed=<missing>"):
        release_gate._verify_core_package_inventories(inventories, capabilities)


def test_multiarch_script_builds_all_core_capabilities_together() -> None:
    script = (ROOT / "scripts/build-kernel-multiarch.sh").read_text()

    assert "--core-capabilities-oci" in script
    assert "--target kernel-core" in script
    for argument in (
        "KOKONUT_CORE_WEB3=true",
        "KOKONUT_CORE_EXPORTS=true",
        "KOKONUT_CORE_LOCAL_MEDIA=true",
    ):
        assert f"--build-arg {argument}" in script


def test_core_oci_gate_rejects_missing_architecture_inventory() -> None:
    with pytest.raises(release_gate.LockError, match="exactly linux/amd64 and linux/arm64"):
        release_gate._verify_core_package_inventories(
            {"amd64": _pins("kernel-core.lock")}, _pins("kernel-core.lock")
        )


def test_core_source_manifest_includes_only_core_lock_inputs(tmp_path: Path) -> None:
    (tmp_path / "requirements").mkdir()
    (tmp_path / "services/core").mkdir(parents=True)
    shutil.copy2(ROOT / "services/core/image_manifest.py", tmp_path / "services/core/image_manifest.py")
    for filename in (
        "kernel-core.in",
        "kernel-core.lock",
        "kernel-core-web3.in",
        "kernel-core-web3.lock",
        "kernel-core-exports.in",
        "kernel-core-exports.lock",
        "kernel-core-storage.in",
        "kernel-core-storage.lock",
    ):
        shutil.copy2(ROOT / "requirements" / filename, tmp_path / "requirements" / filename)

    subprocess.run(
        [
            sys.executable,
            str(tmp_path / "services/core/image_manifest.py"),
            "--root",
            str(tmp_path),
            "--target",
            "kernel-core",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = json.loads((tmp_path / "source-manifest.json").read_text())
    assert manifest["target"] == "kernel-core"
    assert "requirements/kernel-core.lock" in manifest["files"]
    assert "requirements/kernel-core-web3.lock" in manifest["files"]


def test_existing_kernel_image_manifest_does_not_expand_to_core_lock_inputs(tmp_path: Path) -> None:
    (tmp_path / "requirements").mkdir()
    (tmp_path / "services/core").mkdir(parents=True)
    shutil.copy2(ROOT / "services/core/image_manifest.py", tmp_path / "services/core/image_manifest.py")
    shutil.copy2(ROOT / "requirements/kernel-core.lock", tmp_path / "requirements/kernel-core.lock")

    subprocess.run(
        [
            sys.executable,
            str(tmp_path / "services/core/image_manifest.py"),
            "--root",
            str(tmp_path),
            "--target",
            "kernel",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = json.loads((tmp_path / "source-manifest.json").read_text())
    assert manifest["target"] == "kernel"
    assert "requirements/kernel-core.lock" not in manifest["files"]
