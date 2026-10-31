"""Migration-backed projection contracts for private stakeholder views."""

from datetime import datetime, timezone
from uuid import UUID

from services.analytics import stakeholder_identity_resolution as identity_resolution
from services.analytics import stakeholder_trust

TRUST_PROFILE_COLUMNS = (
    "party_id",
    "display_name",
    "party_type",
    "evidence_count",
    "supporting_evidence_count",
    "contradicting_evidence_count",
    "contested_evidence_count",
    "open_risk_count",
    "latest_evidence_at",
    "earliest_evidence_at",
    "latest_snapshot_at",
    "latest_uncertainty",
    "interpretation",
)

TRUST_TIMELINE_COLUMNS = (
    "id",
    "subject_party_id",
    "subject_name",
    "relationship_party_id",
    "relationship_name",
    "dimension",
    "direction",
    "source_type",
    "source_id",
    "source_label",
    "summary",
    "observed_at",
    "expires_at",
    "confidence",
    "uncertainty",
    "status",
    "correction_status",
    "appeal_status",
)

RESOLUTION_QUEUE_COLUMNS = (
    "resolution_case_id",
    "source_system",
    "source_type",
    "source_id",
    "candidate_party_id",
    "candidate_name",
    "proposed_party_type",
    "match_method",
    "confidence",
    "status",
    "created_at",
    "reviewed_at",
)

VERIFIED_SOURCE_LINK_COLUMNS = (
    "source_system",
    "source_id",
    "identifier_type",
    "identifier_value",
    "party_id",
    "party_type",
    "display_name",
    "verification_status",
    "confidence",
    "reviewed_by",
    "reviewed_at",
)


class _Cursor:
    def __init__(self, *, row=None, rows=()):
        self.row = row
        self.rows = list(rows)
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, *, row=None, rows=()):
        self.cursor_instance = _Cursor(row=row, rows=rows)

    def cursor(self, **_kwargs):
        return self.cursor_instance


def _assert_payload(row, result, columns):
    assert list(row) == list(columns)
    assert list(result) == list(columns)
    assert result == row


def test_trust_profile_projection_matches_migration_222_and_payload():
    party_id = UUID("d0000000-0000-0000-0000-000000000001")
    latest = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    row = {
        "party_id": party_id,
        "display_name": "Kokonut Network",
        "party_type": "organization",
        "evidence_count": 3,
        "supporting_evidence_count": 2,
        "contradicting_evidence_count": 1,
        "contested_evidence_count": 0,
        "open_risk_count": 1,
        "latest_evidence_at": latest,
        "earliest_evidence_at": latest,
        "latest_snapshot_at": latest,
        "latest_uncertainty": 0.2,
        "interpretation": "Inspect dimensions and evidence; no universal reputation score.",
    }
    conn = _Connection(row=row)

    result = stakeholder_trust.profile(conn, str(party_id))

    projection = ", ".join(TRUST_PROFILE_COLUMNS)
    assert conn.cursor_instance.executions == [
        (
            f"SELECT {projection} FROM v_party_trust_profile "
            "WHERE party_id = %s::uuid",
            (str(party_id),),
        )
    ]
    _assert_payload(row, result, TRUST_PROFILE_COLUMNS)


def test_trust_timeline_projection_matches_migration_222_and_payload():
    party_id = UUID("d0000000-0000-0000-0000-000000000002")
    evidence_id = UUID("d0000000-0000-0000-0000-000000000003")
    observed_at = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    row = {
        "id": evidence_id,
        "subject_party_id": party_id,
        "subject_name": "Kokonut Network",
        "relationship_party_id": None,
        "relationship_name": None,
        "dimension": "payment",
        "direction": "supporting",
        "source_type": "financial_transaction",
        "source_id": "transaction-123",
        "source_label": "Payment record",
        "summary": "Payment settled within agreed terms",
        "observed_at": observed_at,
        "expires_at": None,
        "confidence": 0.9,
        "uncertainty": 0.1,
        "status": "active",
        "correction_status": "none",
        "appeal_status": "none",
    }
    conn = _Connection(rows=[row])

    result = stakeholder_trust.evidence_timeline(conn, str(party_id))

    projection = ", ".join(TRUST_TIMELINE_COLUMNS)
    assert conn.cursor_instance.executions == [
        (
            f"SELECT {projection} FROM v_party_trust_evidence_timeline "
            "WHERE subject_party_id = %s::uuid ORDER BY observed_at DESC",
            (str(party_id),),
        )
    ]
    assert len(result) == 1
    _assert_payload(row, result[0], TRUST_TIMELINE_COLUMNS)


def test_identity_resolution_queue_projection_matches_migration_227_and_payload():
    candidate_party_id = UUID("d0000000-0000-0000-0000-000000000004")
    created_at = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
    row = {
        "resolution_case_id": UUID("d0000000-0000-0000-0000-000000000005"),
        "source_system": "legacy-import",
        "source_type": "farmer_profile",
        "source_id": "profile-123",
        "candidate_party_id": candidate_party_id,
        "candidate_name": "Community member",
        "proposed_party_type": "person",
        "match_method": "manual",
        "confidence": 0.8,
        "status": "proposed",
        "created_at": created_at,
        "reviewed_at": None,
    }
    conn = _Connection(rows=[row])

    result = identity_resolution.resolution_queue(conn)

    projection = ", ".join(RESOLUTION_QUEUE_COLUMNS)
    assert conn.cursor_instance.executions == [
        (f"SELECT {projection} FROM v_party_resolution_queue ORDER BY created_at", None)
    ]
    assert len(result) == 1
    _assert_payload(row, result[0], RESOLUTION_QUEUE_COLUMNS)


def test_verified_source_link_projection_matches_migration_227_and_payload():
    party_id = UUID("d0000000-0000-0000-0000-000000000006")
    reviewer_id = UUID("d0000000-0000-0000-0000-000000000007")
    reviewed_at = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    row = {
        "source_system": "legacy-import",
        "source_id": "profile-123",
        "identifier_type": "farmer_profile",
        "identifier_value": "F-123",
        "party_id": party_id,
        "party_type": "person",
        "display_name": "Community member",
        "verification_status": "verified",
        "confidence": 1.0,
        "reviewed_by": reviewer_id,
        "reviewed_at": reviewed_at,
    }
    conn = _Connection(row=row)

    result = identity_resolution.verified_party_for_source(
        conn, "legacy-import", "farmer_profile", "profile-123"
    )

    projection = ", ".join(VERIFIED_SOURCE_LINK_COLUMNS)
    assert conn.cursor_instance.executions == [
        (
            f"SELECT {projection} FROM v_canonical_party_source_links "
            "WHERE source_system = %s AND identifier_type = %s AND source_id = %s",
            ("legacy-import", "farmer_profile", "profile-123"),
        )
    ]
    _assert_payload(row, result, VERIFIED_SOURCE_LINK_COLUMNS)
