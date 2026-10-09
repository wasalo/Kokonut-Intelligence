"""Regression checks for Directus tenant-scoped permission repair."""

from pathlib import Path


PERMISSIONS = Path("config/directus/permissions.sql")


def test_staff_permission_repair_adds_location_scope() -> None:
    text = PERMISSIONS.read_text()
    assert "Tenant-scope correction" in text
    assert "'$CURRENT_USER.location_id'" in text
    assert "FOREACH policy_id" in text


def test_create_permissions_validate_location_scope() -> None:
    text = PERMISSIONS.read_text()
    assert "SET validation = '{\"location_id\":{\"_eq\":\"$CURRENT_USER.location_id\"}}'::json" in text
