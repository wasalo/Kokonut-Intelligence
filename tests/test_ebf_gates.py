"""EBF evidence maturity gate tests."""

from pathlib import Path

from services.scoring.gates import score_publication_gate, scorecard_publication_gate


SCHEMA = Path("schemas/postgres/032_ebf_scorecard.sql")


def test_public_scorecard_requires_level4_and_public_claim_allowed() -> None:
    text = SCHEMA.read_text().lower()
    assert "chk_ebf_scorecard_public_maturity" in text
    assert "evidence_maturity_level >= 4" in text
    assert "public_claim_allowed = true" in text


def test_public_scores_require_evidence_links_in_view() -> None:
    text = SCHEMA.read_text().lower()
    assert "select 1 from ebf_score_evidence" in text
    assert "es.public_score_allowed = true" in text


def test_service_publication_gates_match_maturity_rules() -> None:
    assert score_publication_gate("soil_health", 4, True)[0] is True
    assert score_publication_gate("soil_health", 3, True)[0] is False
    assert score_publication_gate("soil_health", 4, False)[0] is False
    claim = {
        "claim_category": "carbon",
        "claim_type": "third_party_verified_claim",
        "evidence_maturity": 6,
        "status": "published",
        "external_verifier": "External MRV reviewer",
        "methodology_ref": "IPCC 2006 GHG Guidelines",
    }
    assert score_publication_gate("carbon_sequestration", 5, True, claim)[0] is False
    assert score_publication_gate("carbon_sequestration", 6, True, claim)[0] is True
    allowed, reasons = scorecard_publication_gate(4, [score_publication_gate("soil_health", 4, True)])
    assert allowed is True
    assert reasons == []


if __name__ == "__main__":
    test_public_scorecard_requires_level4_and_public_claim_allowed()
    test_public_scores_require_evidence_links_in_view()
    test_service_publication_gates_match_maturity_rules()
