"""FastAPI Metadata Graph API."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

app = FastAPI(title="Kokonut Metadata Graph API", version="1.0.0")


class IriRequest(BaseModel):
    metadata: dict


class MetadataResponse(BaseModel):
    iri: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    version: Optional[int] = None
    content_hash: Optional[str] = None
    metadata_json: Optional[dict] = None


@app.get("/data/v2/metadata-graph/{iri:path}")
async def get_metadata_graph(iri: str):
    from services.common.database import get_connection
    from services.metadata_api.resolver import resolve_metadata_graph
    with get_connection() as conn:
        result = resolve_metadata_graph(conn, iri)
        if not result:
            raise HTTPException(status_code=404, detail=f"IRI not found: {iri}")
        return result


@app.post("/data/v2/iri-gen")
async def generate_iri(request: IriRequest):
    from services.common.database import get_connection
    from services.metadata_api.resolver import generate_iri_from_metadata
    with get_connection() as conn:
        iri = generate_iri_from_metadata(conn, request.metadata)
        return {"iri": iri, "metadata": request.metadata}


@app.get("/data/v2/entity/{entity_type}/{entity_id}")
async def get_entity_metadata(entity_type: str, entity_id: str):
    from services.common.database import get_connection
    from services.metadata_api.resolver import resolve_entity_metadata
    with get_connection() as conn:
        result = resolve_entity_metadata(conn, entity_type, entity_id)
        if not result:
            raise HTTPException(status_code=404, detail="Entity not found")
        return result


@app.get("/marketplace/v1/project/{location_id}")
async def get_project(location_id: str):
    from services.common.database import get_connection
    from services.metadata_api.app_metadata import get_complete_project_view
    with get_connection() as conn:
        result = get_complete_project_view(conn, location_id)
        if not result.get("location"):
            raise HTTPException(status_code=404, detail="Project not found")
        return result


@app.get("/marketplace/v1/projects")
async def list_projects(limit: int = 50, offset: int = 0):
    from services.common.database import get_connection
    with get_connection() as conn:
        result = conn.execute(
            conn.text(
                "SELECT l.id, l.name, l.status FROM location l "
                "WHERE l.status = 'active' "
                "ORDER BY l.name LIMIT :limit OFFSET :offset"
            ),
            {"limit": limit, "offset": offset},
        ).mappings()
        return [dict(r) for r in result]


@app.post("/data/v2/sparql")
async def sparql_query(query: str):
    from services.common.database import get_connection
    from services.rdf.sparql_engine import execute_sparql
    with get_connection() as conn:
        return execute_sparql(conn, query)


@app.get("/data/v2/graphs")
async def list_graphs():
    from services.common.database import get_connection
    from services.rdf.sparql_engine import list_named_graphs
    with get_connection() as conn:
        return list_named_graphs(conn)
