"""Contracts for transferring only SOPS-managed media settings to Coolify."""

from __future__ import annotations

import importlib.util
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "install_coolify_media_config",
    ROOT / "scripts" / "install-coolify-media-config.py",
)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_extractor_emits_only_nonempty_allowlisted_media_keys():
    source = """ALERT_SMTP_PASSWORD=must-not-be-copied
MOBILE_MEDIA_PROVIDER=s3
MOBILE_MEDIA_ENCRYPTION_KEY=synthetic-encryption-key
MOBILE_MEDIA_LOCAL_DIRECTORY=
MOBILE_MEDIA_S3_ENDPOINT=https://r2.example.test
MOBILE_MEDIA_S3_BUCKET=synthetic-bucket
MOBILE_MEDIA_S3_ACCESS_KEY_ID=synthetic-access
MOBILE_MEDIA_S3_SECRET_ACCESS_KEY=synthetic-secret
MOBILE_MEDIA_S3_REGION=auto
"""

    result = installer._extract_media_configuration(source).decode()

    assert "ALERT_SMTP_PASSWORD" not in result
    assert "must-not-be-copied" not in result
    assert "MOBILE_MEDIA_LOCAL_DIRECTORY=" not in result
    assert "MOBILE_MEDIA_S3_BUCKET=synthetic-bucket" in result
    assert result.endswith("\n")


def test_extractor_rejects_incomplete_s3_configuration():
    with pytest.raises(ValueError, match="incomplete"):
        installer._extract_media_configuration("MOBILE_MEDIA_PROVIDER=s3\nMOBILE_MEDIA_ENCRYPTION_KEY=synthetic\n")


def test_destination_is_limited_to_selected_application_private_file():
    application_id = "fdphpruj8jxien23ockmbw0j"
    result = installer._validate_destination(
        f"/data/coolify/applications/{application_id}/private/media.env",
        application_id,
    )

    assert result == PurePosixPath(f"/data/coolify/applications/{application_id}/private/media.env")
    with pytest.raises(ValueError, match="destination"):
        installer._validate_destination(
            f"/data/coolify/applications/{application_id}/../media.env",
            application_id,
        )


def test_remote_installer_program_is_valid_python():
    compile(installer.REMOTE_INSTALL, "coolify-media-installer-remote", "exec")
