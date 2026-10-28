#!/usr/bin/env python3
"""Validate locked Kernel image inputs and local multi-platform OCI build outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "config/kernel/release-input-lock.json"
ML_BASE_TOOLING = {"pip": "24.0", "setuptools": "79.0.1", "wheel": "0.46.3"}
CORE_BASE_TOOLING = {**ML_BASE_TOOLING, "packaging": "26.2"}
CORE_CAPABILITY_LOCKS = (
    "kernel-core-web3.lock",
    "kernel-core-exports.lock",
    "kernel-core-storage.lock",
)


class LockError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LockError(f"cannot read JSON input {path.relative_to(ROOT)}: {error}") from error
    if not isinstance(value, dict):
        raise LockError(f"expected a JSON object in {path.relative_to(ROOT)}")
    return value


def _validate_inputs(lock: dict) -> None:
    inputs = lock.get("sha256_inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise LockError("release lock has no sha256_inputs")
    for relative_path, expected_hash in inputs.items():
        path = ROOT / relative_path
        try:
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise LockError(f"cannot read locked input {relative_path}: {error}") from error
        if actual_hash != expected_hash:
            raise LockError(
                f"locked input changed: {relative_path}\n"
                f"  expected sha256:{expected_hash}\n"
                f"  actual   sha256:{actual_hash}\n"
                "Review the change and update config/kernel/release-input-lock.json."
            )

    base_images = lock.get("base_images", {})
    for dockerfile, expected_base in (
        ("Dockerfile.kernel", base_images.get("application")),
        ("Dockerfile.kernel-postgis", base_images.get("database")),
    ):
        if not expected_base or "@sha256:" not in expected_base:
            raise LockError(f"release lock must provide a digest-pinned base for {dockerfile}")
        first_external_from = None
        for line in (ROOT / dockerfile).read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*FROM\s+(\S+)", line, re.IGNORECASE)
            if match and "${" not in match.group(1) and not match.group(1).startswith("--"):
                first_external_from = match.group(1)
                break
        if first_external_from != expected_base:
            raise LockError(
                f"base image mismatch in {dockerfile}: expected {expected_base}, "
                f"found {first_external_from!r}"
            )

    package_record = _load_json(ROOT / "config/postgres/kernel-postgis-packages.json")
    if package_record.get("base_image") != base_images.get("database"):
        raise LockError("PostGIS package record base_image differs from the release lock")
    apt_sources = package_record.get("apt_sources")
    if not isinstance(apt_sources, dict):
        raise LockError("PostGIS package record has no apt_sources lock")
    snapshot_timestamp = apt_sources.get("debian_snapshot_timestamp", "")
    if not re.fullmatch(r"\d{8}T\d{6}Z", snapshot_timestamp):
        raise LockError("PostGIS Debian snapshot timestamp must be an exact UTC timestamp")
    sources_path = apt_sources.get("source_file")
    preferences_path = apt_sources.get("preferences_file")
    bootstrap_sources_path = apt_sources.get("bootstrap_source_file")
    try:
        sources = (ROOT / sources_path).read_text(encoding="utf-8")
        preferences = (ROOT / preferences_path).read_text(encoding="utf-8")
        bootstrap_sources = (ROOT / bootstrap_sources_path).read_text(encoding="utf-8")
    except (TypeError, OSError) as error:
        raise LockError(f"cannot read locked PostGIS apt source inputs: {error}") from error
    expected_source_entries = (
        f"https://snapshot.debian.org/archive/debian/{snapshot_timestamp}/",
        f"https://snapshot.debian.org/archive/debian-security/{snapshot_timestamp}/",
        "Suites: bookworm bookworm-updates",
        "Suites: bookworm-security",
        apt_sources.get("pgdg_archive_uri"),
        apt_sources.get("pgdg_archive_suite"),
    )
    if any(not entry or entry not in sources for entry in expected_source_entries):
        raise LockError("PostGIS apt source file differs from the package-record snapshot lock")
    expected_bootstrap_entries = (
        f"http://snapshot.debian.org/archive/debian/{snapshot_timestamp}/",
        "Suites: bookworm",
        "Components: main",
        "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg",
        "Check-Valid-Until: no",
    )
    if any(entry not in bootstrap_sources for entry in expected_bootstrap_entries):
        raise LockError("PostGIS CA bootstrap source differs from the Debian snapshot lock")
    if "https://" in bootstrap_sources or "apt-archive.postgresql.org" in bootstrap_sources:
        raise LockError("PostGIS CA bootstrap source must use only the signed Debian HTTP snapshot")
    postgis_dockerfile = (ROOT / "Dockerfile.kernel-postgis").read_text(encoding="utf-8")
    bootstrap_stage = postgis_dockerfile.find("FROM postgres-base AS ca-bootstrap")
    ca_install = postgis_dockerfile.find("apt-get install -y --no-install-recommends ca-certificates")
    https_stage = postgis_dockerfile.find("FROM ca-bootstrap AS apt-snapshot-base")
    https_sources_copy = postgis_dockerfile.find("COPY config/postgres/kernel-apt.sources", https_stage)
    if min(bootstrap_stage, ca_install, https_stage, https_sources_copy) < 0 or not (
        bootstrap_stage < ca_install < https_stage < https_sources_copy
    ):
        raise LockError("PostGIS CA certificates must be bootstrapped before HTTPS apt sources are enabled")
    if package_record.get("repository_suite") != apt_sources.get("pgdg_archive_suite"):
        raise LockError("PostGIS repository_suite differs from its apt source lock")
    if "Pin-Priority: 100" not in preferences:
        raise LockError("PostGIS PGDG archive packages must have low default apt priority")
    if set(package_record.get("verified_package_catalog_architectures", [])) != {"amd64", "arm64"}:
        raise LockError("PostGIS package catalog must be verified for amd64 and arm64")
    package_differences = package_record.get("architecture_specific_package_differences")
    if not isinstance(package_differences, dict):
        raise LockError("PostGIS package record has no architecture-specific inventory contract")
    for name, expectation in package_differences.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", name):
            raise LockError(f"invalid architecture-specific Debian package name: {name!r}")
        if not isinstance(expectation, dict) or set(expectation) != {"amd64", "arm64", "rationale"}:
            raise LockError(f"invalid architecture-specific inventory expectation for {name}")
        versions = (expectation["amd64"], expectation["arm64"])
        if any(
            version is not None and (not isinstance(version, str) or not version)
            for version in versions
        ):
            raise LockError(f"invalid architecture-specific package version for {name}")
        if versions[0] == versions[1]:
            raise LockError(f"architecture-specific inventory expectation for {name} must describe a difference")
        if not isinstance(expectation["rationale"], str) or not expectation["rationale"].strip():
            raise LockError(f"architecture-specific inventory expectation for {name} must describe a justified difference")
    package_args = package_record.get("build_arguments", {})
    for name in ("POSTGIS_PACKAGE_VERSION", "POSTGIS_SCRIPTS_VERSION"):
        if package_args.get(name) != lock.get("postgis_packages", {}).get(name):
            raise LockError(f"PostGIS package argument {name} differs from the release lock")


def _read_oci_json(archive: tarfile.TarFile, member_name: str) -> dict:
    candidates = (member_name, f"./{member_name}")
    for candidate in candidates:
        try:
            entry = archive.extractfile(archive.getmember(candidate))
        except KeyError:
            continue
        if entry is None:
            break
        return json.loads(entry.read().decode("utf-8"))
    raise LockError(f"OCI archive is missing {member_name}")


def _read_oci_member(archive: tarfile.TarFile, member_name: str) -> bytes:
    for candidate in (member_name, f"./{member_name}"):
        try:
            entry = archive.extractfile(archive.getmember(candidate))
        except KeyError:
            continue
        if entry is not None:
            return entry.read()
    raise LockError(f"OCI archive is missing {member_name}")


def _blob(archive: tarfile.TarFile, digest: str):
    algorithm, separator, value = digest.partition(":")
    if not separator or algorithm != "sha256" or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise LockError(f"unsupported OCI blob digest: {digest}")
    try:
        entry = archive.extractfile(archive.getmember(f"blobs/{algorithm}/{value}"))
    except KeyError as error:
        raise LockError(f"OCI archive is missing blob {digest}") from error
    if entry is None:
        raise LockError(f"OCI archive blob is unreadable: {digest}")
    return entry


def _platform_manifests(archive: tarfile.TarFile) -> tuple[dict[str, dict], str]:
    index_bytes = _read_oci_json(archive, "index.json")
    index_digest = hashlib.sha256(_read_oci_member(archive, "index.json")).hexdigest()
    manifests: dict[str, dict] = {}
    visited: set[str] = set()

    def visit(descriptor: dict) -> None:
        descriptor_digest = descriptor.get("digest")
        if not descriptor_digest or descriptor_digest in visited:
            return
        visited.add(descriptor_digest)
        platform = descriptor.get("platform") or {}
        architecture = platform.get("architecture")
        content = json.loads(_blob(archive, descriptor_digest).read().decode("utf-8"))

        if platform.get("os") == "linux" and architecture in {"amd64", "arm64"}:
            manifests[architecture] = content
            return

        # Some exporters wrap the platform index in an unlabelled descriptor.
        # Walk nested indexes before treating a descriptor as an image manifest.
        child_descriptors = content.get("manifests")
        if isinstance(child_descriptors, list):
            for child in child_descriptors:
                if isinstance(child, dict) and child.get("digest"):
                    visit(child)
            return

        # OCI exporters may omit platform metadata from image descriptors. The
        # image config remains authoritative; attestations have no config and
        # are skipped by this fallback.
        config_descriptor = content.get("config") or {}
        config_digest = config_descriptor.get("digest")
        if config_digest:
            config = json.loads(_blob(archive, config_digest).read().decode("utf-8"))
            config_platform = {"os": config.get("os"), "architecture": config.get("architecture")}
            architecture = config_platform["architecture"]
            if config_platform.get("os") == "linux" and architecture in {"amd64", "arm64"}:
                manifests[architecture] = content

    for descriptor in index_bytes.get("manifests", []):
        if isinstance(descriptor, dict) and descriptor.get("digest"):
            visit(descriptor)
    missing = {"amd64", "arm64"} - manifests.keys()
    if missing:
        raise LockError(f"OCI output is missing linux platform(s): {', '.join(sorted(missing))}")
    return manifests, index_digest


def _image_file(archive: tarfile.TarFile, manifest: dict, image_path: str) -> bytes:
    wanted = PurePosixPath(image_path).as_posix().lstrip("./")
    for layer_descriptor in reversed(manifest.get("layers", [])):
        layer_stream = _blob(archive, layer_descriptor["digest"])
        with tarfile.open(fileobj=layer_stream, mode="r|*") as layer:
            for member in layer:
                if PurePosixPath(member.name).as_posix().lstrip("./") != wanted:
                    continue
                content = layer.extractfile(member)
                if content is None:
                    break
                return content.read()
    raise LockError(f"multi-platform image does not contain {image_path}")


def _normalized_python_inventory(packages: list[dict]) -> dict[str, str]:
    inventory = {}
    for item in packages:
        name = item.get("name")
        version = item.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise LockError("Python package inventory entries must have string name and version fields")
        normalized_name = re.sub(r"[-_.]+", "-", name).lower()
        previous = inventory.get(normalized_name)
        if previous is not None and previous != version:
            raise LockError(
                f"Python package inventory has conflicting versions for {normalized_name}: "
                f"{previous} and {version}"
            )
        inventory[normalized_name] = version
    if not inventory:
        raise LockError("Python package inventory is empty")
    return inventory


def _lock_versions(lock_path: Path) -> dict[str, str]:
    pins = {}
    for number, raw_line in enumerate(lock_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("--hash="):
            continue
        line = line.rstrip("\\").strip().split(";", 1)[0].strip()
        if "==" not in line:
            raise LockError(f"invalid runtime lock entry at {lock_path}:{number}")
        name, version = line.split("==", 1)
        normalized_name = re.sub(r"[-_.]+", "-", name).lower()
        if not normalized_name or not version or normalized_name in pins:
            raise LockError(f"duplicate or invalid runtime lock pin at {lock_path}:{number}")
        pins[normalized_name] = version
    if not pins:
        raise LockError(f"runtime lock has no package pins: {lock_path}")
    return pins


def _ml_lock_versions(lock_path: Path = ROOT / "requirements/ml-anomaly-runtime.lock") -> dict[str, str]:
    return _lock_versions(lock_path)


def _core_capability_lock_versions() -> dict[str, str]:
    """Merge the core and all optional capability pins, rejecting drift."""
    merged = _lock_versions(ROOT / "requirements/kernel-core.lock")
    for filename in CORE_CAPABILITY_LOCKS:
        for name, version in _lock_versions(ROOT / "requirements" / filename).items():
            previous = merged.get(name)
            if previous is not None and previous != version:
                raise LockError(
                    f"conflicting core capability lock pin for {name}: {previous} and {version}"
                )
            merged[name] = version
    return merged


def _verify_core_package_inventories(
    inventories: dict[str, dict[str, str]], lock_pins: dict[str, str]
) -> None:
    expected_architectures = {"amd64", "arm64"}
    if set(inventories) != expected_architectures:
        raise LockError("core image inventory must include exactly linux/amd64 and linux/arm64")
    expected = {**lock_pins, **CORE_BASE_TOOLING}
    for architecture, inventory in inventories.items():
        differences = [
            f"{name}: installed={inventory.get(name, '<missing>')}, locked={version}"
            for name, version in expected.items()
            if inventory.get(name) != version
        ]
        undeclared = inventory.keys() - expected.keys()
        if undeclared:
            differences.extend(f"{name}: unexpected installed package" for name in sorted(undeclared))
        if differences:
            raise LockError(
                f"{architecture} core image package inventory differs from the locked core/base contract:\n  "
                + "\n  ".join(differences[:30])
            )


def _verify_ml_package_inventories(
    inventories: dict[str, dict[str, str]], lock_pins: dict[str, str]
) -> None:
    expected_architectures = {"amd64", "arm64"}
    actual_architectures = set(inventories)
    if actual_architectures != expected_architectures:
        missing = expected_architectures - actual_architectures
        unexpected = actual_architectures - expected_architectures
        details = []
        if missing:
            details.append(f"missing: {', '.join(sorted(missing))}")
        if unexpected:
            details.append(f"unexpected: {', '.join(sorted(unexpected))}")
        raise LockError("ML image architecture inventory is invalid (" + "; ".join(details) + ")")
    expected = {**lock_pins, **ML_BASE_TOOLING}
    for architecture, inventory in inventories.items():
        mismatches = [
            f"{name}: installed={inventory.get(name, '<missing>')}, locked={version}"
            for name, version in expected.items()
            if inventory.get(name) != version
        ]
        if mismatches:
            raise LockError(
                f"{architecture} ML image package versions differ from the runtime lock/base tooling contract:\n  "
                + "\n  ".join(mismatches[:30])
            )
        undeclared = inventory.keys() - expected.keys()
        if undeclared:
            raise LockError(
                f"{architecture} optional ML image includes undeclared package(s): "
                + ", ".join(sorted(undeclared))
            )
    if inventories["amd64"] != inventories["arm64"]:
        left, right = inventories["amd64"], inventories["arm64"]
        differences = [
            f"{name}: amd64={left.get(name, '<missing>')}, arm64={right.get(name, '<missing>')}"
            for name in sorted(left.keys() | right.keys())
            if left.get(name) != right.get(name)
        ]
        raise LockError("ML Python package version parity failed:\n  " + "\n  ".join(differences[:30]))


def _verify_application(archive_path: Path) -> None:
    with tarfile.open(archive_path, mode="r:*") as archive:
        manifests, index_digest = _platform_manifests(archive)
        inventories = {}
        for architecture, manifest in manifests.items():
            packages = json.loads(_image_file(archive, manifest, "app/python-packages.json"))
            inventories[architecture] = _normalized_python_inventory(packages)
        if inventories["amd64"] != inventories["arm64"]:
            left, right = inventories["amd64"], inventories["arm64"]
            differences = [
                f"{name}: amd64={left.get(name, '<missing>')}, arm64={right.get(name, '<missing>')}"
                for name in sorted(left.keys() | right.keys())
                if left.get(name) != right.get(name)
            ]
            raise LockError("Python package version parity failed:\n  " + "\n  ".join(differences[:20]))
        print(
            "Kernel app OCI build verified: linux/amd64 + linux/arm64, "
            f"{len(inventories['amd64'])} matching Python packages, index sha256:{index_digest}"
        )


def _verify_core_application(archive_path: Path, *, all_capabilities: bool = False) -> None:
    with tarfile.open(archive_path, mode="r:*") as archive:
        manifests, index_digest = _platform_manifests(archive)
        inventories = {}
        for architecture, manifest in manifests.items():
            packages = json.loads(_image_file(archive, manifest, "app/python-packages.json"))
            inventories[architecture] = _normalized_python_inventory(packages)
        lock_pins = (
            _core_capability_lock_versions()
            if all_capabilities
            else _lock_versions(ROOT / "requirements/kernel-core.lock")
        )
        _verify_core_package_inventories(inventories, lock_pins)
        print(
            f"Kernel core {'all-capabilities ' if all_capabilities else ''}OCI build verified: linux/amd64 + linux/arm64, "
            f"{len(lock_pins)} hash-locked packages plus pinned base tooling, index sha256:{index_digest}"
        )


def _verify_ml_anomaly(archive_path: Path) -> None:
    with tarfile.open(archive_path, mode="r:*") as archive:
        manifests, index_digest = _platform_manifests(archive)
        inventories = {}
        for architecture, manifest in manifests.items():
            packages = json.loads(_image_file(archive, manifest, "app/python-packages.json"))
            inventories[architecture] = _normalized_python_inventory(packages)
        lock_pins = _ml_lock_versions()
        _verify_ml_package_inventories(inventories, lock_pins)
        print(
            "Optional ML OCI build verified: linux/amd64 + linux/arm64, "
            f"{len(lock_pins)} locked packages and {len(inventories['amd64'])} matching total Python packages, "
            f"index sha256:{index_digest}"
        )


def _verify_postgis(archive_path: Path, lock: dict) -> None:
    selected = {
        "postgresql-16-postgis-3": lock["postgis_packages"]["POSTGIS_PACKAGE_VERSION"],
        "postgresql-16-postgis-3-scripts": lock["postgis_packages"]["POSTGIS_SCRIPTS_VERSION"],
    }
    with tarfile.open(archive_path, mode="r:*") as archive:
        manifests, index_digest = _platform_manifests(archive)
        actual_by_arch = {}
        for architecture, manifest in manifests.items():
            package_text = _image_file(archive, manifest, "usr/local/share/kokonut/database-packages.txt")
            packages = {}
            for line in package_text.decode("utf-8").splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0].split(":", 1)[0]
                    previous_version = packages.get(name)
                    if previous_version and previous_version != parts[1]:
                        raise LockError(
                            f"{architecture} package inventory has conflicting versions for "
                            f"{name}: {previous_version} and {parts[1]}"
                        )
                    packages[name] = parts[1]
            actual_by_arch[architecture] = packages
            for name, expected_version in selected.items():
                actual_version = packages.get(name)
                if actual_version != expected_version:
                    raise LockError(
                        f"{architecture} PostGIS package {name} has version {actual_version!r}; "
                        f"expected {expected_version!r}"
                    )
        amd64 = actual_by_arch["amd64"]
        arm64 = actual_by_arch["arm64"]
        actual_differences = {
            name: (amd64.get(name), arm64.get(name))
            for name in sorted(amd64.keys() | arm64.keys())
            if amd64.get(name) != arm64.get(name)
        }
        package_record = _load_json(ROOT / "config/postgres/kernel-postgis-packages.json")
        expected_differences = {
            name: (expectation["amd64"], expectation["arm64"])
            for name, expectation in package_record["architecture_specific_package_differences"].items()
        }
        if actual_differences != expected_differences:
            descriptions = []
            for name in sorted(actual_differences.keys() | expected_differences.keys()):
                actual = actual_differences.get(name)
                expected = expected_differences.get(name)
                if actual != expected:
                    actual_versions = actual or (None, None)
                    expected_versions = expected or (None, None)
                    descriptions.append(
                        f"{name}: actual amd64={actual_versions[0] or '<missing>'}, "
                        f"arm64={actual_versions[1] or '<missing>'}; expected "
                        f"amd64={expected_versions[0] or '<matching>'}, "
                        f"arm64={expected_versions[1] or '<matching>'}"
                    )
            raise LockError(
                "installed Debian package inventory differs from the locked architecture-specific contract:\n  "
                + "\n  ".join(descriptions[:50])
            )
        print(
            "PostGIS OCI build verified: linux/amd64 + linux/arm64, "
            f"{len(amd64)} amd64 and {len(arm64)} arm64 installed packages including selected PostGIS versions, "
            f"{len(expected_differences)} documented architecture-specific package difference(s), "
            f"index sha256:{index_digest}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application-oci", type=Path, help="verify a multi-platform Kernel OCI archive")
    parser.add_argument("--core-oci", type=Path, help="verify the optional minimal Kernel core OCI archive")
    parser.add_argument(
        "--core-capabilities-oci",
        type=Path,
        help="verify the core image with Web3, exports/S3, and local-media packages enabled",
    )
    parser.add_argument("--ml-anomaly-oci", type=Path, help="verify the optional ML worker OCI archive")
    parser.add_argument("--postgis-oci", type=Path, help="verify a multi-platform PostGIS OCI archive")
    args = parser.parse_args()
    try:
        lock = _load_json(LOCK_PATH)
        _validate_inputs(lock)
        print("Kernel release inputs match config/kernel/release-input-lock.json")
        if args.application_oci:
            _verify_application(args.application_oci)
        if args.core_oci:
            _verify_core_application(args.core_oci)
        if args.core_capabilities_oci:
            _verify_core_application(args.core_capabilities_oci, all_capabilities=True)
        if args.ml_anomaly_oci:
            _verify_ml_anomaly(args.ml_anomaly_oci)
        if args.postgis_oci:
            _verify_postgis(args.postgis_oci, lock)
        if not args.application_oci and not args.core_oci and not args.core_capabilities_oci and not args.ml_anomaly_oci and not args.postgis_oci:
            print("No OCI archives supplied; platform builds were not inspected")
    except (LockError, KeyError, OSError, tarfile.TarError, json.JSONDecodeError) as error:
        print(f"Kernel release gate failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
