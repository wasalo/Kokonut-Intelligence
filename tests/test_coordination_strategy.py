"""Coordination strategy lifecycle tests."""

from unittest.mock import MagicMock

import pytest

from services.analytics.coordination import activate_alliance, create_alliance
from services.analytics.coordination_strategy import (
    declare_conflict, record_benefit_harm_analysis, review_and_renew,
    review_benefit_harm_analysis, review_conflict_declaration,
)
from services.ingestion.base import get_db


def test_strategy_review_can_start_a_new_term():
    try:
        conn = get_db()
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")
    alliance = create_alliance("Strategy lifecycle test", "Test review and renewal", market_cycle="standard")
    try:
        declaration = declare_conflict(alliance["id"], "a0000000-0000-0000-0000-000000001000", "no_conflict", "No conflict declared")
        review_conflict_declaration(declaration["id"], "a0000000-0000-0000-0000-000000001000")
        analysis = record_benefit_harm_analysis(alliance["id"], "benefit", "Benefit and harm analysis")
        review_benefit_harm_analysis(analysis["id"], "a0000000-0000-0000-0000-000000001000")
        from services.analytics.coordination import approve_alliance
        approve_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000", "Reviewed")
        activate_alliance(alliance["id"], "a0000000-0000-0000-0000-000000001000")
        result = review_and_renew(
            alliance["id"], "2026-01-01", "2026-03-31", "a0000000-0000-0000-0000-000000001000",
            "Participation reviewed", "Benefits reviewed", "Harms reviewed", "Continue with safeguards", "continue",
        )
        assert result["recommendation"] == "continue"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM coordination_alliance WHERE id = %s::uuid", (alliance["id"],))
        conn.commit()


def test_declare_conflict_rejects_invalid_type():
    with pytest.raises(ValueError, match="declaration_type must be"):
        declare_conflict("alliance-id", "party-id", "invalid", "description")


def test_record_benefit_harm_analysis_rejects_invalid_type():
    with pytest.raises(ValueError, match="analysis_type must be"):
        record_benefit_harm_analysis("alliance-id", "invalid", "description")
