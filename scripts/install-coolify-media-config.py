#!/usr/bin/env python3
"""Install the SOPS-managed media settings as a Gateway-only Coolify host file."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath

MEDIA_KEYS = frozenset(
    {
        "MOBILE_MEDIA_PROVIDER",
        "MOBILE_MEDIA_ENCRYPTION_KEY",
        "MOBILE_MEDIA_LOCAL_DIRECTORY",
        "MOBILE_MEDIA_LOCAL_KEY",
        "MOBILE_MEDIA_S3_ENDPOINT",
        "MOBILE_MEDIA_S3_BUCKET",
        "MOBILE_MEDIA_S3_ACCESS_KEY_ID",
        "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY",
        "MOBILE_MEDIA_S3_REGION",
    }
)
APPLICATION_ID_PATTERN = re.compile(r"^[a-z0-9]{24}$")
REMOTE_INSTALL = r"""import os, pathlib, re, stat, sys, tempfile
destination = pathlib.Path(sys.argv[1])
application_id = sys.argv[2]
root = pathlib.PurePosixPath("/data/coolify/applications")
parts = destination.parts
if (not destination.is_absolute() or ".." in parts or len(parts) != 7
        or pathlib.PurePosixPath(*parts[:4]) != root
        or parts[4] != application_id or parts[5] != "private"
        or parts[6] != "media.env"):
    raise SystemExit("destination is outside the selected Coolify application")
allowed = {
    "MOBILE_MEDIA_PROVIDER", "MOBILE_MEDIA_ENCRYPTION_KEY",
    "MOBILE_MEDIA_LOCAL_DIRECTORY", "MOBILE_MEDIA_LOCAL_KEY",
    "MOBILE_MEDIA_S3_ENDPOINT", "MOBILE_MEDIA_S3_BUCKET",
    "MOBILE_MEDIA_S3_ACCESS_KEY_ID", "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY",
    "MOBILE_MEDIA_S3_REGION",
}
payload = sys.stdin.buffer.read(16385)
if len(payload) > 16384:
    raise SystemExit("media configuration exceeds the size limit")
text = payload.decode("utf-8")
values = {}
for line_number, raw_line in enumerate(text.splitlines(), 1):
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    key, separator, value = line.partition("=")
    key = key.strip()
    if not separator or key not in allowed or key in values:
        raise SystemExit("media configuration contains an invalid entry")
    values[key] = value.strip()
def plain(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value
provider = plain(values.get("MOBILE_MEDIA_PROVIDER", "s3")).lower()
if provider not in {"s3", "local"}:
    raise SystemExit("media provider is unsupported")
if not (plain(values.get("MOBILE_MEDIA_ENCRYPTION_KEY", ""))
        or plain(values.get("MOBILE_MEDIA_LOCAL_KEY", ""))):
    raise SystemExit("media encryption key is missing")
required = (
    ("MOBILE_MEDIA_S3_ENDPOINT", "MOBILE_MEDIA_S3_BUCKET",
     "MOBILE_MEDIA_S3_ACCESS_KEY_ID", "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY",
     "MOBILE_MEDIA_S3_REGION") if provider == "s3"
    else ("MOBILE_MEDIA_LOCAL_DIRECTORY",)
)
if any(not plain(values.get(key, "")).strip() for key in required):
    raise SystemExit("required media settings are missing")
parent = destination.parent
parent.mkdir(mode=0o700, parents=True, exist_ok=True)
parent_stat = parent.lstat()
if not stat.S_ISDIR(parent_stat.st_mode):
    raise SystemExit("media configuration parent is not a directory")
os.chown(parent, 0, 0)
os.chmod(parent, 0o700)
try:
    existing = destination.lstat()
except FileNotFoundError:
    existing = None
if existing is not None and not stat.S_ISREG(existing.st_mode):
    raise SystemExit("existing media configuration target is not a regular file")
descriptor, temporary = tempfile.mkstemp(prefix=".media.env.", dir=parent)
try:
    os.fchown(descriptor, 0, 10001)
    os.fchmod(descriptor, 0o440)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
except BaseException:
    try:
        os.close(descriptor)
    except OSError:
        pass
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    raise
installed = destination.stat()
if (not stat.S_ISREG(installed.st_mode) or installed.st_uid != 0
        or installed.st_gid != 10001 or stat.S_IMODE(installed.st_mode) != 0o440):
    raise SystemExit("installed media configuration permissions did not verify")
print("installed mode=0440 owner=0:10001 keys=" + ",".join(sorted(values)))
"""


def _plain_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _extract_media_configuration(decrypted: str) -> bytes:
    values: dict[str, str] = {}
    lines: list[str] = []
    for raw_line in decrypted.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, raw_value = line.partition("=")
        key = key.strip()
        if not separator or key not in MEDIA_KEYS:
            continue
        if key in values:
            raise ValueError("encrypted media configuration contains a duplicate key")
        value = raw_value.strip()
        if not value:
            continue
        values[key] = value
        lines.append(f"{key}={value}")

    provider = _plain_value(values.get("MOBILE_MEDIA_PROVIDER", "s3")).lower()
    if provider not in {"s3", "local"}:
        raise ValueError("encrypted media configuration selects an unsupported provider")
    if not (
        _plain_value(values.get("MOBILE_MEDIA_ENCRYPTION_KEY", ""))
        or _plain_value(values.get("MOBILE_MEDIA_LOCAL_KEY", ""))
    ):
        raise ValueError("encrypted media configuration has no encryption key")
    required = (
        (
            "MOBILE_MEDIA_S3_ENDPOINT",
            "MOBILE_MEDIA_S3_BUCKET",
            "MOBILE_MEDIA_S3_ACCESS_KEY_ID",
            "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY",
            "MOBILE_MEDIA_S3_REGION",
        )
        if provider == "s3"
        else ("MOBILE_MEDIA_LOCAL_DIRECTORY",)
    )
    if any(not _plain_value(values.get(key, "")).strip() for key in required):
        raise ValueError("encrypted media configuration is incomplete")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _validate_destination(destination: str, application_id: str) -> PurePosixPath:
    if not APPLICATION_ID_PATTERN.fullmatch(application_id):
        raise ValueError("Coolify application ID has an invalid format")
    path = PurePosixPath(destination)
    expected_parent = PurePosixPath("/data/coolify/applications", application_id, "private")
    if not path.is_absolute() or ".." in path.parts or path.parent != expected_parent or path.name != "media.env":
        raise ValueError("destination must be the private media.env file in the selected application")
    return path


def _install(args: argparse.Namespace) -> int:
    try:
        destination = _validate_destination(args.destination, args.application_id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        decrypted = subprocess.run(
            [
                "sops",
                "-d",
                "--input-type",
                "dotenv",
                "--output-type",
                "dotenv",
                str(args.sops_file),
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        payload = _extract_media_configuration(decrypted)
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError):
        print("could not prepare the SOPS-managed media configuration", file=sys.stderr)
        return 1
    finally:
        if "decrypted" in locals():
            del decrypted

    remote_command = "python3 -c {} {} {}".format(
        shlex.quote(REMOTE_INSTALL),
        shlex.quote(str(destination)),
        shlex.quote(args.application_id),
    )
    try:
        result = subprocess.run(
            ["ssh", "-T", args.ssh_host, remote_command],
            input=payload,
            capture_output=True,
            check=False,
        )
    except OSError:
        print("SSH could not install the private media configuration", file=sys.stderr)
        return 1
    if result.returncode:
        print("remote media configuration install failed; no secret values were displayed", file=sys.stderr)
        return 1
    summary = result.stdout.decode("utf-8", errors="replace").strip()
    if not summary.startswith("installed mode=0440 owner=0:10001 keys="):
        print("remote media configuration install did not return verified metadata", file=sys.stderr)
        return 1
    print(f"Installed Gateway-only media configuration at {destination}: {summary}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host", required=True, help="SSH host alias or root@host")
    parser.add_argument("--application-id", required=True, help="Coolify application UUID")
    parser.add_argument("--destination", required=True, help="Coolify private host-file destination")
    parser.add_argument("--sops-file", type=Path, default=Path(".env.sops"))
    return _install(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
