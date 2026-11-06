"""Tests for the Business Model Canvas service."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import psycopg2
import pytest

from services.analytics import business_model_canvas as bmc
from services.ingestion.base import get_db


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


def _location(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM location LIMIT 1")
        row = cur.fetchone()
    return str(row[0]) if row else None


def test_module_shape():
    assert hasattr(bmc, "create")
    assert hasattr(bmc, "list_canvas")
    assert hasattr(bmc, "get")
    assert hasattr(bmc, "update_block")
    assert hasattr(bmc, "create_version")
    assert hasattr(bmc, "list_versions")
    assert hasattr(bmc, "suggest")
    assert hasattr(bmc, "compute_health")


@pytest.mark.parametrize(
    ("command", "command_args"),
    [
        ("create", []),
        ("create-from-data", []),
        ("update-block", ["--canvas-id", "canvas-id", "--block", "key_partners"]),
        ("version", ["--canvas-id", "canvas-id"]),
    ],
)
def test_retired_cli_persistence_commands_fail_before_database_access(
    monkeypatch, capsys, command, command_args
):
    get_db_mock = MagicMock()
    monkeypatch.setattr(bmc, "get_db", get_db_mock)
    monkeypatch.setattr(sys, "argv", ["business_model_canvas", command, *command_args])

    with pytest.raises(SystemExit) as exc_info:
        bmc.main()

    assert exc_info.value.code == 2
    get_db_mock.assert_not_called()
    assert bmc._BMC_CLI_RETIREMENT_MESSAGE in capsys.readouterr().err


@pytest.mark.parametrize(
    "command", ["create", "create-from-data", "update-block", "version"]
)
def test_cmd_rejects_retired_commands_before_database_access(monkeypatch, command):
    get_db_mock = MagicMock()
    monkeypatch.setattr(bmc, "get_db", get_db_mock)

    with pytest.raises(ValueError, match="BMC CLI persistence is retired"):
        bmc._cmd(SimpleNamespace(command=command))

    get_db_mock.assert_not_called()


@pytest.mark.parametrize(
    ("command", "handler_name", "command_args"),
    [
        ("list", "list_canvas", {"location_id": "location-1", "org_id": None}),
        ("get", "get", {"canvas_id": "canvas-1"}),
        ("list-versions", "list_versions", {"canvas_id": "canvas-1"}),
        ("suggest", "suggest", {"location_id": "location-1"}),
        ("health", "compute_health", {"canvas_id": "canvas-1"}),
    ],
)
def test_supported_cli_reads_start_readonly_bounded_transaction(
    monkeypatch, command, handler_name, command_args
):
    events = []
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = lambda sql: events.append(("sql", sql))
    connection.set_session.side_effect = lambda **kwargs: events.append(("session", kwargs))
    result = {"command": command}
    handler = MagicMock(side_effect=lambda *args, **kwargs: events.append(("query", command)) or result)
    monkeypatch.setattr(bmc, "get_db", MagicMock(return_value=connection))
    monkeypatch.setattr(bmc, handler_name, handler)
    print_json = MagicMock()
    monkeypatch.setattr(bmc, "print_json", print_json)

    bmc._cmd(SimpleNamespace(command=command, **command_args))

    assert events == [
        ("session", {"readonly": True, "autocommit": False}),
        ("sql", "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"),
        ("sql", "SET LOCAL statement_timeout = '8s'"),
        ("sql", "SET LOCAL lock_timeout = '2s'"),
        ("query", command),
    ]
    print_json.assert_called_once_with(result)
    connection.close.assert_called_once_with()


def test_cli_help_keeps_retired_commands_visible(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["business_model_canvas", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        bmc.main()

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for command in bmc._BMC_RETIRED_CLI_COMMANDS:
        assert command in help_text
    assert bmc._BMC_CLI_RETIREMENT_MESSAGE in " ".join(help_text.split())


def test_create_and_list():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(
            conn, location_id=loc,
            canvas_name="Test Canvas",
            description="A test canvas",
            fiscal_year=2026,
            tags=["test"],
            created_by=None,
        )
        assert created["entity_type"] == "location"
        assert str(created["entity_id"]) == loc
        assert created["status"] == "draft"
        assert created["version"] == 1
        rows = bmc.list_canvas(conn, location_id=loc)
        assert any(str(r["id"]) == str(created["id"]) for r in rows)
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_get_with_children():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Child Test")
        canvas_id = str(created["id"])
        result = bmc.get(conn, canvas_id)
        assert result is not None
        assert result["canvas_name"] == "Child Test"
        assert "jobs" in result
        assert "pain_points" in result
        assert "gain_creators" in result
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_update_block():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Update Test")
        canvas_id = str(created["id"])
        items = [{"name": "Partner A", "type": "supplier"}]
        result = bmc.update_block(conn, canvas_id, "key_partners", items)
        assert result["id"]
        canvas = bmc.get(conn, canvas_id)
        assert canvas["key_partners"] == items
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_update_block_invalid():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Invalid Test")
        canvas_id = str(created["id"])
        with pytest.raises(ValueError, match="invalid block"):
            bmc.update_block(conn, canvas_id, "nonexistent_block", [])
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_version_snapshot():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Version Test")
        canvas_id = str(created["id"])
        bmc.update_block(conn, canvas_id, "key_partners", [{"name": "P1"}])
        v1 = bmc.create_version(conn, canvas_id, changes="Added partner", change_reason="Testing")
        assert v1["version"] == 1
        bmc.update_block(conn, canvas_id, "key_partners", [{"name": "P1"}, {"name": "P2"}])
        v2 = bmc.create_version(conn, canvas_id, changes="Added second partner")
        assert v2["version"] == 2
        versions = bmc.list_versions(conn, canvas_id)
        assert len(versions) == 2
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_suggest():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        out = bmc.suggest(conn, loc)
        assert "blocks" in out
        assert "generated_from" in out
        assert isinstance(out["blocks"], dict)
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_calculate_health_scores_blocks_and_bonuses_without_database_access():
    canvas = {block: [] for block in bmc.BMC_BLOCKS}
    canvas["key_partners"] = [{"name": "Partner A"}, {"name": "Partner B"}]
    canvas["value_propositions"] = [{"name": "Value"}]
    canvas["cost_structure"] = {"USD": 100.0}
    canvas["jobs"] = [{"name": "Customer job"}]

    health = bmc._calculate_health(canvas)

    assert health["health_score"] == 43.3
    assert health["breakdown"]["key_partners"] == 13.1
    assert health["breakdown"]["value_propositions"] == 11.1
    assert health["breakdown"]["cost_structure"] == 11.1
    assert health["breakdown"]["vpc_link_bonus"] == 5
    assert health["breakdown"]["cost_data_bonus"] == 3


def test_compute_health_reads_canvas_without_writing(monkeypatch):
    conn = MagicMock()
    canvas = {block: [] for block in bmc.BMC_BLOCKS}
    monkeypatch.setattr(bmc, "get", lambda _conn, _canvas_id: canvas)

    health = bmc.compute_health(conn, "canvas-id")

    assert health["health_score"] == 0.0
    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_compute_health():
    conn = _db()
    loc = _location(conn)
    if not loc:
        pytest.skip("no location row available")
    try:
        created = bmc.create(conn, location_id=loc, canvas_name="Health Test")
        canvas_id = str(created["id"])
        bmc.update_block(conn, canvas_id, "key_partners", [{"name": "P1"}, {"name": "P2"}])
        bmc.update_block(conn, canvas_id, "value_propositions", [{"desc": "V1"}])
        health = bmc.compute_health(conn, canvas_id)
        assert 0 <= health["health_score"] <= 100
        assert "breakdown" in health
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_get_nonexistent():
    conn = _db()
    try:
        result = bmc.get(conn, "00000000-0000-0000-0000-000000000000")
        assert result is None
    except psycopg2.ProgrammingError:
        pytest.skip("business_model_canvas table not present (migration not applied)")
    finally:
        conn.close()


def test_entity_validation():
    with pytest.raises(ValueError, match="provide exactly one"):
        bmc._entity(None, None)
    with pytest.raises(ValueError, match="provide exactly one"):
        bmc._entity("org-id", "loc-id")
