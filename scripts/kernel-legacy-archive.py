#!/usr/bin/env python3
"""Encrypt stopped legacy volumes and repository configuration without starting services."""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

CONTAINERS = tuple(f"kokonut-intelligence-{name}-1" for name in (
    "database", "cache", "directus", "metabase", "clickhouse", "mosquitto", "caddy",
    "gateway", "grpc",
))
HELPER = "sha256:bf51ddd5679c92a6c804a8be0a5cfeccd90df534b9f0b5efe60ca583940c2db6"


def inspect_containers():
    result = subprocess.run(["docker", "inspect", *CONTAINERS], check=True,
                            capture_output=True, text=True)
    containers = json.loads(result.stdout)
    if any(c["State"]["Status"] != "exited" for c in containers):
        raise RuntimeError("All legacy containers must remain stopped")
    return containers


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--recipient", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    before = inspect_containers()
    volumes = sorted({mount["Name"] for c in before for mount in c["Mounts"]
                      if mount["Type"] == "volume"})
    args.destination.mkdir(mode=0o700)  # Existing archives are never overwritten.
    archive = args.destination / "legacy-storage.tar.age"
    partial = archive.with_suffix(".age.partial")
    command = ["docker", "run", "--rm", "--network", "none", "--read-only",
               "--user", "0", "--entrypoint", "tar"]
    for index, volume in enumerate(volumes):
        command += ["--mount", f"type=volume,src={volume},dst=/inventory/volume-{index},readonly"]
    # Include credential-bearing configs encrypted; never print their contents.
    command += ["--mount", f"type=bind,src={root / 'config'},dst=/inventory/config,readonly",
                "--mount", f"type=bind,src={root / 'extensions'},dst=/inventory/extensions,readonly",
                "--mount", f"type=bind,src={root / '.env.sops'},dst=/inventory/env.sops,readonly",
                HELPER, "-C", "/inventory", "-cf", "-", "."]
    producer = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        encryption = subprocess.run(["age", "-r", args.recipient, "-o", str(partial)],
                                    stdin=producer.stdout, stderr=subprocess.DEVNULL)
        producer.stdout.close()
        result = producer.wait()
        if encryption.returncode or result:
            raise RuntimeError("Archive incomplete; encrypted partial retained")
    finally:
        if producer.poll() is None:
            producer.terminate()
            producer.wait()
    after = inspect_containers()
    if [(c["Id"], c["State"]["FinishedAt"], c["Mounts"]) for c in before] != [
        (c["Id"], c["State"]["FinishedAt"], c["Mounts"]) for c in after
    ]:
        raise RuntimeError("Legacy state changed during archive; partial retained")
    partial.rename(archive)
    archive.chmod(0o600)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    manifest = {
        "format": 1, "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "archive": archive.name, "bytes": archive.stat().st_size, "sha256": digest.hexdigest(),
        "helper_image": HELPER,
        "volumes": {f"volume-{i}": volume for i, volume in enumerate(volumes)},
        "sources": [{"container": c["Name"], "image": c["Image"]} for c in before],
        "bindings": ["config/", "extensions/", ".env.sops"],
        "scope": "Stopped volume files and selected encrypted configuration; no external services, age identity, application checkout or independent remote backup.",
        "restore_rehearsed": False,
        "warning": "Raw PostgreSQL/ClickHouse files require compatible engines and crash recovery; not logical portable dumps.",
    }
    manifest_path = args.destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest_path.chmod(0o600)
    print(f"Encrypted archive created: {len(volumes)} stopped volumes; restore pending")


if __name__ == "__main__":
    main()
