from unittest.mock import MagicMock

import pytest

from services.iri.resolver import _compute_content_hash, generate_iri


def test_iri_content_hash_rejects_unknown_algorithm():
    with pytest.raises(ValueError, match="unsupported hash algorithm"):
        _compute_content_hash({"name": "Adelphi"}, algorithm="md5")


def test_iri_generation_takes_entity_advisory_lock_and_clears_all_currents():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.side_effect = [
        None,
        {"max_version": 0},
    ]
    generate_iri(conn, "location", "00000000-0000-0000-0000-000000000001", {"name": "Adelphi"})
    statements = [call.args[0] for call in conn.text.call_args_list]
    assert "pg_advisory_xact_lock" in statements[0]
    assert any("is_current = TRUE" in statement for statement in statements)


def test_iri_generation_persists_rebuild_provenance():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.side_effect = [None, {"max_version": 0}]
    generate_iri(
        conn,
        "location",
        "00000000-0000-0000-0000-000000000001",
        {"name": "Adelphi"},
        rebuild_id="rebuild-1",
        source_cutoff="2026-07-23T12:00:00Z",
    )
    insert = [call.args[0] for call in conn.text.call_args_list if "INSERT INTO iri_registry" in call.args[0]][0]
    assert "rebuild_id" in insert
    params = conn.execute.call_args_list[-1].args[1]
    assert params["rebuild_id"] == "rebuild-1"
    assert params["source_cutoff"] == "2026-07-23T12:00:00Z"


def test_iri_generation_rejects_incomplete_rebuild_provenance():
    with pytest.raises(ValueError, match="provided together"):
        generate_iri(MagicMock(), "location", "location-1", rebuild_id="rebuild-1")
