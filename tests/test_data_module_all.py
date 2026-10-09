"""Tests for services.data_module — content_hash, resolver, and attestor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# --- content_hash tests ---

def test_data_module_content_hash_sha256():
    from services.data_module.content_hash import compute_hash

    h = compute_hash(b"hello world", "sha256")
    assert len(h) == 64
    import hashlib
    assert h == hashlib.sha256(b"hello world").hexdigest()


def test_data_module_content_hash_blake2b():
    from services.data_module.content_hash import compute_hash

    h = compute_hash(b"test data", "blake2b256")
    assert len(h) == 64


def test_data_module_content_hash_rejects_unsupported():
    from services.data_module.content_hash import compute_hash

    with pytest.raises(ValueError, match="Unsupported algorithm"):
        compute_hash(b"data", "md5")


def test_data_module_compute_content_hash_dict():
    from services.data_module.content_hash import compute_content_hash

    result = compute_content_hash({"key": "value"}, algorithm="sha256")

    assert result["hash_algorithm"] == "sha256"
    assert result["content_type"] == "raw"
    assert len(result["hash_value"]) == 64


def test_data_module_create_content_hash_inserts():
    from services.data_module.content_hash import create_content_hash

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"id": "ch-001"}

    result = create_content_hash(conn, "iri-001", "abc123hash")

    assert result["id"] == "ch-001"
    assert result["hash_value"] == "abc123hash"


def test_data_module_create_content_hash_rejects_unsupported_algo():
    from services.data_module.content_hash import create_content_hash

    conn = MagicMock()

    with pytest.raises(ValueError, match="Unsupported algorithm"):
        create_content_hash(conn, "iri-001", "hash", hash_algorithm="md5")


def test_data_module_create_content_hash_graph_requires_canonicalization():
    from services.data_module.content_hash import create_content_hash

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"id": "ch-002"}

    result = create_content_hash(conn, "iri-001", "hash", content_type="graph")
    assert result["id"] == "ch-002"


# --- resolver tests ---

def test_data_module_define_resolver_inserts():
    from services.data_module.resolver import define_resolver

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "id": "resolver-001",
    }

    result = define_resolver(conn, "https://data.kokonut.network", "0xManager")

    assert result["id"] == "resolver-001"
    assert result["resolver_url"] == "https://data.kokonut.network"


def test_data_module_get_resolver_returns_none():
    from services.data_module.resolver import get_resolver

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None

    result = get_resolver(conn, "resolver-nonexistent")
    assert result is None


def test_data_module_register_data_to_resolver():
    from services.data_module.resolver import register_data_to_resolver

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"id": "reg-001"}

    result = register_data_to_resolver(conn, "resolver-001", "iri-001", registered_by="0xAdmin")

    assert result["resolver_id"] == "resolver-001"
    assert result["iri_id"] == "iri-001"


def test_data_module_unregister_data_from_resolver():
    from services.data_module.resolver import unregister_data_from_resolver

    conn = MagicMock()
    conn.execute.return_value.rowcount = 1

    result = unregister_data_from_resolver(conn, "resolver-001", "iri-001")
    assert result is True


def test_data_module_list_resolvers_returns_list():
    from services.data_module.resolver import list_resolvers

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    result = list_resolvers(conn)
    assert isinstance(result, list)


# --- attestor tests ---

def test_data_module_attest_to_iri_new():
    from services.data_module.attestor import attest_to_iri

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    conn.execute.return_value.mappings.return_value.first.side_effect = [
        None,  # existing check returns None
        {"id": "att-001"},  # insert returns id
    ]

    result = attest_to_iri(conn, "iri-001", "0xAttestor")

    assert result["iri_id"] == "iri-001"
    assert result["attestor_address"] == "0xAttestor"


def test_data_module_attest_to_iri_already_attested():
    from services.data_module.attestor import attest_to_iri

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"id": "existing"}

    result = attest_to_iri(conn, "iri-001", "0xAttestor")

    assert result["already_attested"] is True


def test_data_module_get_attestors_for_iri():
    from services.data_module.attestor import get_attestors_for_iri

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    result = get_attestors_for_iri(conn, "iri-001")
    assert isinstance(result, list)


def test_data_module_remove_attestor():
    from services.data_module.attestor import remove_attestor

    conn = MagicMock()
    conn.execute.return_value.rowcount = 1

    result = remove_attestor(conn, "iri-001", "0xAttestor")
    assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
