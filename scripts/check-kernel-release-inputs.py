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
    if set(package_record.get("verified_package_catalog_architectures", [])) != {"amd64", "arm64"}:
        raise LockError("PostGIS package catalog must be verified for amd64 and arm64")
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
    for descriptor in index_bytes.get("manifests", []):
        platform = descriptor.get("platform") or {}
        if platform.get("os") != "linux":
            continue
        architecture = platform.get("architecture")
        if architecture not in {"amd64", "arm64"}:
            continue
        manifests[architecture] = json.loads(_blob(archive, descriptor["digest"]).read().decode("utf-8"))
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


def _verify_application(archive_path: Path) -> None:
    with tarfile.open(archive_path, mode="r:*") as archive:
        manifests, index_digest = _platform_manifests(archive)
        inventories = {}
        for architecture, manifest in manifests.items():
            packages = json.loads(_image_file(archive, manifest, "app/python-packages.json"))
            inventories[architecture] = {
                item["name"].lower().replace("_", "-").replace(".", "-"): item["version"]
                for item in packages
            }
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
                    packages[parts[0].split(":", 1)[0]] = parts[1]
            actual_by_arch[architecture] = packages
            for name, expected_version in selected.items():
                actual_version = packages.get(name)
                if actual_version != expected_version:
                    raise LockError(
                        f"{architecture} PostGIS package {name} has version {actual_version!r}; "
                        f"expected {expected_version!r}"
                    )
        print(
            "PostGIS OCI build verified: linux/amd64 + linux/arm64, "
            f"selected packages match, index sha256:{index_digest}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application-oci", type=Path, help="verify a multi-platform Kernel OCI archive")
    parser.add_argument("--postgis-oci", type=Path, help="verify a multi-platform PostGIS OCI archive")
    args = parser.parse_args()
    try:
        lock = _load_json(LOCK_PATH)
        _validate_inputs(lock)
        print("Kernel release inputs match config/kernel/release-input-lock.json")
        if args.application_oci:
            _verify_application(args.application_oci)
        if args.postgis_oci:
            _verify_postgis(args.postgis_oci, lock)
        if not args.application_oci and not args.postgis_oci:
            print("No OCI archives supplied; platform builds were not inspected")
    except (LockError, KeyError, OSError, tarfile.TarError, json.JSONDecodeError) as error:
        print(f"Kernel release gate failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
