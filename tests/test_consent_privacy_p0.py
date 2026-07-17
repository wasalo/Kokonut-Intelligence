"""Regression coverage for P0 consent and public-visibility gates."""

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
