"""EBF public-safe view tests."""

from pathlib import Path


SCHEMA = Path("schemas/postgres/032_ebf_scorecard.sql")


def test_public_views_filter_to_published_registry_backed_records() -> None:
    text = SCHEMA.read_text().lower()
    assert "create or replace view v_public_ebf_scorecard" in text
    assert "esc.status = 'published'" in text
    assert "farm_registry_record" in text
    assert "fr.status in ('verified', 'published')" in text


def test_public_summary_requires_complete_seven_pillars() -> None:
    text = SCHEMA.read_text().lower()
    assert "having count(es.id) = 7" in text


def test_public_carbon_view_requires_linked_verified_impact_claim() -> None:
    text = SCHEMA.read_text().lower()
    assert "ic.id = es.impact_claim_id" in text
    assert "third_party_verified_claim" in text
    assert "external_verifier" in text
    assert "methodology_ref" in text


if __name__ == "__main__":
    test_public_views_filter_to_published_registry_backed_records()
    test_public_summary_requires_complete_seven_pillars()
    test_public_carbon_view_requires_linked_verified_impact_claim()
