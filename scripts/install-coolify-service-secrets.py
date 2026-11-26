#!/usr/bin/env python3
"""Install SOPS-managed secrets as private, service-scoped Coolify env files."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = ROOT / "config/kernel/coolify-service-secret-env.json"
DEFAULT_SOPS_FILE = ROOT / ".env.sops"
APPLICATION_ID_PATTERN = re.compile(r"^[a-z0-9]{24}$")
SERVICE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENVIRONMENT_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

REQUIRED_SERVICE_KEYS = {
    "app": {
        "PG_PASSWORD",
        "KOKONUT_OPERATOR_AUTH_PASSWORD",
        "KOKONUT_OPERATOR_OIDC_CLIENT_SECRET",
        "KOKONUT_OPERATOR_OIDC_STATE_SECRET",
    },
    "worker": {"PG_PASSWORD"},
    "database": {"POSTGRES_PASSWORD"},
    "runtime-role-bootstrap": {
        "KOKONUT_DB_ADMIN_PASSWORD",
        "KOKONUT_OPERATOR_AUTH_PASSWORD",
        "KOKONUT_RUNTIME_PASSWORD",
        "KOKONUT_SCHEDULER_PASSWORD",
        "KOKONUT_WORKER_RUNTIME_PASSWORD",
    },
    "zitadel-api": {
        "ZITADEL_DATABASE_POSTGRES_DSN",
        "ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD",
        "ZITADEL_MASTERKEY",
    },
    "zitadel-db": {"KOKONUT_ZITADEL_DATABASE_PASSWORD", "POSTGRES_PASSWORD"},
    "zitadel-login": {"ZITADEL_SESSION_COOKIE_SECRET"},
}

SERVICE_KEY_ALIASES = {
    ("app", "PG_PASSWORD"): "KOKONUT_RUNTIME_PASSWORD",
    ("worker", "PG_PASSWORD"): "KOKONUT_WORKER_RUNTIME_PASSWORD",
    ("runtime-role-bootstrap", "KOKONUT_DB_ADMIN_PASSWORD"): "POSTGRES_PASSWORD",
    ("zitadel-db", "POSTGRES_PASSWORD"): "KOKONUT_ZITADEL_POSTGRES_ADMIN_PASSWORD",
    ("worker", "KOKONUT_REMOTE_SENSING_COPERNICUS_EMAIL"): "COPERNICUS_EMAIL",
    ("worker", "KOKONUT_REMOTE_SENSING_COPERNICUS_PASSWORD"): "COPERNICUS_PASSWORD",
    ("worker", "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_ID"): "COPERNICUS_CLIENT_ID",
    ("worker", "KOKONUT_REMOTE_SENSING_COPERNICUS_CLIENT_SECRET"): (
        "COPERNICUS_CLIENT_SECRET"
    ),
    ("worker", "KOKONUT_CLIMATE_GEE_SERVICE_ACCOUNT_KEY"): "GEE_SERVICE_ACCOUNT_KEY",
    ("worker", "KOKONUT_REMOTE_SENSING_GEE_SERVICE_ACCOUNT_KEY"): "GEE_SERVICE_ACCOUNT_KEY",
    ("worker", "KOKONUT_WEATHER_FORECAST_OPENWEATHERMAP_API_KEY"): "KOKONUT_WEATHER_OPENWEATHERMAP_API_KEY",
    ("zitadel-api", "ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD"): "KOKONUT_ZITADEL_ADMIN_PASSWORD",
    ("zitadel-api", "ZITADEL_MASTERKEY"): "KOKONUT_ZITADEL_MASTERKEY",
    ("zitadel-login", "ZITADEL_SESSION_COOKIE_SECRET"): "KOKONUT_ZITADEL_LOGIN_COOKIE_SECRET",
}

REMOTE_INSTALL = r"""import json, os, pathlib, re, stat, sys, tempfile
application_id = sys.argv[1]
if not re.fullmatch(r"[a-z0-9]{24}", application_id):
    raise SystemExit("Coolify application id is invalid")
payload = sys.stdin.buffer.read(262145)
if len(payload) > 262144:
    raise SystemExit("service secret payload exceeds the size limit")
try:
    files = json.loads(payload)
except Exception:
    raise SystemExit("service secret payload is invalid") from None
if not isinstance(files, dict) or not files:
    raise SystemExit("service secret payload has no service files")
service_pattern = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
key_pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
base = pathlib.Path("/data/coolify/applications") / application_id
private = base / "private"
if private.is_symlink() or not private.is_dir():
    raise SystemExit("Coolify application private directory is unavailable")
data_root = base / "data"
if data_root.is_symlink() or (data_root.exists() and not data_root.is_dir()):
    raise SystemExit("Coolify application data path is not a directory")
data_root.mkdir(mode=0o750, exist_ok=True)
os.chown(data_root, 0, 0)
os.chmod(data_root, 0o755)
sensor_inputs = data_root / "sensor-inputs"
if sensor_inputs.is_symlink() or (sensor_inputs.exists() and not sensor_inputs.is_dir()):
    raise SystemExit("Coolify sensor-input path is not a directory")
sensor_inputs.mkdir(mode=0o750, exist_ok=True)
os.chown(sensor_inputs, 0, 10001)
os.chmod(sensor_inputs, 0o750)
directory = private / "runtime-env"
if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
    raise SystemExit("service secret directory is not a directory")
directory.mkdir(mode=0o700, exist_ok=True)
os.chown(directory, 0, 0)
os.chmod(directory, 0o700)
installed = 0
key_count = 0
validated = {}
for service, content in files.items():
    if not isinstance(service, str) or not service_pattern.fullmatch(service):
        raise SystemExit("service secret payload contains an invalid service name")
    if not isinstance(content, str) or len(content.encode("utf-8")) > 65536:
        raise SystemExit("service secret payload contains an invalid file")
    seen = set()
    for line in content.splitlines():
        if not line:
            continue
        key, sep, _ = line.partition("=")
        if not sep or not key_pattern.fullmatch(key) or key in seen:
            raise SystemExit("service secret file contains an invalid or duplicate entry")
        seen.add(key)
    target = directory / (service + ".env")
    if target.is_symlink():
        raise SystemExit("existing service secret target is a symlink")
    if target.exists() and not target.is_file():
        raise SystemExit("existing service secret target is not a regular file")
    validated[service] = (content, len(seen))
staged = {}
try:
    for service, (content, count) in validated.items():
        fd, temporary = tempfile.mkstemp(prefix="." + service + ".env.", dir=directory)
        staged[service] = temporary
        os.fchown(fd, 0, 10001)
        os.fchmod(fd, 0o440)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        key_count += count
    for service, temporary in list(staged.items()):
        target = directory / (service + ".env")
        os.replace(temporary, target)
        staged.pop(service, None)
        installed += 1
except BaseException:
    for temporary in staged.values():
        try: os.unlink(temporary)
        except FileNotFoundError: pass
    raise
directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
try:
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
for service, content in files.items():
    target = directory / (service + ".env")
    mode = stat.S_IMODE(target.stat().st_mode)
    if target.stat().st_uid != 0 or target.stat().st_gid != 10001 or mode != 0o440:
        raise SystemExit("installed service secret permissions did not verify")
print("installed service_files=%d key_entries=%d mode=0440 owner=0:10001" % (installed, key_count))
"""


def _load_inventory(path: Path) -> dict[str, list[str]]:
    inventory = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(inventory, dict)
        or inventory.get("format_version") != 1
        or not isinstance(inventory.get("services"), dict)
    ):
        raise ValueError("service secret inventory is invalid")
    result: dict[str, list[str]] = {}
    for service, keys in inventory["services"].items():
        if (
            not isinstance(service, str)
            or not SERVICE_NAME_PATTERN.fullmatch(service)
            or not isinstance(keys, list)
            or any(not isinstance(key, str) or not ENVIRONMENT_KEY_PATTERN.fullmatch(key) for key in keys)
            or any(key.startswith("MOBILE_MEDIA_") for key in keys)
            or len(set(keys)) != len(keys)
        ):
            raise ValueError("service secret inventory contains an invalid entry")
        result[service] = keys
    return result


def _load_sops_values(path: Path) -> dict[str, str]:
    result = subprocess.run(
        ["sops", "-d", "--input-type", "dotenv", "--output-type", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    values = json.loads(result.stdout)
    if not isinstance(values, dict) or any(not isinstance(key, str) for key in values):
        raise ValueError("decrypted SOPS values are invalid")
    return {key: value for key, value in values.items() if isinstance(value, str)}


def _resolve_secret(service: str, key: str, values: dict[str, str]) -> str | None:
    source_key = SERVICE_KEY_ALIASES.get((service, key))
    if source_key:
        source = values.get(source_key)
        if source:
            return source
    direct = values.get(key)
    if isinstance(direct, str) and direct:
        return direct
    if service == "zitadel-api" and key == "ZITADEL_DATABASE_POSTGRES_DSN":
        password = values.get("KOKONUT_ZITADEL_DATABASE_PASSWORD", "")
        if password:
            from urllib.parse import quote

            return f"postgresql://zitadel:{quote(password, safe='')}@zitadel-db:5432/zitadel?sslmode=disable"
    if key == "KOKONUT_BAAL_INDEXER_RPC_ENDPOINT":
        return values.get("GNOSIS_RPC_URL") or None
    if key == "KOKONUT_GNOSIS_INDEXER_RPC_ENDPOINTS":
        endpoint = values.get("GNOSIS_RPC_URL", "")
        return json.dumps({"gnosis": endpoint}, separators=(",", ":")) if endpoint else None
    if key == "KOKONUT_RPC_INDEXER_RPC_ENDPOINTS":
        source_names = {
            "ethereum": "ETH_RPC_URL",
            "optimism": "OPTIMISM_RPC_URL",
            "base": "BASE_RPC_URL",
            "arbitrum": "ARBITRUM_RPC_URL",
            "gnosis": "GNOSIS_RPC_URL",
            "celo": "CELO_RPC_URL",
            "celo-alfajores": "CELO_ALFAJORES_RPC_URL",
        }
        endpoints = {chain: values[name] for chain, name in source_names.items() if values.get(name)}
        return json.dumps(endpoints, separators=(",", ":")) if endpoints else None
    return None


def _render_service_files(
    services: dict[str, list[str]], values: dict[str, str]
) -> tuple[dict[str, str], dict[str, int]]:
    files: dict[str, str] = {}
    counts: dict[str, int] = {}
    missing_required: list[str] = []
    for service, keys in services.items():
        absent_from_inventory = REQUIRED_SERVICE_KEYS.get(service, set()) - set(keys)
        missing_required.extend(f"{service}:{key}" for key in sorted(absent_from_inventory))
        entries: list[str] = []
        for key in keys:
            value = _resolve_secret(service, key, values)
            if value is None or value == "":
                if key in REQUIRED_SERVICE_KEYS.get(service, set()):
                    missing_required.append(f"{service}:{key}")
                continue
            if "\x00" in value or "\r" in value or "\n" in value:
                raise ValueError(f"service secret {service}:{key} contains an unsupported character")
            entries.append(f"{key}={value}\n")
        files[service] = "".join(entries)
        counts[service] = len(entries)
    for service, keys in REQUIRED_SERVICE_KEYS.items():
        if service not in services:
            missing_required.extend(f"{service}:{key}" for key in sorted(keys))
    if missing_required:
        raise ValueError("required SOPS service secret mappings are missing: " + ", ".join(sorted(set(missing_required))))
    return files, counts


def _build_payload(args: argparse.Namespace) -> tuple[bytes, dict[str, int]]:
    if not APPLICATION_ID_PATTERN.fullmatch(args.application_id):
        raise ValueError("Coolify application ID has an invalid format")
    services = _load_inventory(args.inventory)
    values = _load_sops_values(args.sops_file)
    try:
        files, counts = _render_service_files(services, values)
    finally:
        values.clear()
    return json.dumps(files, separators=(",", ":")).encode("utf-8"), counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-host", required=True, help="SSH host alias or root@host")
    parser.add_argument("--application-id", required=True, help="Coolify application UUID")
    parser.add_argument("--sops-file", type=Path, default=DEFAULT_SOPS_FILE)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--install", action="store_true", help="install generated files on the candidate host")
    args = parser.parse_args()

    try:
        payload, counts = _build_payload(args)
    except (OSError, subprocess.CalledProcessError, UnicodeError, json.JSONDecodeError, ValueError):
        print("could not prepare service-scoped SOPS environment files", file=sys.stderr)
        return 1

    if not args.install:
        summary = ", ".join(f"{service}={count}" for service, count in sorted(counts.items()))
        print(f"SOPS service-secret coverage is complete; per-service key counts: {summary}")
        return 0

    remote_command = "python3 -c {} {}".format(shlex.quote(REMOTE_INSTALL), shlex.quote(args.application_id))
    try:
        result = subprocess.run(
            ["ssh", "-T", args.ssh_host, remote_command],
            input=payload,
            capture_output=True,
            check=False,
        )
    except OSError:
        print("SSH could not install service-scoped environment files", file=sys.stderr)
        return 1
    if result.returncode:
        print("service-scoped environment installation failed; no secret values were displayed", file=sys.stderr)
        return 1
    summary = result.stdout.decode("utf-8", errors="replace").strip()
    if not summary.startswith("installed service_files=") or "mode=0440 owner=0:10001" not in summary:
        print("service-scoped environment install did not return verified metadata", file=sys.stderr)
        return 1
    print("Installed SOPS-managed service environment files; " + summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
