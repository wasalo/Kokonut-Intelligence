#!/usr/bin/env python3
"""Generate the optional, namespaced Python SDK protobuf/gRPC package."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = ROOT / "proto"
PACKAGE_ROOT = ROOT / "sdk/python/kokonut/grpc"
PROTO_FILES = (
    "common/pagination.proto",
    "data/v1/types.proto",
    "data/v1/service.proto",
    "ecocredit/v1/types.proto",
    "ecocredit/v1/service.proto",
)
IMPORT_PREFIXES = {
    "common": "kokonut.grpc.common",
    "data.v1": "kokonut.grpc.data.v1",
    "ecocredit.v1": "kokonut.grpc.ecocredit.v1",
}
CODEGEN_VERSIONS = {"grpcio-tools": "1.68.1", "protobuf": "5.29.1"}


def generate() -> dict[Path, str]:
    try:
        import grpc_tools  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "SDK protobuf code generation requires grpcio-tools==1.68.1 and "
            "protobuf==5.29.1; install the SDK grpc-codegen extra"
        ) from exc

    installed_versions = {}
    for package, expected in CODEGEN_VERSIONS.items():
        try:
            installed = version(package)
        except PackageNotFoundError as exc:
            raise RuntimeError(
                f"{package}=={expected} is required; install the SDK grpc-codegen extra"
            ) from exc
        if installed != expected:
            installed_versions[package] = installed
    if installed_versions:
        actual = ", ".join(
            f"{package}=={installed}" for package, installed in installed_versions.items()
        )
        expected = ", ".join(
            f"{package}=={pinned}" for package, pinned in CODEGEN_VERSIONS.items()
        )
        raise RuntimeError(
            f"SDK protobuf generation requires {expected}; found {actual}. "
            "Install the SDK grpc-codegen extra in an isolated environment."
        )

    with tempfile.TemporaryDirectory(prefix="kokonut-sdk-protos-") as temp_dir:
        output_root = Path(temp_dir)
        command = [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{PROTO_ROOT}",
            f"--python_out={output_root}",
            f"--grpc_python_out={output_root}",
            *PROTO_FILES,
        ]
        subprocess.run(command, cwd=ROOT, check=True)

        generated: dict[Path, str] = {}
        for proto_file in PROTO_FILES:
            proto_path = Path(proto_file)
            generated_paths = (
                proto_path.with_name(f"{proto_path.stem}_pb2.py"),
                proto_path.with_name(f"{proto_path.stem}_pb2_grpc.py"),
            )
            for generated_path in generated_paths:
                source = output_root / generated_path
                if not source.is_file():
                    raise RuntimeError(f"protoc did not generate {generated_path}")
                content = source.read_text(encoding="utf-8")
                for import_path, package_path in IMPORT_PREFIXES.items():
                    content = re.sub(
                        rf"(?m)^from {re.escape(import_path)} import ",
                        f"from {package_path} import ",
                        content,
                    )
                if generated_path.name.endswith("_pb2.py"):
                    module_pattern = (
                        r"(_builder\.BuildTopDescriptorsAndMessages\(DESCRIPTOR, )"
                        r"'([^']+)'"
                    )
                    content, replacements = re.subn(
                        module_pattern,
                        lambda match: (
                            f"{match.group(1)}'kokonut.grpc.{match.group(2)}'"
                        ),
                        content,
                        count=1,
                    )
                    if replacements != 1:
                        raise RuntimeError(
                            f"could not namespace generated module metadata in {generated_path}"
                        )
                generated[Path("kokonut/grpc") / generated_path] = content
        return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare generated output with checked-in modules without writing",
    )
    args = parser.parse_args()

    try:
        generated = generate()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        package_base = ROOT / "sdk/python"
        stale = [
            rel_path
            for rel_path, expected in generated.items()
            if not (package_base / rel_path).is_file()
            or (package_base / rel_path).read_text(encoding="utf-8") != expected
        ]
        generated_files = {
            path.relative_to(package_base)
            for path in PACKAGE_ROOT.rglob("*_pb2*.py")
        }
        stale_files = generated_files - generated.keys()
        missing_files = generated.keys() - generated_files
        if stale or stale_files or missing_files:
            print("Generated SDK protobuf modules are stale:", file=sys.stderr)
            for rel_path in stale:
                print(f"  {rel_path}", file=sys.stderr)
            for rel_path in sorted(stale_files | missing_files):
                print(f"  {rel_path}", file=sys.stderr)
            return 1
        print(f"Verified {len(generated)} generated SDK modules.")
        return 0

    for rel_path, content in generated.items():
        destination = ROOT / "sdk/python" / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    print(f"Generated {len(generated)} modules under {PACKAGE_ROOT}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
