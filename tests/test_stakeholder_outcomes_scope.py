"""Location-scope guarantees for stakeholder outcome reports."""

from unittest.mock import MagicMock

from services.export.reports.strategy import generate_stakeholder_outcomes


def _connection(fetches):
    cursor = MagicMock()
    cursor.__enter__ = lambda self: cursor
    cursor.__exit__ = lambda self, *_args: None
    cursor.fetchall.side_effect = fetches
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_location_report_omits_network_architecture_view():
    conn, cursor = _connection([[{"id": "outcome-a"}]])

    report = generate_stakeholder_outcomes(conn, "location-a")

    assert report["outcomes"] == [{"id": "outcome-a"}]
    assert report["capability_and_value_stream_links"] == []
    assert any("no location lineage" in note for note in report["limitations"])
    assert cursor.execute.call_count == 1
    query, params = cursor.execute.call_args.args
    assert "location_id = %s::uuid" in query
    assert params == ["location-a"]


def test_network_report_keeps_network_architecture_view():
    architecture = [{"entity_type": "capability", "entity_name": "Synthetic"}]
    conn, cursor = _connection([[], architecture])

    report = generate_stakeholder_outcomes(conn)

    assert report["capability_and_value_stream_links"] == architecture
    assert cursor.execute.call_count == 2
    assert "v_stakeholder_capability_value_stream" in cursor.execute.call_args_list[1].args[0]
