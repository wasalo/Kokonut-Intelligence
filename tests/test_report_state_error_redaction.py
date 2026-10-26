from unittest.mock import MagicMock

from services.export.reports import state

SECRET = "private farm row and database-password=synthetic"


def test_state_of_kokonut_sections_redact_source_errors(monkeypatch):
    cursor = MagicMock()
    cursor.fetchall.return_value = [{
        "id": "location-1",
        "name": "Synthetic farm",
        "slug": "synthetic",
        "country": "DO",
        "region": "North",
        "status": "active",
    }]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(
        state,
        "generate_farm_summary",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(SECRET)),
    )
    for name in (
        "generate_crop_noi",
        "generate_environmental",
        "generate_climate_impact",
        "generate_financial_sustainability",
        "generate_capital_efficiency",
        "generate_holistic_wellbeing",
        "generate_community_governance",
        "generate_gnh_alignment",
        "generate_training_impact",
        "generate_regenerative_outcomes",
    ):
        monkeypatch.setattr(state, name, lambda *_args: {})

    locations, composed = state._state_of_kokonut_locations(conn, None, None, None)

    error = composed[0]["sections"]["farm_summary"]["error"]
    assert error == "report section failed (RuntimeError)"
    assert SECRET not in repr((locations, composed))
    cursor.close.assert_called_once_with()


def test_graph_report_redacts_descriptor_errors(monkeypatch, capsys):
    class Descriptor:
        name = "synthetic graph"
        layout = "flow"
        title = "Synthetic"

        def to_json(self):
            return {}

        def to_mermaid(self):
            raise ValueError(SECRET)

    monkeypatch.setattr(state, "build_all", lambda *_args, **_kwargs: [Descriptor()])

    report = state.generate_state_of_kokonut_graphs(object())
    output = capsys.readouterr()

    assert report["graphs"][0]["error"] == "graph generation failed (ValueError)"
    assert SECRET not in repr(report)
    assert SECRET not in output.out + output.err


def test_comprehensive_status_redacts_section_failures(monkeypatch):
    composed = [{"location_id": "location-1", "sections": {}}]
    monkeypatch.setattr(state, "_state_of_kokonut_locations", lambda *_args: ([{}], composed))
    monkeypatch.setattr(
        state,
        "generate_foundational_wellbeing",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(SECRET)),
    )
    monkeypatch.setattr(state, "generate_stakeholder_outcomes", lambda *_args: {})
    monkeypatch.setattr(
        state,
        "generate_capital_accounting",
        lambda *_args: (_ for _ in ()).throw(ValueError(SECRET)),
    )

    report = state.generate_comprehensive_status(MagicMock(), location_id="location-1")

    sections = report["locations"][0]["sections"]
    assert sections["foundational_wellbeing"]["error"] == (
        "report section failed (RuntimeError)"
    )
    assert sections["capital_accounting"]["error"] == (
        "capital accounting failed (ValueError)"
    )
    assert SECRET not in repr(report)


def test_strategic_reserve_redacts_seed_vault_error(monkeypatch):
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"id": "location-1", "name": "Synthetic farm"}]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    from services.strategic_reserve import health

    monkeypatch.setattr(health, "reserve_health", lambda *_args: {"reserves": [], "reserve_count": 0})
    monkeypatch.setattr(
        health,
        "seed_vault_health",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(SECRET)),
    )

    report = state.generate_strategic_reserve(conn, location_id="location-1")

    assert report["locations"][0]["seed_vault"]["error"] == (
        "seed-vault health failed (RuntimeError)"
    )
    assert SECRET not in repr(report)
    cursor.close.assert_called_once_with()
