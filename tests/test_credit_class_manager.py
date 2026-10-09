"""Tests for services.credit_class.class_manager — methodology and protocol definitions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_credit_class_manager_create_rejects_invalid_type():
    from services.credit_class.class_manager import create_class

    conn = MagicMock()

    with pytest.raises(ValueError, match="Invalid credit_type"):
        create_class(conn, "Test Class", "IPCC", "invalid_type")


def test_credit_class_manager_create_rejects_empty_name():
    from services.credit_class.class_manager import create_class

    conn = MagicMock()

    with pytest.raises(ValueError, match="name is required"):
        create_class(conn, "", "IPCC", "carbon")


def test_credit_class_manager_create_rejects_empty_methodology():
    from services.credit_class.class_manager import create_class

    conn = MagicMock()

    with pytest.raises(ValueError, match="methodology is required"):
        create_class(conn, "Test Class", "", "carbon")


def test_credit_class_manager_create_success():
    from services.credit_class.class_manager import create_class

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"id": "cc-001"}

    result = create_class(conn, "Kokonut Carbon", "IPCC 2006", "carbon")

    assert result["id"] == "cc-001"
    assert result["name"] == "Kokonut Carbon"
    conn.execute.assert_called()


def test_credit_class_manager_get_class_returns_none():
    from services.credit_class.class_manager import get_class

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_class(conn, "cc-nonexistent")
    assert result is None


def test_credit_class_manager_list_classes_returns_list():
    from services.credit_class.class_manager import list_classes

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    result = list_classes(conn)
    assert isinstance(result, list)


def test_credit_class_manager_update_rejects_invalid_fields():
    from services.credit_class.class_manager import update_class

    conn = MagicMock()

    with pytest.raises(ValueError, match="No valid fields"):
        update_class(conn, "cc-001", invalid_field="value")


def test_credit_class_manager_update_rejects_invalid_status():
    from services.credit_class.class_manager import update_class

    conn = MagicMock()

    with pytest.raises(ValueError, match="Invalid status"):
        update_class(conn, "cc-001", status="bogus")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
