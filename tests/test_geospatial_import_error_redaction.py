"""GIS and remote-sensing import errors must not leak raw spatial input."""

from unittest.mock import MagicMock

from services.ingestion import gis_import, remote_sensing

SECRET = "sensitive-spatial-input"


def _remote_sensing_csv(path, *, source="drone", ndvi="0.5"):
    path.write_text(
        "plot_id,location_id,observation_date,source,ndvi\n"
        f"11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222,2026-01-01,{source},{ndvi}\n",
        encoding="utf-8",
    )
    return str(path)


def test_gis_csv_parser_does_not_log_invalid_coordinates(tmp_path, monkeypatch):
    logger = MagicMock()
    csv_path = tmp_path / "boundary.csv"
    csv_path.write_text(
        f"slug,lat,lon\nfarm,{SECRET},{SECRET}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gis_import, "logger", logger)

    assert gis_import.parse_csv_boundaries(str(csv_path)) == []

    assert SECRET not in str(logger.warning.call_args)
    assert "invalid latitude/longitude" in str(logger.warning.call_args)


def test_gis_update_failure_logs_only_exception_class(monkeypatch):
    connection = MagicMock()
    logger = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value

    def fail_update(query, *_args):
        if query.lstrip().startswith("UPDATE"):
            raise RuntimeError(f"database DSN contained {SECRET}")

    cursor.execute.side_effect = fail_update
    monkeypatch.setattr(gis_import, "logger", logger)

    assert not gis_import.import_record(
        connection,
        "record-id",
        "location",
        "SRID=4326;POINT(0 0)",
    )

    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)
    executed = [call.args[0] for call in cursor.execute.call_args_list]
    assert any(statement == "SAVEPOINT gis_import_update" for statement in executed)
    assert any(statement == "ROLLBACK TO SAVEPOINT gis_import_update" for statement in executed)
    assert any(statement == "RELEASE SAVEPOINT gis_import_update" for statement in executed)


def test_gis_run_failure_is_redacted_from_log_and_audit(tmp_path, monkeypatch):
    connection = MagicMock()
    logger = MagicMock()
    audit = MagicMock()
    monkeypatch.setattr(gis_import, "get_db", lambda: connection)
    monkeypatch.setattr(
        gis_import,
        "parse_geojson",
        lambda _path: [{"slug": "farm-slug", "geom_type": "Point", "wkt": "SRID=4326;POINT(0 0)", "lat": 0, "lon": 0}],
    )
    monkeypatch.setattr(
        gis_import,
        "resolve_target_record",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(f"database DSN contained {SECRET}")),
    )
    monkeypatch.setattr(gis_import, "hash_payload", lambda _value: "c" * 64)
    monkeypatch.setattr(gis_import, "log_ingestion", audit)
    monkeypatch.setattr(gis_import, "logger", logger)

    gis_import.run(str(tmp_path / "boundary.geojson"))

    audit.assert_called_once()
    assert audit.call_args.kwargs["error_message"] == "boundary import failed (RuntimeError)"
    assert audit.call_args.kwargs["db"] is connection
    assert audit.call_args.kwargs["location_id"] is None
    assert SECRET not in str(audit.call_args)
    assert SECRET not in str(logger.error.call_args)
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_remote_sensing_row_exception_is_redacted_and_rolled_back(tmp_path, monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    plot_id = "11111111-1111-4111-8111-111111111111"
    location_id = "22222222-2222-4222-8222-222222222222"
    cursor.fetchall.return_value = [(plot_id, location_id)]
    logger = MagicMock()
    audit = MagicMock()
    csv_path = _remote_sensing_csv(tmp_path / "sensing.csv", ndvi=SECRET)
    monkeypatch.setattr(remote_sensing, "get_db", lambda: connection)
    monkeypatch.setattr(remote_sensing, "hash_payload", lambda _value: "d" * 64)
    monkeypatch.setattr(remote_sensing, "log_ingestion", audit)
    monkeypatch.setattr(remote_sensing, "logger", logger)

    remote_sensing.run(csv_path, location_id=location_id)

    audit.assert_called_once()
    assert audit.call_args.kwargs["error_message"] == "row processing failed (ValueError)"
    assert SECRET not in str(audit.call_args)
    assert SECRET not in str(logger.error.call_args)
    connection.rollback.assert_called_once()
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_remote_sensing_rejects_unrecognized_source_without_echoing_it(tmp_path, monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    logger = MagicMock()
    csv_path = _remote_sensing_csv(tmp_path / "sensing.csv", source=SECRET)
    monkeypatch.setattr(remote_sensing, "get_db", lambda: connection)
    monkeypatch.setattr(remote_sensing, "logger", logger)

    remote_sensing.run(csv_path, all_locations=True)

    assert SECRET not in str(logger.warning.call_args)
    assert "invalid source" in str(logger.warning.call_args)
    connection.close.assert_called_once()
