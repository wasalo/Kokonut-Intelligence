"""Contracts for the optional ML multi-architecture release gate."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RELEASE_GATE = run_path(str(ROOT / "scripts/check-kernel-release-inputs.py"))
LockError = RELEASE_GATE["LockError"]
BASE_TOOLING = RELEASE_GATE["ML_BASE_TOOLING"]
read_ml_lock_versions = RELEASE_GATE["_ml_lock_versions"]
verify_ml_inventories = RELEASE_GATE["_verify_ml_package_inventories"]


def _complete_inventory(pins: dict[str, str]) -> dict[str, str]:
    return {**pins, **BASE_TOOLING}


def test_multiplatform_build_includes_optional_ml_target_and_verification() -> None:
    script = (ROOT / "scripts/build-kernel-multiarch.sh").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile.kernel").read_text(encoding="utf-8")

    assert "--target ml-anomaly" in script
    assert "kernel-ml-anomaly.oci.tar" in script
    assert "--ml-anomaly-oci" in script
    remove_base_packaging = dockerfile.index("RUN rm -rf /usr/local/lib/python3.11/site-packages/packaging")
    copy_locked_runtime = dockerfile.index(
        "COPY --from=ml-anomaly-dependencies /opt/ml-anomaly-site/",
        remove_base_packaging,
    )
    assert remove_base_packaging < copy_locked_runtime


def test_ml_release_gate_requires_each_locked_package_on_both_architectures() -> None:
    pins = read_ml_lock_versions()
    assert len(pins) == 24

    inventory = _complete_inventory(pins)
    verify_ml_inventories({"amd64": inventory, "arm64": dict(inventory)}, pins)


def test_ml_release_gate_rejects_missing_or_changed_locked_packages() -> None:
    pins = read_ml_lock_versions()
    inventory = _complete_inventory(pins)
    inventory.pop("numpy")

    with pytest.raises(LockError, match="numpy: installed=<missing>"):
        verify_ml_inventories({"amd64": inventory, "arm64": dict(pins)}, pins)

    inventory = _complete_inventory(pins)
    inventory["numpy"] = "0.0.0"
    with pytest.raises(LockError, match="numpy: installed=0.0.0"):
        verify_ml_inventories({"amd64": inventory, "arm64": dict(pins)}, pins)


def test_ml_release_gate_rejects_architecture_differences_and_unrelated_groups() -> None:
    pins = read_ml_lock_versions()
    arm64 = _complete_inventory(pins)
    arm64["arm-only-extra"] = "1.0"
    with pytest.raises(LockError, match="undeclared package.*arm-only-extra"):
        verify_ml_inventories({"amd64": _complete_inventory(pins), "arm64": arm64}, pins)

    amd64 = _complete_inventory(pins)
    amd64["yfinance"] = "1.0"
    with pytest.raises(LockError, match="undeclared package.*yfinance"):
        verify_ml_inventories({"amd64": amd64, "arm64": _complete_inventory(pins)}, pins)


def test_ml_release_gate_pins_base_tooling_and_rejects_wrong_versions() -> None:
    pins = read_ml_lock_versions()
    inventory = _complete_inventory(pins)
    inventory["pip"] = "99.0"

    with pytest.raises(LockError, match="pip: installed=99.0, locked=24.0"):
        verify_ml_inventories({"amd64": inventory, "arm64": _complete_inventory(pins)}, pins)
