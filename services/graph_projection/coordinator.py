"""Coordinate atomic typed-graph, RDF, and IRI rebuilds."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from services.iri.resolver import generate_iri
from services.rdf.graph_builder import _persist_graph

from .kernel import PROJECTION_KEY, PROJECTION_VERSION, _rebuild


def create_rebuild_request(conn, actor: str, source_cutoff=None) -> dict:
    if not actor or not actor.strip():
        raise ValueError("actor is required")
    cutoff = source_cutoff or datetime.now(timezone.utc)
    row = (
        conn.execute(
            conn.text(
                "INSERT INTO graph_rebuild_coordinator "
                "(id, status, source_cutoff, requested_by) "
                "VALUES (:id, 'building', :cutoff, :actor) "
                "RETURNING id, status, source_cutoff"
            ),
            {"id": uuid.uuid4(), "cutoff": cutoff, "actor": actor},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("rebuild request was not created")
    conn.commit()
    return dict(row)


def _finish_request(conn, request_id, status, typed_id=None, rdf_id=None, error=None):
    conn.execute(
        conn.text(
            "UPDATE graph_rebuild_coordinator SET status = :status, "
            "typed_generation_id = COALESCE(:typed_id, typed_generation_id), "
            "rdf_generation_id = COALESCE(:rdf_id, rdf_generation_id), "
            "error_message = :error, completed_at = CASE WHEN :status IN ('active', 'failed') THEN NOW() ELSE completed_at END "
            "WHERE id = :id"
        ),
        {"id": request_id, "status": status, "typed_id": typed_id, "rdf_id": rdf_id, "error": error},
    )


def rebuild_synchronized(conn, actor: str, location_id: str, iri_updates=None) -> dict:
    """Rebuild both projections at one cutoff, then version supplied IRIs."""
    request = create_rebuild_request(conn, actor)
    request_id = request["id"]
    cutoff = request["source_cutoff"]
    try:
        typed = _rebuild(
            conn, actor, PROJECTION_KEY, PROJECTION_VERSION,
            rebuild_id=request_id, cutoff=cutoff, commit=False,
        )
        rdf = _persist_graph(conn, location_id, rebuild_id=request_id, cutoff=cutoff, commit=False)
        iris = []
        for update in iri_updates or []:
            values = dict(update)
            values["rebuild_id"] = request_id
            values["source_cutoff"] = cutoff
            iris.append(generate_iri(conn, **values))
        _finish_request(conn, request_id, "active", typed["generation_id"], rdf["generation_id"])
        conn.commit()
        return {"rebuild_id": request_id, "source_cutoff": cutoff, "typed": typed, "rdf": rdf, "iris": iris, "status": "active"}
    except Exception as exc:
        conn.rollback()
        try:
            _finish_request(conn, request_id, "failed", error=str(exc))
            conn.commit()
        except Exception:
            conn.rollback()
        raise
