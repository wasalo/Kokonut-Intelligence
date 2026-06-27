"""EBF JSON export validation tests."""

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


if __name__ == "__main__":
    test_public_json_export_format()
