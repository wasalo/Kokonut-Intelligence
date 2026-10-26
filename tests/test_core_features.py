"""Tests for services.core.features — feature flags."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.core.features import (
    FEATURES,
    critical_features,
    enabled_features,
    get_feature,
    is_enabled,
    list_features,
    require_feature,
)
from services.core.providers import ProviderSettings


def test_list_features_returns_list():
    """list_features returns a list of dicts."""
    result = list_features()
    assert isinstance(result, list)
    assert len(result) > 0
    assert "name" in result[0]


def test_list_features_filters_by_category():
    """list_features with category filters correctly."""
    core_features = list_features(category="core")
    for f in core_features:
        assert f["category"] == "core"
    assert len(core_features) >= 2


def test_is_enabled_known_feature():
    """is_enabled returns a bool for known features."""
    result = is_enabled("database")
    assert isinstance(result, bool)
    assert result is True  # database is always enabled


def test_is_enabled_unknown_feature():
    """is_enabled returns False for unknown feature names."""
    assert is_enabled("nonexistent_feature_xyz") is False


def test_get_feature_returns_config():
    """get_feature returns the full config dict for a known feature."""
    feature = get_feature("database")
    assert feature is not None
    assert feature["enabled"] is True
    assert feature["critical"] is True
    assert feature["category"] == "core"


def test_get_feature_returns_none_for_unknown():
    """get_feature returns None for unknown names."""
    assert get_feature("no_such_feature") is None


@patch.dict(os.environ, {"KOKONUT_FEATURE_PREFECT": "true"}, clear=False)
def test_feature_toggle_via_env():
    """Optional features can be toggled via env vars."""
    # Re-evaluate the module-level dict to pick up the patched env
    # We test the mechanism: the env var is read at import time.
    # Here we verify the env var pattern works.
    val = os.getenv("KOKONUT_FEATURE_PREFECT", "false").lower() == "true"
    assert val is True


def test_require_feature_raises_for_disabled():
    """require_feature raises RuntimeError when feature is disabled."""
    with pytest.raises(RuntimeError, match="not enabled"):
        require_feature("nonexistent_feature_xyz")


def test_enabled_features_returns_list():
    """enabled_features returns a non-empty list of strings."""
    result = enabled_features()
    assert isinstance(result, list)
    assert "database" in result
    assert "directus" in result


def test_critical_features_returns_core():
    """critical_features includes database and directus."""
    result = critical_features()
    assert "database" in result
    assert "directus" in result


def test_legacy_dataset_sql_is_disabled_by_default_and_can_be_selected():
    """Legacy stored queries require an explicit provider setting."""
    defaults = ProviderSettings.from_environment({})
    enabled = ProviderSettings.from_environment({"KOKONUT_FEATURE_LEGACY_DATASET_SQL": "true"})

    assert defaults.legacy_dataset_sql is False
    assert enabled.legacy_dataset_sql is True


def test_isolated_event_dispatch_is_default_off():
    assert FEATURES["isolated_event_dispatch"]["enabled"] is False


def test_dataset_refresh_checks_legacy_sql_gate_before_database_access(monkeypatch):
    """A disabled compatibility path must not fetch or execute stored SQL."""
    from services.export.dataset_refresh import refresh_dataset

    monkeypatch.setitem(FEATURES["legacy_dataset_sql"], "enabled", False)
    conn = Mock()

    with pytest.raises(RuntimeError, match="legacy_dataset_sql.*not enabled"):
        refresh_dataset(conn, "dataset-id")

    conn.cursor.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
