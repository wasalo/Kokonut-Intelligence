"""CSV remote-sensing uploads stay inside their selected plot/location scope."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.ingestion import remote_sensing


class PlotMapConnection:
    def __init__(self, plot_locations):
        self.plot_locations = plot_locations
        self.commit = MagicMock()
        self.rollback = MagicMock()
        self.close = MagicMock()
        self.cursor_obj = MagicMock()
        self.cursor_obj.fetchall.return_value = plot_locations
        self.cursor_context = MagicMock()
        self.cursor_context.__enter__.return_value = self.cursor_obj
        self.cursor_context.__exit__.return_value = False

    def cursor(self):
        return self.cursor_context


def _write_csv(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "plot_id,location_id,observation_date,source,ndvi\n"
        + "".join(
            f"{row['plot_id']},{row.get('location_id', '')},"
            f"2026-01-01,drone,0.5\n"
            for row in rows
        )
    )
    return path


def test_scope_is_required_before_file_or_database_access(tmp_path):
    with patch.object(remote_sensing, "get_db") as get_db, pytest.raises(
        ValueError, match="provide --location-id"
    ):
        remote_sensing.run(str(tmp_path / "missing.csv"))

    get_db.assert_not_called()


def test_cli_requires_explicit_scope_before_ingestion(tmp_path):
    with patch.object(remote_sensing, "get_db") as get_db, pytest.raises(SystemExit) as exc:
        remote_sensing.main(["--file", str(tmp_path / "unused.csv")])

    assert exc.value.code == 2
    get_db.assert_not_called()


def test_invalid_location_uuid_fails_before_reading_file_or_database(tmp_path):
    with patch.object(remote_sensing, "get_db") as get_db, pytest.raises(SystemExit) as exc:
        remote_sensing.main(
            ["--file", str(tmp_path / "missing.csv"), "--location-id", "invalid"]
        )

    assert exc.value.code == 2
    get_db.assert_not_called()


def test_single_location_query_canonicalizes_ids_and_imports_only_matching_plot(tmp_path):
    location_id = uuid4()
    plot_id = uuid4()
    db = PlotMapConnection([(plot_id, location_id)])
    csv_path = _write_csv(
        tmp_path / "single.csv",
        [{"plot_id": str(plot_id).upper(), "location_id": str(location_id).upper()}],
    )
    with (
        patch.object(remote_sensing, "get_db", return_value=db),
        patch.object(remote_sensing, "insert_observation", return_value="observation-id") as insert,
        patch.object(remote_sensing, "insert_clickhouse"),
        patch.object(remote_sensing, "log_ingestion"),
    ):
        remote_sensing.run(str(csv_path), location_id=str(location_id).upper())

    query, params = db.cursor_obj.execute.call_args.args
    assert "WHERE f.location_id = %s" in query
    assert params == (str(location_id), [str(plot_id)])
    record = insert.call_args.args[1]
    assert record["plot_id"] == str(plot_id)
    assert record["location_id"] == str(location_id)
    db.commit.assert_called_once_with()
    db.close.assert_called_once_with()


def test_row_location_mismatch_is_rejected_before_insert(tmp_path):
    location_id = uuid4()
    other_location_id = uuid4()
    plot_id = uuid4()
    db = PlotMapConnection([(plot_id, location_id)])
    csv_path = _write_csv(
        tmp_path / "mismatch.csv",
        [{"plot_id": str(plot_id), "location_id": str(other_location_id)}],
    )
    with (
        patch.object(remote_sensing, "get_db", return_value=db),
        patch.object(remote_sensing, "insert_observation") as insert,
        patch.object(remote_sensing, "log_ingestion"),
    ):
        remote_sensing.run(str(csv_path), location_id=str(location_id))

    insert.assert_not_called()
    db.rollback.assert_called_once_with()
    db.close.assert_called_once_with()


def test_plot_outside_single_location_lookup_is_rejected(tmp_path):
    location_id, other_location_id = uuid4(), uuid4()
    plot_id = uuid4()
    db = PlotMapConnection([])
    csv_path = _write_csv(
        tmp_path / "outside.csv",
        [{"plot_id": str(plot_id), "location_id": str(other_location_id)}],
    )
    with (
        patch.object(remote_sensing, "get_db", return_value=db),
        patch.object(remote_sensing, "insert_observation") as insert,
        patch.object(remote_sensing, "log_ingestion"),
    ):
        remote_sensing.run(str(csv_path), location_id=str(location_id))

    query, params = db.cursor_obj.execute.call_args.args
    assert "WHERE f.location_id = %s" in query
    assert params == (str(location_id), [str(plot_id)])
    insert.assert_not_called()


def test_invalid_plot_uuid_is_rejected_without_a_plot_lookup(tmp_path):
    db = PlotMapConnection([])
    csv_path = _write_csv(
        tmp_path / "invalid-plot.csv",
        [{"plot_id": "not-a-uuid", "location_id": ""}],
    )
    with (
        patch.object(remote_sensing, "get_db", return_value=db),
        patch.object(remote_sensing, "insert_observation") as insert,
        patch.object(remote_sensing, "log_ingestion"),
    ):
        remote_sensing.run(str(csv_path), location_id=str(uuid4()))

    db.cursor_obj.execute.assert_not_called()
    insert.assert_not_called()


def test_explicit_aggregate_mode_preserves_multi_location_imports(tmp_path):
    location_a, location_b = uuid4(), uuid4()
    plot_a, plot_b = uuid4(), uuid4()
    db = PlotMapConnection([(plot_a, location_a), (plot_b, location_b)])
    csv_path = _write_csv(
        tmp_path / "aggregate.csv",
        [
            {"plot_id": str(plot_a), "location_id": str(location_a)},
            {"plot_id": str(plot_b), "location_id": str(location_b)},
        ],
    )
    with (
        patch.object(remote_sensing, "get_db", return_value=db),
        patch.object(remote_sensing, "insert_observation", side_effect=["a", "b"]) as insert,
        patch.object(remote_sensing, "insert_clickhouse"),
        patch.object(remote_sensing, "log_ingestion"),
    ):
        remote_sensing.run(str(csv_path), all_locations=True)

    query, params = db.cursor_obj.execute.call_args.args
    assert "WHERE f.location_id IS NOT NULL" in query
    assert "p.id = ANY(%s)" in query
    assert params == (sorted([str(plot_a), str(plot_b)]),)
    records = [call.args[1] for call in insert.call_args_list]
    assert [record["location_id"] for record in records] == [
        str(location_a), str(location_b)
    ]


def test_cli_rejects_conflicting_scope_selectors_before_database_access(tmp_path):
    with patch.object(remote_sensing, "get_db") as get_db, pytest.raises(SystemExit) as exc:
        remote_sensing.main(
            [
                "--file",
                str(tmp_path / "unused.csv"),
                "--location-id",
                str(uuid4()),
                "--all-locations",
            ]
        )

    assert exc.value.code == 2
    get_db.assert_not_called()
