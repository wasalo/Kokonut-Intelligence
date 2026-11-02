"""Build-time inventory of bundled code; contains no environment or credentials."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/app"))
    parser.add_argument(
        "--target", required=True,
        choices=("kernel", "kernel-core", "grpc", "mqtt", "oidc", "ml-anomaly"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    paths = []
    for directory, suffix in (("services", ".py"), ("schemas", ".sql"),
                              ("requirements", ".txt"), ("proto", ".proto"),
                              ("generated", ".py")):
        paths.extend((root / directory).rglob(f"*{suffix}"))
    for suffix in (".html", ".js", ".css"):
        paths.extend((root / "apps").rglob(f"*{suffix}"))
    paths.extend(root / name for name in ("VERSION", "pyproject.toml", "Dockerfile.kernel"))
    if args.target == "kernel-core":
        paths.extend((root / "requirements").glob("kernel-core*.in"))
        paths.extend((root / "requirements").glob("kernel-core*.lock"))
    files = {}
    for path in sorted(set(paths)):
        if path.is_file() and "__pycache__" not in path.parts:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("Manifest input must be a regular bundled file")
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "format": 1, "target": args.target,
        "scope": "Python, SQL, requirement, protobuf, and first-party browser sources; VERSION, pyproject and image recipe. Configuration, secrets, installed packages and runtime data excluded.",
        "source_sha256": hashlib.sha256(canonical).hexdigest(), "files": files,
    }
    (root / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
