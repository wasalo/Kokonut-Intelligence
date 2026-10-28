"""Regression coverage for P0 consent and public-visibility gates."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "schemas/postgres/298_consent_privacy_p0.sql").read_text()
PERMISSIONS = (ROOT / "config/directus/permissions.sql").read_text()


def test_consent_matching_requires_exact_recipient_party():
    assert "requested_recipient_party_id UUID\n" in MIGRATION
    assert "c.recipient_party_id IS NOT DISTINCT FROM requested_recipient_party_id" in MIGRATION
    assert "c.recipient_party_id IS NULL OR" not in MIGRATION


def test_public_feedback_requires_identified_party_and_consent():
    assert "WHERE sf.party_id IS NOT NULL" in MIGRATION
    assert "stakeholder_has_effective_consent(" in MIGRATION
    assert "sf.party_id IS NULL OR" not in MIGRATION


def test_public_projections_fail_closed_without_public_safe_marker():
    assert "dsp.metadata->>'privacy' = 'public_summary'" in MIGRATION
    assert "e.metadata->>'privacy' = 'public_summary'" in MIGRATION
    assert "ws.metadata->>'privacy' = 'public_summary'" in MIGRATION
    assert "e.status = 'resolved'" in MIGRATION


def test_analyst_feedback_permission_is_public_safe_only():
    assert "party_id,feedback_type" in PERMISSIONS
    assert '"is_public":{"_eq":true}' in PERMISSIONS
    assert '"consent_given":{"_eq":true}' in PERMISSIONS
    assert '"party_id":{"_nnull":true}' in PERMISSIONS

    public_fields = (
        "id,location_id,farm_id,feedback_type,stakeholder_group,feedback_date,"
        "sentiment,themes,public_summary,evidence_maturity"
    )
    inserted = re.search(
        r"\('stakeholder_feedback', 'read', '([^']+)', '\{\}', '([^']+)', "
        r"'b1000000-0000-0000-0000-000000000005'\)",
        PERMISSIONS,
    )
    assert inserted is not None
    assert inserted.group(2) == public_fields

    updated = re.search(
        r"UPDATE directus_permissions\s+SET permissions = '([^']+)',\s+"
        r"fields = '([^']+)'\s+WHERE policy = 'b1000000-0000-0000-0000-000000000005'\s+"
        r"AND collection = 'stakeholder_feedback'\s+AND action = 'read';",
        PERMISSIONS,
    )
    assert updated is not None
    assert updated.group(2) == public_fields

    for private_field in (
        "feedback_text",
        "stakeholder_name",
        "feedback_audio_cid",
        "harms_or_unintended_consequences",
        "consent_notes",
        "source_raw",
        "party_id",
    ):
        assert private_field not in updated.group(2)
