"""EBF dashboard dataset tests."""

from pathlib import Path


def test_dashboard_dataset_seeds_and_sql_exist() -> None:
    for seed in ["schemas/seeds/033_ebf_dashboard_datasets.sql", "schemas/seeds/034_ebf_p2_dashboard_datasets.sql"]:
        assert Path(seed).exists()
    for sql in ["22_ebf_scorecard.sql", "23_ebf_evidence_gap.sql", "24_ebf_calibration_history.sql", "25_ebf_portfolio_messy_rollup.sql"]:
        assert Path("dashboards/metabase/sql") .joinpath(sql).exists()


def test_dashboard_datasets_have_refresh_metadata() -> None:
    text = Path("schemas/seeds/033_ebf_dashboard_datasets.sql").read_text() + Path("schemas/seeds/034_ebf_p2_dashboard_datasets.sql").read_text()
    assert "refresh_cron" in text
    assert "impact_guild" in text


if __name__ == "__main__":
    test_dashboard_dataset_seeds_and_sql_exist()
    test_dashboard_datasets_have_refresh_metadata()
