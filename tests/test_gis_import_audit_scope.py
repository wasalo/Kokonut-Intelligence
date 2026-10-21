"""GIS import audits stay scoped to the target's owning location."""

from unittest.mock import MagicMock

import pytest

from services.ingestion import gis_import


@pytest.mark.parametrize(
    ("target", "record_id", "location_id"),
    [
        ("location", "location-1", "location-1"),
        ("farm", "farm-1", "location-1"),
        ("plot", "plot-1", "location-1"),
    ],
)
def test_resolve_target_record_returns_owning_location(target, record_id, location_id):
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (record_id, location_id)

    assert gis_import.resolve_target_record(db, "source-slug", target) == (
        record_id,
        location_id,
    )

    query = cursor.execute.call_args.args[0]
    if target == "location":
        assert "SELECT id, id AS location_id FROM location" in query
    elif target == "farm":
        assert "SELECT id, location_id FROM farm" in query
    else:
        assert "JOIN farm f ON f.id = p.farm_id" in query
        assert "f.location_id" in query


@pytest.mark.parametrize(
    ("target", "record_id", "location_id"),
    [
        ("location", "location-1", "location-1"),
        ("farm", "farm-1", "location-1"),
        ("plot", "plot-1", "location-1"),
    ],
)
def test_run_audits_success_on_same_connection_and_location(
    target, record_id, location_id, monkeypatch, tmp_path
):
    db = MagicMock()
    audit_calls = []
    imported = []
    record = {
        "slug": "source-slug",
        "geom_type": "Point",
        "wkt": "SRID=4326;POINT(0 0)",
        "lat": 0,
        "lon": 0,
    }
    monkeypatch.setattr(gis_import, "get_db", lambda: db)
    monkeypatch.setattr(gis_import, "parse_geojson", lambda _path: [record])
    monkeypatch.setattr(
        gis_import,
        "resolve_target_record",
        lambda _db, slug, actual_target: (
            (record_id, location_id)
            if slug == record["slug"] and actual_target == target
            else pytest.fail("unexpected target resolution")
        ),
    )
    monkeypatch.setattr(gis_import, "import_record", lambda *args: imported.append(args) or True)
    monkeypatch.setattr(gis_import, "log_ingestion", lambda **kwargs: audit_calls.append(kwargs))

    gis_import.run(str(tmp_path / "boundary.geojson"), target=target)

    assert len(imported) == 1
    assert imported[0][:3] == (db, record_id, target)
    assert audit_calls[0]["db"] is db
    assert audit_calls[0]["location_id"] == location_id
    assert audit_calls[0]["target_id"] == record_id
    assert audit_calls[0]["status"] == "success"
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_run_unmatched_target_uses_fixed_failure_audit(tmp_path, monkeypatch):
    db = MagicMock()
    logger = MagicMock()
    audit_calls = []
    record = {"slug": "sensitive-source-slug", "geom_type": "Point", "wkt": "POINT(0 0)"}
    monkeypatch.setattr(gis_import, "get_db", lambda: db)
    monkeypatch.setattr(gis_import, "parse_geojson", lambda _path: [record])
    monkeypatch.setattr(gis_import, "resolve_target_record", lambda *_args: None)
    monkeypatch.setattr(gis_import, "hash_payload", lambda _value: "a" * 64)
    monkeypatch.setattr(gis_import, "log_ingestion", lambda **kwargs: audit_calls.append(kwargs))
    monkeypatch.setattr(gis_import, "logger", logger)

    gis_import.run(str(tmp_path / "boundary.geojson"))

    assert len(audit_calls) == 1
    assert audit_calls[0]["db"] is db
    assert audit_calls[0]["location_id"] is None
    assert audit_calls[0]["error_message"] == "Target record not found"
    assert "sensitive-source-slug" not in str(logger.method_calls)
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_run_rolls_back_and_closes_when_batch_commit_fails(tmp_path, monkeypatch):
    db = MagicMock()
    db.commit.side_effect = RuntimeError("commit failed")
    record = {"slug": "source-slug", "geom_type": "Point", "wkt": "SRID=4326;POINT(0 0)"}
    monkeypatch.setattr(gis_import, "get_db", lambda: db)
    monkeypatch.setattr(gis_import, "parse_geojson", lambda _path: [record])
    monkeypatch.setattr(gis_import, "resolve_target_record", lambda *_args: ("location-1", "location-1"))
    monkeypatch.setattr(gis_import, "import_record", lambda *_args: True)
    monkeypatch.setattr(gis_import, "log_ingestion", lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match="commit failed"):
        gis_import.run(str(tmp_path / "boundary.geojson"))

    db.rollback.assert_called_once()
    db.close.assert_called_once()

