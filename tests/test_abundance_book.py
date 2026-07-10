"""Abundance Book improvements tests."""

from pathlib import Path

SCHEMAS = {
    "externalities": Path("schemas/postgres/090_externality_countermeasures.sql"),
    "superalignment": Path("schemas/postgres/091_superalignment.sql"),
    "content": Path("schemas/postgres/092_content_layer.sql"),
    "ai_evaluation": Path("schemas/postgres/093_ai_evaluation.sql"),
    "currency_stability": Path("schemas/postgres/094_currency_stability.sql"),
}

SERVICES = {
    "externalities": Path("services/abundance/externalities.py"),
    "superalignment": Path("services/abundance/superalignment.py"),
    "content": Path("services/abundance/content.py"),
    "ai_evaluation": Path("services/abundance/ai_evaluation.py"),
    "currency_stability": Path("services/abundance/currency_stability.py"),
}


# --- Component 1: Externality Countermeasures ---

def test_externality_schema_exists():
    assert SCHEMAS["externalities"].exists()

def test_externality_has_core_tables():
    content = SCHEMAS["externalities"].read_text()
    for table in ["externality_index", "externality_alert", "externality_counteraction", "externality_reduction_target"]:
        assert table in content

def test_externality_has_public_view():
    content = SCHEMAS["externalities"].read_text()
    assert "v_public_externality_summary" in content

def test_externality_service_exists():
    assert SERVICES["externalities"].exists()

def test_externality_has_compute_index():
    from services.abundance.externalities import compute_externality_index
    assert callable(compute_externality_index)

def test_externality_has_check_thresholds():
    from services.abundance.externalities import check_externality_thresholds
    assert callable(check_externality_thresholds)

def test_externality_has_counteraction():
    from services.abundance.externalities import propose_counteraction, track_counteraction_progress
    assert callable(propose_counteraction)
    assert callable(track_counteraction_progress)


# --- Component 2: Superalignment ---

def test_superalignment_schema_exists():
    assert SCHEMAS["superalignment"].exists()

def test_superalignment_has_core_tables():
    content = SCHEMAS["superalignment"].read_text()
    for table in ["ecosystem_registry", "cross_ecosystem_impact", "superalignment_score"]:
        assert table in content

def test_superalignment_service_exists():
    assert SERVICES["superalignment"].exists()

def test_superalignment_has_register():
    from services.abundance.superalignment import register_ecosystem
    assert callable(register_ecosystem)

def test_superalignment_has_propagate():
    from services.abundance.superalignment import propagate_impact
    assert callable(propagate_impact)

def test_superalignment_has_alignment_score():
    from services.abundance.superalignment import compute_alignment_score
    assert callable(compute_alignment_score)

def test_superalignment_has_detect():
    from services.abundance.superalignment import detect_adversarial_dynamics
    assert callable(detect_adversarial_dynamics)


# --- Component 3: Content ---

def test_content_schema_exists():
    assert SCHEMAS["content"].exists()

def test_content_has_core_tables():
    content = SCHEMAS["content"].read_text()
    for table in ["content_piece", "content_distribution", "sensemaking_score"]:
        assert table in content

def test_content_has_types():
    content = SCHEMAS["content"].read_text()
    assert "narrative" in content
    assert "report" in content
    assert "investigation" in content

def test_content_service_exists():
    assert SERVICES["content"].exists()

def test_content_has_generate():
    from services.abundance.content import generate_narrative
    assert callable(generate_narrative)

def test_content_has_publish():
    from services.abundance.content import publish_content
    assert callable(publish_content)

def test_content_has_sensemaking():
    from services.abundance.content import compute_sensemaking_score
    assert callable(compute_sensemaking_score)


# --- Component 4: AI Evaluation ---

def test_ai_evaluation_schema_exists():
    assert SCHEMAS["ai_evaluation"].exists()

def test_ai_evaluation_has_table():
    content = SCHEMAS["ai_evaluation"].read_text()
    assert "ai_impact_evaluation" in content
    assert "human_validator_id" in content
    assert "human_validation_result" in content

def test_ai_evaluation_has_human_in_loop():
    content = SCHEMAS["ai_evaluation"].read_text()
    assert "ai_generated" in content
    assert "pending_validation" in content
    assert "validated" in content
    assert "rejected" in content

def test_ai_evaluation_service_exists():
    assert SERVICES["ai_evaluation"].exists()

def test_ai_evaluation_has_evaluate():
    from services.abundance.ai_evaluation import evaluate_impact
    assert callable(evaluate_impact)

def test_ai_evaluation_has_validate():
    from services.abundance.ai_evaluation import validate_evaluation
    assert callable(validate_evaluation)

def test_ai_evaluation_has_confidence():
    from services.abundance.ai_evaluation import compute_evaluation_confidence
    assert callable(compute_evaluation_confidence)


# --- Component 5: Currency Stability ---

def test_currency_stability_schema_exists():
    assert SCHEMAS["currency_stability"].exists()

def test_currency_stability_has_core_tables():
    content = SCHEMAS["currency_stability"].read_text()
    for table in ["value_stability_metric", "inflation_adjustment"]:
        assert table in content

def test_currency_stability_has_public_view():
    content = SCHEMAS["currency_stability"].read_text()
    assert "v_currency_stability_summary" in content

def test_currency_stability_service_exists():
    assert SERVICES["currency_stability"].exists()

def test_currency_has_stability():
    from services.abundance.currency_stability import compute_value_stability
    assert callable(compute_value_stability)

def test_currency_has_adjustment():
    from services.abundance.currency_stability import suggest_inflation_adjustment
    assert callable(suggest_inflation_adjustment)

def test_currency_has_supply():
    from services.abundance.currency_stability import track_supply_metrics
    assert callable(track_supply_metrics)

def test_currency_has_capacity():
    from services.abundance.currency_stability import compute_economic_capacity
    assert callable(compute_economic_capacity)


# --- Cross-cutting ---

def test_all_components_cover_5_improvements():
    """Verify all 5 improvements are covered."""
    all_content = " ".join(s.read_text() for s in SCHEMAS.values())
    improvements = [
        "externality_index",           # Externality Countermeasures
        "externality_counteraction",   # Externality Countermeasures
        "ecosystem_registry",          # Superalignment
        "cross_ecosystem_impact",      # Superalignment
        "content_piece",              # Content Layer
        "sensemaking_score",          # Content Layer
        "ai_impact_evaluation",       # AI Evaluation
        "value_stability_metric",     # Currency Stability
    ]
    for imp in improvements:
        assert imp in all_content, f"Missing: {imp}"
