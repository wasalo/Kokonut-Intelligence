"""Grant network tests: grant history, regional chapters, network diversity."""

from pathlib import Path

from services.analytics.grant_network import (
    compute_grant_history_summary,
    compute_network_diversity_summary,
    compute_regional_chapter_detail,
)

SCHEMA = Path("schemas/postgres/054_grant_network.sql")
SEED = Path("schemas/seeds/054_grant_network.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in [
        "grant_application_history", "regional_chapter", "network_membership",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in [
        "v_public_grant_application_history", "v_public_regional_chapters",
        "v_network_diversity", "v_public_farm_network_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_constraints() -> None:
    text = SCHEMA.read_text()
    assert "chk_grant_hist_status" in text
    assert "chk_chapter_type" in text
    assert "chk_chapter_status" in text
    assert "chk_membership_type" in text
    assert "chk_membership_status" in text
    assert "grant-network-v1" in text


def test_schema_adds_returning_applicant() -> None:
    text = SCHEMA.read_text()
    assert "returning_applicant" in text
    assert "grant_count" in text
    assert "total_grants_received" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metrics() -> None:
    text = SEED.read_text()
    assert "grant_funding_rate" in text
    assert "network_species_diversity" in text


def test_seed_has_adelphi_data() -> None:
    text = SEED.read_text()
    assert "Ma Earth Land Regenerators Grant" in text
    assert "Regenerative Agriculture Innovation Fund" in text
    assert "Caribbean Syntropic Network" in text
    assert "founding_member" in text
    assert "Grant Application Template" in text
    assert "returning_applicant" in text


def test_seed_has_grant_template() -> None:
    text = SEED.read_text()
    assert "Grant Application Template" in text
    assert "funder-ready" in text
    assert "regenerative" in text


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single
        self._calls = 0

    def execute(self, query, params=None):
        self._calls += 1

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._single

    def close(self):
        pass


class _MockConn:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def cursor(self, cursor_factory=None):
        return _MockCursor(self._rows, self._single)


def test_grant_history_summary_analytics() -> None:
    rows = [
        ("funded", "2025-Q2", 1, 25000.0, 25000.0, 0),
        ("submitted", "2026-Q1", 1, 50000.0, 0.0, 1),
    ]
    result = compute_grant_history_summary(_MockConn(rows), "test-location")
    assert result["total_applications"] == 2
    assert result["funded_applications"] == 1
    assert result["funding_rate_pct"] == 50.0
    assert result["total_awarded"] == 25000.0


def test_network_diversity_summary_analytics() -> None:
    rows = [
        ("Caribbean Syntropic Network", "Caribbean", "Dominican Republic", 3, 1),
    ]
    result = compute_network_diversity_summary(_MockConn(rows))
    assert result["total_chapters"] == 1
    assert result["total_farms"] == 3
    assert result["unique_countries"] == 1


def test_regional_chapter_detail_analytics() -> None:
    chapter_row = ("Caribbean Syntropic Network", "Regional network", "Caribbean", "Dominican Republic", "regional", "2025-09-01", 3)
    member_rows = [
        ("loc1", "Kokonut Adelphi", "Dominican Republic", "founding_member", "demonstration_site", "2025-09-01"),
    ]

    class _Conn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._single = chapter_row
                elif self._calls == 2:
                    c._rows = member_rows
            c.execute = execute
            return c

    result = compute_regional_chapter_detail(_Conn(), "test-chapter")
    assert result["chapter_name"] == "Caribbean Syntropic Network"
    assert result["member_count"] == 3
    assert len(result["members"]) == 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_constraints()
    test_schema_adds_returning_applicant()
    test_seed_has_metrics()
    test_seed_has_adelphi_data()
    test_seed_has_grant_template()
    test_grant_history_summary_analytics()
    test_network_diversity_summary_analytics()
    test_regional_chapter_detail_analytics()
    print("All tests passed.")
