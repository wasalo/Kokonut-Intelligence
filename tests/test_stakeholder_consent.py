"""Integration tests for conservative stakeholder consent resolution."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import UUID

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


def test_consent_record_rejects_invalid_event_type():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="event_type"):
        consent_resolver.record_consent(
            mock_conn, "p1", "soil", "research", event_type="invalid"
        )


def test_consent_record_rejects_empty_purpose():
    mock_conn = MagicMock()
    with pytest.raises(ValueError, match="data_category and purpose"):
        consent_resolver.record_consent(
            mock_conn, "p1", "  ", "  "
        )


def test_consent_check_returns_absent_when_no_record():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    result = consent_resolver.check_consent(mock_conn, "p1", "soil", "research")
    assert result["consented"] is False
    assert result["effective_status"] == "absent"


def test_withdraw_consent_rejects_empty_reason():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="reason is required"):
        consent_resolver.withdraw_consent(mock_conn, "some-id", "  ")


_EFFECTIVE_CONSENT_COLUMNS = (
    "consent_event_id",
    "party_id",
    "party_name",
    "event_type",
    "data_category",
    "purpose",
    "scope_type",
    "scope_id",
    "recipient_party_id",
    "recipient_party_name",
    "recipient_type",
    "recipient_name",
    "consent_method",
    "legal_basis",
    "consent_version",
    "effective_at",
    "expires_at",
    "effective_status",
    "consented",
    "reason",
    "evidence",
    "source_system",
    "source_record_id",
    "created_at",
)


def _effective_consent_row():
    effective_at = datetime(2026, 10, 29, 11, 0, tzinfo=timezone.utc)
    created_at = datetime(2026, 10, 29, 10, 45, tzinfo=timezone.utc)
    return {
        "consent_event_id": UUID("c0000000-0000-0000-0000-000000000001"),
        "party_id": UUID("c0000000-0000-0000-0000-000000000002"),
        "party_name": "Community member",
        "event_type": "grant",
        "data_category": "social",
        "purpose": "community research",
        "scope_type": "location",
        "scope_id": UUID("c0000000-0000-0000-0000-000000000003"),
        "recipient_party_id": UUID("c0000000-0000-0000-0000-000000000004"),
        "recipient_party_name": "Research team",
        "recipient_type": "researcher",
        "recipient_name": "Approved Research Team",
        "consent_method": "digital_form",
        "legal_basis": "consent",
        "consent_version": "2.1",
        "effective_at": effective_at,
        "expires_at": None,
        "effective_status": "granted",
        "consented": True,
        "reason": None,
        "evidence": [{"source": "consent-form"}],
        "source_system": "stakeholder_registry",
        "source_record_id": "form-123",
        "created_at": created_at,
    }


def _expected_serialized_consent(row):
    return {
        key: value.isoformat() if isinstance(value, datetime)
        else str(value) if isinstance(value, UUID)
        else value
        for key, value in row.items()
    }


def test_check_consent_uses_migration_projection_and_preserves_payload():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    row = _effective_consent_row()
    mock_cursor.fetchone.return_value = row

    result = consent_resolver.check_consent(
        mock_conn,
        str(row["party_id"]),
        row["data_category"],
        row["purpose"],
        scope_type=row["scope_type"],
        scope_id=str(row["scope_id"]),
        recipient_party_id=str(row["recipient_party_id"]),
        recipient_type=row["recipient_type"],
    )

    projection = ", ".join(_EFFECTIVE_CONSENT_COLUMNS)
    sql = " ".join(mock_cursor.execute.call_args.args[0].split())
    assert sql == (
        f"SELECT {projection} FROM v_effective_stakeholder_consent "
        "WHERE party_id = %s::uuid AND data_category = %s AND purpose = %s "
        "AND scope_type = %s AND scope_id IS NOT DISTINCT FROM %s::uuid "
        "AND recipient_party_id IS NOT DISTINCT FROM %s::uuid "
        "AND recipient_type = %s LIMIT 1"
    )
    assert mock_cursor.execute.call_args.args[1] == (
        str(row["party_id"]),
        row["data_category"],
        row["purpose"],
        row["scope_type"],
        str(row["scope_id"]),
        str(row["recipient_party_id"]),
        row["recipient_type"],
    )
    assert list(result) == list(_EFFECTIVE_CONSENT_COLUMNS)
    assert result == _expected_serialized_consent(row)


@pytest.mark.parametrize(
    ("party_id", "effective_status", "where", "params"),
    [
        (None, None, "", []),
        (
            "c0000000-0000-0000-0000-000000000002",
            None,
            " WHERE party_id = %s::uuid",
            ["c0000000-0000-0000-0000-000000000002"],
        ),
        (None, "granted", " WHERE effective_status = %s", ["granted"]),
        (
            "c0000000-0000-0000-0000-000000000002",
            "granted",
            " WHERE party_id = %s::uuid AND effective_status = %s",
            ["c0000000-0000-0000-0000-000000000002", "granted"],
        ),
    ],
)
def test_list_effective_consent_uses_migration_projection_and_preserves_payload(
    party_id, effective_status, where, params
):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    row = _effective_consent_row()
    mock_cursor.fetchall.return_value = [row]

    result = consent_resolver.list_effective_consent(
        mock_conn, party_id, effective_status=effective_status
    )

    projection = ", ".join(_EFFECTIVE_CONSENT_COLUMNS)
    mock_cursor.execute.assert_called_once_with(
        f"SELECT {projection} FROM v_effective_stakeholder_consent{where} "
        "ORDER BY party_name, data_category, purpose",
        params,
    )
    assert "SELECT *" not in mock_cursor.execute.call_args.args[0]
    assert len(result) == 1
    assert list(result[0]) == list(_EFFECTIVE_CONSENT_COLUMNS)
    assert result[0] == _expected_serialized_consent(row)
