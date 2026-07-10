"""Evaluator registry and attester reputation tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/079_web_of_trust.sql")


def test_schema_file_exists() -> None:
    assert SCHEMA.exists()


def test_schema_has_evaluator_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS evaluator" in content


def test_schema_has_reputation_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS attester_reputation" in content


def test_schema_has_reference_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS attestation_reference" in content


def test_schema_has_evaluator_type_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_evaluator_type" in content
    assert "citizen" in content
    assert "professional" in content
    assert "expert" in content
    assert "funder" in content
    assert "self" in content


def test_schema_supports_wallet_did_ens() -> None:
    content = SCHEMA.read_text()
    assert "wallet_address" in content
    assert "did" in content
    assert "ens_name" in content


def test_schema_has_trust_score_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_evaluator_trust" in content
    assert "trust_score >= 0 AND trust_score <= 1" in content


def test_schema_has_reputation_event_types() -> None:
    content = SCHEMA.read_text()
    assert "chk_reputation_event" in content
    assert "attestation_made" in content
    assert "attestation_verified" in content
    assert "attestation_revoked" in content


def test_schema_has_reference_types() -> None:
    content = SCHEMA.read_text()
    assert "chk_attref_type" in content
    assert "supports" in content
    assert "contradicts" in content
    assert "supersedes" in content


def test_schema_has_public_view() -> None:
    content = SCHEMA.read_text()
    assert "v_public_evaluator_directory" in content


def test_evaluator_service_exists() -> None:
    assert Path("services/scoring/evaluator.py").exists()


def test_service_has_register_evaluator() -> None:
    from services.scoring.evaluator import register_evaluator
    assert callable(register_evaluator)


def test_service_has_compute_trust_score() -> None:
    from services.scoring.evaluator import compute_trust_score
    assert callable(compute_trust_score)


def test_service_has_update_reputation() -> None:
    from services.scoring.evaluator import update_reputation
    assert callable(update_reputation)


def test_service_has_get_evaluator_profile() -> None:
    from services.scoring.evaluator import get_evaluator_profile
    assert callable(get_evaluator_profile)


def test_service_has_list_evaluators() -> None:
    from services.scoring.evaluator import list_evaluators
    assert callable(list_evaluators)


def test_service_has_link_attestations() -> None:
    from services.scoring.evaluator import link_attestations
    assert callable(link_attestations)


def test_service_has_get_attestation_references() -> None:
    from services.scoring.evaluator import get_attestation_references
    assert callable(get_attestation_references)


def test_service_has_reputation_weights() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "ACCURACY_WEIGHT" in content
    assert "LONGEVITY_WEIGHT" in content
    assert "DOMAIN_WEIGHT" in content
    assert "RECENCY_WEIGHT" in content


def test_service_has_decay_rate() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "DECAY_RATE" in content
    assert "0.01" in content


def test_service_uses_logging() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "get_logger" in content


def test_trust_score_formula() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "accuracy * ACCURACY_WEIGHT" in content
    assert "longevity * LONGEVITY_WEIGHT" in content
    assert "domain_score * DOMAIN_WEIGHT" in content
    assert "recency * RECENCY_WEIGHT" in content


def test_recency_uses_exponential_decay() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "math.exp" in content
    assert "DECAY_RATE" in content


def test_register_supports_all_identity_types() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "wallet_address" in content
    assert "did" in content
    assert "ens_name" in content


def test_link_attestations_has_upsert() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "ON CONFLICT" in content
    assert "source_attestation_id, target_attestation_id, reference_type" in content


def test_evaluator_profile_includes_reputation_history() -> None:
    content = Path("services/scoring/evaluator.py").read_text()
    assert "reputation_history" in content
    assert "attester_reputation" in content


def test_public_view_filters_by_trust() -> None:
    content = SCHEMA.read_text()
    assert "trust_score >= 0.3" in content
