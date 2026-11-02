"""EBF JSON export validation tests."""

from datetime import date
from decimal import Decimal

from services.scoring.export import dumps_export, export_public_scorecard


def test_public_json_export_format() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params):
            self.calls += 1
        def fetchone(self):
            return {"scorecard_id": "a0000000-0000-0000-0000-000000000100", "overall_score": Decimal("6.5")}
        def fetchall(self):
            return [{"pillar_key": "soil_health", "normalized_score": Decimal("6.5")}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    document = export_public_scorecard(Conn(), "a0000000-0000-0000-0000-000000000100")
    rendered = dumps_export(document)
    assert document["export_type"] == "ebf_scorecard_public"
    assert "ebf_scorecard_public" in rendered


def test_json_export_serializes_decimals_to_float() -> None:
    from services.scoring.export import _json_value
    assert _json_value(Decimal("3.14")) == 3.14
    assert _json_value("plain") == "plain"


def test_json_export_includes_limitations_and_cids_mapping() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params):
            self.calls += 1
        def fetchone(self):
            return {"scorecard_id": "s1", "overall_score": Decimal("5.0")}
        def fetchall(self):
            return [{"pillar_key": "soil_health", "normalized_score": Decimal("5.0")}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    document = export_public_scorecard(Conn(), "s1")
    assert "limitations" in document
    assert "cids_mapping" in document
    assert len(document["limitations"]) >= 2


def test_public_scorecard_summary_uses_exact_migration_projection_and_payload() -> None:
    scorecard_id = "a0000000-0000-0000-0000-000000000100"
    columns = [
        "scorecard_id",
        "location_id",
        "location_name",
        "farm_id",
        "farm_name",
        "period_start",
        "period_end",
        "overall_score",
        "overall_confidence",
        "rubric_version",
        "evidence_maturity_level",
        "evidence_maturity_label",
        "pillar_count",
        "public_safe_pillar_count",
        "min_pillar_evidence_maturity",
        "max_pillar_evidence_maturity",
        "caveat",
    ]
    summary = {
        "scorecard_id": scorecard_id,
        "location_id": "b0000000-0000-0000-0000-000000000200",
        "location_name": "Synthetic location",
        "farm_id": "c0000000-0000-0000-0000-000000000300",
        "farm_name": "Synthetic farm",
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 3, 31),
        "overall_score": Decimal("6.5"),
        "overall_confidence": Decimal("0.92"),
        "rubric_version": "v1",
        "evidence_maturity_level": 5,
        "evidence_maturity_label": "High",
        "pillar_count": 4,
        "public_safe_pillar_count": 3,
        "min_pillar_evidence_maturity": 4,
        "max_pillar_evidence_maturity": 6,
        "caveat": "Contextual, not a farm ranking.",
    }

    class Cursor:
        def __init__(self):
            self.queries = []
            self.closed = False

        def execute(self, query, params):
            self.queries.append((query, params))

        def fetchone(self):
            return summary

        def fetchall(self):
            return [{"pillar_key": "soil_health", "normalized_score": Decimal("6.5")}]

        def close(self):
            self.closed = True

    class Conn:
        def __init__(self):
            self.cursor_instance = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_instance

    conn = Conn()
    document = export_public_scorecard(conn, scorecard_id)
    query, params = conn.cursor_instance.queries[0]
    projection = query.split("SELECT", 1)[1].split("FROM", 1)[0]
    selected_columns = [
        column.strip() for column in projection.replace("\n", " ").split(",")
    ]

    assert selected_columns == columns
    assert "FROM v_public_ebf_scorecard_summary" in query
    assert "WHERE scorecard_id = %s" in query
    assert params == (scorecard_id,)
    assert list(document["scorecard"]) == columns
    assert document["scorecard"] == {
        **summary,
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
        "overall_score": 6.5,
        "overall_confidence": 0.92,
    }
    assert document["pillars"] == [
        {"pillar_key": "soil_health", "normalized_score": 6.5}
    ]
    assert conn.cursor_instance.closed


if __name__ == "__main__":
    test_public_json_export_format()
