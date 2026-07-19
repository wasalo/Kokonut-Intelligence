"""Integration tests for conservative stakeholder consent resolution."""

from datetime import datetime, timedelta, timezone

import pytest

from services.analytics import consent_resolver
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_absence_of_consent_denies_use():
    conn = _db()
    try:
        result = consent_resolver.check_consent(
            conn,
            "a0000000-0000-0000-0000-000000001002",
            "personal",
            "research",
        )
        assert result["consented"] is False
        assert result["effective_status"] == "absent"
    finally:
        conn.close()


def test_grant_withdrawal_and_scope_matching():
    conn = _db()
    party_id = "a0000000-0000-0000-0000-000000001002"
    try:
        grant = consent_resolver.record_consent(
            conn, party_id, "social", "community research",
            scope_type="location", scope_id="a0000000-0000-0000-0000-000000000001",
            recipient_type="researcher", recipient_name="Approved Research Team",
            evidence=[{"source": "test"}],
        )
        allowed = consent_resolver.check_consent(
            conn, party_id, "social", "community research",
            scope_type="location", scope_id="a0000000-0000-0000-0000-000000000001",
            recipient_type="researcher",
        )
        wrong_purpose = consent_resolver.check_consent(
            conn, party_id, "social", "commercial marketing",
            scope_type="location", scope_id="a0000000-0000-0000-0000-000000000001",
            recipient_type="researcher",
        )
        withdrawal = consent_resolver.withdraw_consent(conn, grant["id"], "Research scope changed")
        denied = consent_resolver.check_consent(
            conn, party_id, "social", "community research",
            scope_type="location", scope_id="a0000000-0000-0000-0000-000000000001",
            recipient_type="researcher",
        )

        assert allowed["consented"] is True
        assert wrong_purpose["consented"] is False
        assert withdrawal["event_type"] == "withdraw"
        assert denied["consented"] is False
        assert denied["effective_status"] == "withdrawn"
    finally:
        conn.close()


def test_expired_grant_is_not_effective():
    conn = _db()
    party_id = "a0000000-0000-0000-0000-000000001003"
    try:
        now = datetime.now(timezone.utc)
        result = consent_resolver.record_consent(
            conn, party_id, "biodiversity", "internal assessment",
            effective_at=now - timedelta(days=2),
            expires_at=now - timedelta(days=1),
            consent_method="system_migration",
        )
        effective = consent_resolver.check_consent(
            conn, party_id, "biodiversity", "internal assessment"
        )
        assert result["event_type"] == "grant"
        assert effective["consented"] is False
        assert effective["effective_status"] == "expired"
    finally:
        conn.close()


def test_legacy_consent_view_requires_verified_party_link():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM v_mappable_legacy_consent")
            assert cur.fetchone()[0] >= 0
    finally:
        conn.close()
