"""EBF P2 portfolio, CIDS mapping, and documentation tests."""

from pathlib import Path


P2_DASHBOARD_SEED = Path("schemas/seeds/034_ebf_p2_dashboard_datasets.sql")
CIDS_DOC = Path("docs/cids-mapping.md")
SCORECARD_DOC = Path("docs/ebf-scorecard.md")
TRUST_GRAPH_DOC = Path("docs/ebf-trust-graph.md")
IMPLEMENTATION_MEMO = Path("docs/ebf-implementation-memo.md")
ADVISOR_GUIDE = Path("docs/advisor-review-guide.md")


def test_ebf_p2_dashboard_seed_defines_messy_rollup_dataset() -> None:
    text = P2_DASHBOARD_SEED.read_text().lower()
    assert "ebf portfolio messy rollup" in text
    assert "messy_rollup" in text
    assert "do not rank farms" in text
    assert Path("dashboards/metabase/sql/25_ebf_portfolio_messy_rollup.sql").exists()
    assert Path("dashboards/metabase/22_ebf_scorecard.json").exists()


def test_cids_mapping_documents_ebf_indicator_report_path() -> None:
    text = CIDS_DOC.read_text()
    assert "EBF score metrics in `metric_value`" in text
    assert "`cids:IndicatorReport`" in text
    assert "no new CIDS class" in text
    assert "kokonut:ebfPillar" in text


def test_ebf_scorecard_guide_covers_public_gates_and_agents() -> None:
    text = SCORECARD_DOC.read_text().lower()
    for phrase in [
        "public ebf scorecards require",
        "public carbon pillar scores use `evidence_maturity_level = 6`",
        "no new cids class",
        "messy roll-ups",
        "agents may not verify scores",
    ]:
        assert phrase in text


def test_ebf_trust_graph_guide_covers_public_safe_exports() -> None:
    text = TRUST_GRAPH_DOC.read_text().lower()
    for phrase in [
        "ebf_trust_graph_node",
        "ebf_trust_graph_edge",
        "--public-safe",
        "reviewer identities",
        "portfolio dashboards should still use messy roll-ups",
    ]:
        assert phrase in text


def test_ebf_pr_sequence_docs_exist() -> None:
    memo = IMPLEMENTATION_MEMO.read_text().lower()
    advisor = ADVISOR_GUIDE.read_text().lower()
    assert "reused foundations" in memo
    assert "new ebf foundation" in memo
    assert "third-party calibration" in advisor
    assert "publication authority" in advisor


if __name__ == "__main__":
    test_ebf_p2_dashboard_seed_defines_messy_rollup_dataset()
    test_cids_mapping_documents_ebf_indicator_report_path()
    test_ebf_scorecard_guide_covers_public_gates_and_agents()
    test_ebf_trust_graph_guide_covers_public_safe_exports()
    test_ebf_pr_sequence_docs_exist()
