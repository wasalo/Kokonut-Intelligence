from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


class PublishedImageError(RuntimeError):
    pass


INDEX_MEDIA_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
REPOSITORY_PATTERN = re.compile(r"ghcr\.io/[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*")


def immutable_reference(repository: str, digest: str) -> str:
    if REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise PublishedImageError("GHCR repository must be a lowercase ghcr.io owner/name reference without a tag")
    if DIGEST_PATTERN.fullmatch(digest) is None:
        raise PublishedImageError("published image must use an immutable sha256 digest")
    return f"{repository}@{digest}"


def verify_published_image(descriptor_path: Path, manifest_path: Path, repository: str) -> str:
    try:
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise PublishedImageError(f"cannot read remote manifest verification input: {error}") from error
    if not isinstance(descriptor, dict) or not isinstance(manifest, dict):
        raise PublishedImageError("remote descriptor and manifest must be JSON objects")
    digest = descriptor.get("digest", "")
    reference = immutable_reference(repository, digest)
    if descriptor.get("mediaType") not in INDEX_MEDIA_TYPES or manifest.get("mediaType") != descriptor.get("mediaType"):
        raise PublishedImageError("published PostGIS reference is not a multi-platform image index")
    actual_digest = f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}"
    if actual_digest != digest:
        raise PublishedImageError("remote manifest bytes do not match the registry digest")
    descriptors = manifest.get("manifests")
    if not isinstance(descriptors, list):
        raise PublishedImageError("published PostGIS image index has no manifest list")
    platforms: dict[str, int] = {}
    for item in descriptors:
        if not isinstance(item, dict):
            raise PublishedImageError("published PostGIS image index contains an invalid manifest descriptor")
        platform = item.get("platform")
        if not isinstance(platform, dict):
            continue
        key = f"{platform.get('os')}/{platform.get('architecture')}"
        if key in {"linux/amd64", "linux/arm64"}:
            if DIGEST_PATTERN.fullmatch(item.get("digest", "")) is None:
                raise PublishedImageError(f"published PostGIS {key} manifest has an invalid digest")
            platforms[key] = platforms.get(key, 0) + 1
    invalid_platforms = {platform: count for platform, count in platforms.items() if count != 1}
    if invalid_platforms:
        raise PublishedImageError(f"published PostGIS index contains duplicate platform manifests: {invalid_platforms}")
    missing = {"linux/amd64", "linux/arm64"} - platforms.keys()
    if missing:
        raise PublishedImageError(f"published PostGIS index is missing platforms: {', '.join(sorted(missing))}")
    return reference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    try:
        print(verify_published_image(args.descriptor, args.manifest, args.repository))
    except PublishedImageError as error:
        print(f"PostGIS publication verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
