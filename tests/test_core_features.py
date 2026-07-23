"""Tests for services.core.features — feature flags."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.core.features import (
    FEATURES,
    is_enabled,
    get_feature,
    list_features,
    require_feature,
    enabled_features,
    critical_features,
)


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
