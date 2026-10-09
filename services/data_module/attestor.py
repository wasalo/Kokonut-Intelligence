"""Data Attestor: per-IRI attestor tracking."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger("data.attestor")


def attest_to_iri(conn, iri_id: str, attestor_address: str) -> dict:
    existing = conn.execute(
        conn.text(
            "SELECT id FROM data_iri_attestor WHERE iri_id = :iri AND attestor_address = :addr"
        ),
        {"iri": iri_id, "addr": attestor_address},
    ).mappings().first()

    if existing:
        return {"iri_id": iri_id, "attestor_address": attestor_address, "already_attested": True}

    result = conn.execute(
        conn.text(
            "INSERT INTO data_iri_attestor (iri_id, attestor_address) "
            "VALUES (:iri, :addr) RETURNING id"
        ),
        {"iri": iri_id, "addr": attestor_address},
    ).mappings().first()

    logger.info("Attestor %s attested to IRI %s", attestor_address, iri_id)
    return {"id": str(result["id"]), "iri_id": iri_id, "attestor_address": attestor_address}


def get_attestors_for_iri(conn, iri_id: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT * FROM data_iri_attestor WHERE iri_id = :iri ORDER BY attested_at"
        ),
        {"iri": iri_id},
    )
    return [dict(r) for r in result.mappings()]


def get_attested_irids_for_address(conn, attestor_address: str) -> list[dict]:
    result = conn.execute(
        conn.text(
            "SELECT dia.*, iri.iri, iri.entity_type, iri.entity_id "
            "FROM data_iri_attestor dia "
            "JOIN iri_registry iri ON iri.id = dia.iri_id "
            "WHERE dia.attestor_address = :addr ORDER BY dia.attested_at DESC"
        ),
        {"addr": attestor_address},
    )
    return [dict(r) for r in result.mappings()]


def remove_attestor(conn, iri_id: str, attestor_address: str) -> bool:
    result = conn.execute(
        conn.text(
            "DELETE FROM data_iri_attestor WHERE iri_id = :iri AND attestor_address = :addr"
        ),
        {"iri": iri_id, "addr": attestor_address},
    )
    return result.rowcount > 0
