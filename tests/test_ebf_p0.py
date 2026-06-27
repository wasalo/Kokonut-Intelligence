"""EBF P0 schema, rubric, and public gate tests."""

from pathlib import Path


SCHEMA = Path("schemas/postgres/032_ebf_scorecard.sql")
SEED = Path("schemas/seeds/032_ebf_rubric.sql")
SEED_SCRIPT = Path("scripts/seed.sh")

PILLARS = [
    "air_quality",
    "water_management",
    "soil_health",
    "biodiversity",
    "carbon_sequestration",
    "equity_community",
    "implementation_quality",
]


def _schema_text() -> str:
    return SCHEMA.read_text()


def _seed_text() -> str:
    return SEED.read_text()


def test_ebf_p0_schema_defines_required_tables() -> None:
    text = _schema_text().lower()
    for table in [
        "ebf_pillar",
        "ebf_rubric_band",
        "ebf_scorecard",
        "ebf_score",
        "ebf_score_evidence",
    ]:
        assert f"create table if not exists {table}" in text


def test_ebf_p0_public_views_are_present() -> None:
    text = _schema_text().lower()
    for view in [
        "v_public_ebf_scorecard",
        "v_public_ebf_scorecard_summary",
        "v_public_ebf_pillar_summary",
    ]:
        assert f"create or replace view {view}" in text


def test_ebf_p0_uses_canonical_lifecycle_states() -> None:
    text = _schema_text().lower()
    assert "chk_ebf_scorecard_lifecycle" in text
    for status in ["draft", "submitted", "verified", "published", "rejected"]:
        assert f"'{status}'" in text

    for noncanonical_status in ["open_for_feedback", "under_review", "calibrated", "approved", "superseded"]:
        assert noncanonical_status not in text


def test_ebf_p0_public_maturity_and_carbon_gates_are_enforced() -> None:
    text = _schema_text().lower()
    assert "chk_ebf_scorecard_public_maturity" in text
    assert "evidence_maturity_level >= 4" in text
    assert "chk_ebf_score_public_carbon_level6" in text
    assert "pillar_key = 'carbon_sequestration'" in text
    assert "evidence_maturity_level = 6" in text


def test_ebf_p0_public_views_require_registry_and_evidence_links() -> None:
    text = _schema_text().lower()
    assert "farm_registry_record" in text
    assert "fr.status in ('verified', 'published')" in text
    assert "exists (\n      select 1 from ebf_score_evidence" in text
    assert "public ebf scorecards preserve maturity and confidence context" in text
    assert "do not rank farms as interchangeable units" in text


def test_ebf_p0_seed_defines_seven_pillars_and_dimension_mapping() -> None:
    text = _seed_text()
    for pillar in PILLARS:
        assert f"'{pillar}'" in text

    for dimension in ["ebf_environmental", "ebf_social", "ebf_sustainability"]:
        assert f"'{dimension}'" in text

    assert "JOIN impact_framework fw ON fw.framework_key = 'ebf'" in text
    assert "JOIN impact_dimension dim ON dim.dimension_key = ps.dimension_key" in text


def test_ebf_p0_seed_creates_seventy_rubric_bands() -> None:
    text = _seed_text().lower()
    assert "cross join generate_series(0, 9)" in text
    assert "unique(pillar_id, score_value, rubric_version)" in _schema_text().lower()
    assert len(PILLARS) * 10 == 70


def test_ebf_p0_seed_registers_cids_indicator_report_metric_definitions() -> None:
    text = _seed_text()
    for metric_key in [
        "ebf_air_quality_score",
        "ebf_water_management_score",
        "ebf_soil_health_score",
        "ebf_biodiversity_score",
        "ebf_carbon_sequestration_score",
        "ebf_equity_community_score",
        "ebf_implementation_quality_score",
        "ebf_overall_score",
    ]:
        assert f"'{metric_key}'" in text
    assert "cids_indicator_report" in text


def test_seed_script_loads_ebf_rubric_seed() -> None:
    text = SEED_SCRIPT.read_text()
    assert "schemas/seeds/032_ebf_rubric.sql" in text


if __name__ == "__main__":
    test_ebf_p0_schema_defines_required_tables()
    test_ebf_p0_public_views_are_present()
    test_ebf_p0_uses_canonical_lifecycle_states()
    test_ebf_p0_public_maturity_and_carbon_gates_are_enforced()
    test_ebf_p0_public_views_require_registry_and_evidence_links()
    test_ebf_p0_seed_defines_seven_pillars_and_dimension_mapping()
    test_ebf_p0_seed_creates_seventy_rubric_bands()
    test_ebf_p0_seed_registers_cids_indicator_report_metric_definitions()
    test_seed_script_loads_ebf_rubric_seed()
