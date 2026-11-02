"""The opt-in core Gateway starts without capability-specific packages."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gateway_app_creation_does_not_import_core_optional_capabilities(tmp_path: Path) -> None:
    script = r'''
import importlib.abc
import json
import os
import sys

blocked = {"web3", "eth_abi", "boto3", "botocore", "openpyxl", "Crypto"}
attempts = []

class RejectOptionalPackages(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            attempts.append(fullname)
            raise ModuleNotFoundError("optional package blocked: " + fullname)

sys.meta_path.insert(0, RejectOptionalPackages())
from services.gateway.app import create_app

class RateLimiter:
    def check(self, _caller):
        return True
    def retry_after(self, _caller):
        return 0

app = create_app(rate_limiter=RateLimiter())
print(json.dumps({"routes": len(app.routes), "attempts": attempts}))
'''
    environment = {
        **os.environ,
        "KOKONUT_ENV": "development",
        "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH": str(tmp_path / "gateway-audit.sqlite3"),
        "KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS": "100",
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    import json

    output = json.loads(result.stdout.splitlines()[-1])
    assert output["routes"] > 0
    assert output["attempts"] == []


def test_missing_capability_packages_fail_closed_at_their_feature_boundary(tmp_path: Path) -> None:
    script = r'''
import importlib.abc
import json
import os
import sys

blocked = {"web3", "eth_abi", "boto3", "botocore", "openpyxl", "Crypto"}
attempts = []

class RejectOptionalPackages(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            attempts.append(fullname)
            raise ModuleNotFoundError("optional package blocked: " + fullname)

sys.meta_path.insert(0, RejectOptionalPackages())
from services.mobile.media_storage import create_media_store, MediaStorageNotConfigured

errors = {}
try:
    create_media_store(environ={
        "MOBILE_MEDIA_PROVIDER": "s3",
        "MOBILE_MEDIA_S3_ENDPOINT": "https://objects.example",
        "MOBILE_MEDIA_S3_BUCKET": "private-test",
        "MOBILE_MEDIA_S3_ACCESS_KEY_ID": "synthetic-access",
        "MOBILE_MEDIA_S3_SECRET_ACCESS_KEY": "synthetic-secret",
        "MOBILE_MEDIA_S3_REGION": "auto",
    })
except MediaStorageNotConfigured as exc:
    errors["s3"] = str(exc)

from services.mobile.local_media import LocalMediaStore
try:
    LocalMediaStore(os.environ["KERNEL_CORE_TEST_MEDIA_DIR"], "01" * 32)
except MediaStorageNotConfigured as exc:
    errors["local_media"] = str(exc)

from services.ingestion.market_data import parse_pink_sheet
try:
    parse_pink_sheet(b"synthetic spreadsheet")
except RuntimeError as exc:
    errors["spreadsheet"] = str(exc)

try:
    import services.ingestion.rpc_indexer
except ModuleNotFoundError as exc:
    errors["web3"] = str(exc)

print(json.dumps({"errors": errors, "attempts": attempts}))
'''
    media_directory = tmp_path / "private-media"
    media_directory.mkdir(mode=0o700)
    environment = {
        **os.environ,
        "KOKONUT_ENV": "development",
        "KOKONUT_ENV_SECRETS_NOT_REQUIRED": "true",
        "KERNEL_CORE_TEST_MEDIA_DIR": str(media_directory),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    import json

    output = json.loads(result.stdout.splitlines()[-1])
    assert output["errors"] == {
        "s3": "S3-compatible object storage client is unavailable",
        "local_media": "Local media encryption driver is unavailable",
        "spreadsheet": "openpyxl is required for World Bank Pink Sheet parsing",
        "web3": "optional package blocked: web3",
    }
    assert set(output["attempts"]) == {"boto3", "Crypto", "openpyxl", "web3"}
