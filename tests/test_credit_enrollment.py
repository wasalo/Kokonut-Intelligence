"""Tests for services.credit_class.enrollment — apply → approve/reject workflow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_credit_enrollment_apply_creates_new():
    from services.credit_class.enrollment import apply_to_class

    conn = MagicMock()
    # First call: existing check returns None; second call: INSERT returns id
    conn.execute.return_value.mappings.return_value.first.side_effect = [
        None,  # existing enrollment check
        {"id": "enr-new"},  # INSERT RETURNING id
    ]

    result = apply_to_class(conn, "loc-001", "cc-001")

    assert result["status"] == "applied"
    assert result["id"] == "enr-new"


def test_credit_enrollment_apply_rejects_duplicate_applied():
    from services.credit_class.enrollment import apply_to_class

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": "enr-001",
        "status": "applied",
    }

    with pytest.raises(ValueError, match="already exists"):
        apply_to_class(conn, "loc-001", "cc-001")


def test_credit_enrollment_apply_rejects_already_enrolled():
    from services.credit_class.enrollment import apply_to_class

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": "enr-001",
        "status": "accepted",
    }

    with pytest.raises(ValueError, match="already enrolled"):
        apply_to_class(conn, "loc-001", "cc-001")


def test_credit_enrollment_evaluate_rejects_invalid_status():
    from services.credit_class.enrollment import evaluate_application

    conn = MagicMock()

    with pytest.raises(ValueError, match="Invalid status"):
        evaluate_application(conn, "enr-001", "0xIssuer", "bogus_status")


def test_credit_enrollment_evaluate_rejects_invalid_transition():
    from services.credit_class.enrollment import evaluate_application

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": "enr-001",
        "status": "rejected",
    }

    with pytest.raises(ValueError, match="Cannot transition"):
        evaluate_application(conn, "enr-001", "0xIssuer", "accepted")


def test_credit_enrollment_evaluate_accepts_valid_transition():
    from services.credit_class.enrollment import evaluate_application

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": "enr-001",
        "status": "applied",
    }

    result = evaluate_application(conn, "enr-001", "0xIssuer", "accepted")

    assert result["old_status"] == "applied"
    assert result["new_status"] == "accepted"


def test_credit_enrollment_terminate_rejects_non_accepted():
    from services.credit_class.enrollment import terminate_enrollment

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "status": "applied",
    }

    with pytest.raises(ValueError, match="Only accepted"):
        terminate_enrollment(conn, "enr-001", "0xAdmin")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
