"""Abundance Protocol tests."""

import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCHEMAS = {
    "estimates": Path("schemas/postgres/086_abundance_estimates.sql"),
    "validation": Path("schemas/postgres/087_abundance_validation.sql"),
    "periodic": Path("schemas/postgres/088_abundance_periodic.sql"),
    "economics": Path("schemas/postgres/089_abundance_economics.sql"),
}

SERVICES = {
    "estimates": Path("services/abundance/estimates.py"),
    "validation": Path("services/abundance/validation.py"),
    "periodic": Path("services/abundance/periodic.py"),
    "economics": Path("services/abundance/economics.py"),
}


# --- Phase 1: Estimates ---

def test_estimate_schema_exists():
    assert SCHEMAS["estimates"].exists()

def test_estimate_has_core_tables():
    content = SCHEMAS["estimates"].read_text()
    for table in ["impact_estimate_post", "estimate_category_assignment", "waiting_list_entry", "expertise_category", "category_relatedness", "category_graft"]:
        assert table in content

def test_estimate_has_status_constraint():
    content = SCHEMAS["estimates"].read_text()
    assert "chk_eep_status" in content
    assert "waiting_list" in content
    assert "validating" in content

def test_estimate_service_exists():
    assert SERVICES["estimates"].exists()

def test_estimate_service_has_create():
    from services.abundance.estimates import create_estimate_post
    assert callable(create_estimate_post)

def test_estimate_service_has_sort():
    from services.abundance.estimates import sort_waiting_list
    assert callable(sort_waiting_list)

def test_estimate_service_has_graft():
    from services.abundance.estimates import graft_category
    assert callable(graft_category)

def test_estimate_fee_computation():
    from services.abundance.estimates import compute_validation_fee
    fee = compute_validation_fee(1000, "medium", 500)
    assert fee > 0
    assert compute_validation_fee(100, "low", 100) < compute_validation_fee(100, "high", 100)

def test_expertise_category_has_relatedness():
    content = SCHEMAS["estimates"].read_text()
    assert "category_relatedness" in content
    assert "relatedness_coefficient" in content


# --- Phase 2: Validation ---

def test_validation_schema_exists():
    assert SCHEMAS["validation"].exists()

def test_validation_has_core_tables():
    content = SCHEMAS["validation"].read_text()
    for table in ["validation_round", "validator_selection", "validator_review", "quadratic_vote", "validator_compensation"]:
        assert table in content

def test_validation_has_3_tiers():
    content = SCHEMAS["validation"].read_text()
    assert "tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3))" in content

def test_validation_has_commit_reveal():
    content = SCHEMAS["validation"].read_text()
    assert "commit_hash" in content
    assert "committing" in content
    assert "revealing" in content

def test_validation_service_exists():
    assert SERVICES["validation"].exists()

def test_validation_has_select():
    from services.abundance.validation import select_validators
    assert callable(select_validators)

def test_validation_has_review():
    from services.abundance.validation import cast_review
    assert callable(cast_review)

def test_validation_has_qv():
    from services.abundance.validation import cast_qv_vote
    assert callable(cast_qv_vote)

def test_validation_has_results():
    from services.abundance.validation import compute_round_results
    assert callable(compute_round_results)

def test_validation_has_compensation():
    from services.abundance.validation import assign_compensation
    assert callable(assign_compensation)

def test_qv_sqrt_weight():
    from services.abundance.validation import cast_qv_vote

    cursor = MagicMock()
    cursor.fetchone.return_value = ("vote-1",)
    conn = MagicMock()
    conn.cursor.return_value = cursor

    cast_qv_vote(conn, "evaluator-1", "review-1", 0.25)

    vote_params = cursor.execute.call_args.args[1]
    assert vote_params[4] == 0.5


# --- Phase 3: Periodic ---

def test_periodic_schema_exists():
    assert SCHEMAS["periodic"].exists()

def test_periodic_has_core_tables():
    content = SCHEMAS["periodic"].read_text()
    for table in ["periodic_validation", "realized_impact_record", "impact_deviation", "relatedness_coefficient"]:
        assert table in content

def test_periodic_has_deviation():
    content = SCHEMAS["periodic"].read_text()
    assert "deviation_pct" in content
    assert "is_significant" in content

def test_periodic_service_exists():
    assert SERVICES["periodic"].exists()

def test_periodic_has_create():
    from services.abundance.periodic import create_periodic_validation
    assert callable(create_periodic_validation)

def test_periodic_has_record():
    from services.abundance.periodic import record_realized_impact
    assert callable(record_realized_impact)

def test_periodic_service_has_deviation_calculation():
    from services.abundance.periodic import compute_impact_deviation
    assert callable(compute_impact_deviation)

def test_periodic_has_relatedness():
    from services.abundance.periodic import update_relatedness_coefficients
    assert callable(update_relatedness_coefficients)


# --- Phase 4: Economics ---

def test_economics_schema_exists():
    assert SCHEMAS["economics"].exists()

def test_economics_has_core_tables():
    content = SCHEMAS["economics"].read_text()
    for table in ["coin_inflation_event", "inflation_schedule", "validator_compensation_detail", "incentive_alignment_log", "funding_request", "funding_bid", "fund_distribution"]:
        assert table in content

def test_economics_has_incentive_alignment():
    content = SCHEMAS["economics"].read_text()
    assert "incentive_alignment_log" in content
    assert "accuracy_bonus" in content
    assert "overestimate_penalty" in content

def test_economics_service_exists():
    assert SERVICES["economics"].exists()

def test_economics_has_compensation():
    from services.abundance.economics import compute_compensation
    assert callable(compute_compensation)

def test_economics_has_issue_coins():
    from services.abundance.economics import issue_coins
    assert callable(issue_coins)

def test_economics_has_funding():
    from services.abundance.economics import create_funding_request
    assert callable(create_funding_request)

def test_economics_has_bid():
    from services.abundance.economics import submit_bid
    assert callable(submit_bid)

def test_economics_has_distribution():
    from services.abundance.economics import compute_fund_distribution
    assert callable(compute_fund_distribution)

def test_economics_has_value_preservation():
    from services.abundance.economics import check_value_preservation
    assert callable(check_value_preservation)

def test_economics_has_alignment_log():
    from services.abundance.economics import log_incentive_alignment
    assert callable(log_incentive_alignment)


# --- Cross-cutting ---

def test_all_schemas_cover_11_gaps():
    """Verify all 11 gaps are covered across the 4 schema files."""
    all_content = " ".join(s.read_text() for s in SCHEMAS.values())
    gaps = [
        "impact_estimate_post",      # Impact Estimate Posts
        "waiting_list_entry",        # Waiting List Sorting
        "category_graft",           # Category Grafting
        "validation_round",         # 3-Tier Validation
        "validator_selection",      # Random Validator Selection
        "quadratic_vote",          # Quadratic Voting
        "category_relatedness",    # Relatedness Coefficients
        "coin_inflation_event",    # Coin Inflation
        "incentive_alignment_log", # Incentive Alignment
        "funding_request",         # Funding Requests
        "periodic_validation",     # Periodic Validation
    ]
    for gap in gaps:
        assert gap in all_content, f"Missing table for gap: {gap}"

def test_package_init_exists():
    assert Path("services/abundance/__init__.py").exists()


# --- Governance and issuance guards ---

def test_select_validators_applies_category_expertise_threshold():
    from services.abundance.validation import select_validators

    cursor = MagicMock()
    cursor.fetchall.side_effect = [
        [
            {"category_id": "soil-id", "category_name": "Soil Health", "relative_impact_score": 5.0},
            {"category_id": "water-id", "category_name": "Water Access", "relative_impact_score": 2.5},
        ],
        [
            {
                "id": "soil-evaluator",
                "display_name": "Soil Expert",
                "trust_score": 0.99,
                "evaluator_type": "expert",
                "domain_expertise": ["soil health"],
            },
            {
                "id": "water-evaluator",
                "display_name": "Water Expert",
                "trust_score": 0.99,
                "evaluator_type": "expert",
                "domain_expertise": ["Water Access"],
            },
        ],
    ]
    cursor.fetchone.return_value = ("round-1",)
    conn = MagicMock()
    conn.cursor.return_value = cursor

    round_id = select_validators(conn, "estimate-1", tier=1, required_expertise=4.5, slot_count=1)

    assert round_id == "round-1"
    selection_params = cursor.execute.call_args_list[3].args[1]
    assert selection_params[1] == "soil-evaluator"
    assert selection_params[4] == 5.0
    conn.commit.assert_called_once()


def test_select_validators_fails_closed_when_no_evaluator_matches_expertise():
    from services.abundance.validation import select_validators

    cursor = MagicMock()
    cursor.fetchall.side_effect = [
        [{"category_id": "soil-id", "category_name": "Soil Health", "relative_impact_score": 5.0}],
        [{"id": "water-evaluator", "trust_score": 0.99, "domain_expertise": ["Water Access"]}],
    ]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    assert select_validators(conn, "estimate-1", tier=1, required_expertise=5.0) is None
    assert cursor.execute.call_count == 2
    conn.commit.assert_not_called()


@pytest.mark.parametrize("tier,required,slots", [(0, 0, 1), (4, 0, 1), (1, -1, 1), (1, math.nan, 1), (1, 0, 0)])
def test_select_validators_rejects_invalid_scope_before_database_access(tier, required, slots):
    from services.abundance.validation import select_validators

    conn = MagicMock()
    with pytest.raises(ValueError):
        select_validators(conn, "estimate-1", tier, required, slots)
    conn.cursor.assert_not_called()

def test_cast_review_rejects_unselected_validator_before_insert():
    from services.abundance.validation import cast_review

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = None
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with pytest.raises(ValueError, match="not selected and revealed"):
        cast_review(conn, "evaluator-1", "round-1", 0.8, 5.0)

    assert cursor.execute.call_count == 1
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()


def test_cast_review_uses_round_tier_for_selected_revealed_validator():
    from services.abundance.validation import cast_review

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [{"tier": 2}, ("review-1",)]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    review_id = cast_review(conn, "evaluator-1", "round-1", 0.8, 5.0)

    assert review_id == "review-1"
    guard_query = cursor.execute.call_args_list[0].args[0]
    assert "vs.status = 'revealed'" in guard_query
    assert "FOR UPDATE OF vs" in guard_query
    insert_params = cursor.execute.call_args_list[1].args[1]
    assert insert_params[2] == 2
    conn.commit.assert_called_once()


@pytest.mark.parametrize("weight", [0, -0.1, 1.01, math.nan, math.inf, -math.inf, True])
def test_cast_qv_vote_rejects_invalid_weight_before_database_access(weight):
    from services.abundance.validation import cast_qv_vote

    conn = MagicMock()
    with pytest.raises(ValueError, match="vote_weight"):
        cast_qv_vote(conn, "evaluator-1", "review-1", weight)
    conn.cursor.assert_not_called()


def test_cast_qv_vote_rejects_unsupported_vote_type_before_database_access():
    from services.abundance.validation import cast_qv_vote

    conn = MagicMock()
    with pytest.raises(ValueError, match="vote_type"):
        cast_qv_vote(conn, "evaluator-1", "review-1", 0.5, vote_type="approve")
    conn.cursor.assert_not_called()


@pytest.mark.parametrize("impact", [0, -1, math.nan, math.inf, -math.inf, True])
def test_issue_coins_rejects_invalid_impact_before_database_access(impact):
    from services.abundance.economics import issue_coins

    conn = MagicMock()
    with pytest.raises(ValueError, match="impact_score"):
        issue_coins(conn, "validation-1", impact, "0x1234")
    conn.cursor.assert_not_called()


def test_issue_coins_requires_validated_periodic_impact_before_insert():
    from services.abundance.economics import issue_coins

    cursor = MagicMock()
    cursor.fetchone.return_value = ("collecting_data",)
    conn = MagicMock()
    conn.cursor.return_value = cursor

    with pytest.raises(ValueError, match="validated periodic impact"):
        issue_coins(conn, "validation-1", 5.0, "0x1234")

    assert cursor.execute.call_count == 1
    assert "FOR UPDATE" in cursor.execute.call_args.args[0]
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()


def test_issue_coins_writes_only_after_periodic_validation_is_validated():
    from services.abundance.economics import issue_coins

    cursor = MagicMock()
    cursor.fetchone.side_effect = [("validated",), ("event-1",)]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    event_id = issue_coins(conn, "validation-1", 5.0, "0x1234")

    assert event_id == "event-1"
    assert cursor.execute.call_count == 2
    assert "INSERT INTO coin_inflation_event" in cursor.execute.call_args_list[1].args[0]
    conn.commit.assert_called_once()
