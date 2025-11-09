from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..schemas.graph import GraphMaintenanceResponse, GraphResponse
from ..services.graph import get_graph_client
from ..services.graph_sync import reset_graph, resync_graph

router = APIRouter(prefix="/api/graph", tags=["graph"])

_graph_client = get_graph_client()


@router.get("/{term}", response_model=GraphResponse)
def get_person_graph(term: str, limit: int = Query(200, ge=10, le=500)) -> GraphResponse:
    if not _graph_client.is_enabled():
        raise HTTPException(status_code=503, detail="Neo4j integration is disabled or not configured")

    response = _graph_client.fetch_person_graph(term=term, limit=limit)
    if not response.nodes:
        raise HTTPException(status_code=404, detail="No matching nodes found in Neo4j")
    return response


@router.post("/reset", response_model=GraphMaintenanceResponse)
def reset_graph_view() -> GraphMaintenanceResponse:
    stats = reset_graph()
    return _stats_to_response(stats)


@router.post("/resync", response_model=GraphMaintenanceResponse)
def resync_graph_view(clear_first: bool = Query(False, description="Clear Neo4j before rebuilding")) -> GraphMaintenanceResponse:
    stats = resync_graph(clear_first=clear_first)
    return _stats_to_response(stats)


def _stats_to_response(stats) -> GraphMaintenanceResponse:
    if stats.detail:
        status_code = 503 if "disabled" in stats.detail.lower() else 500
        raise HTTPException(status_code=status_code, detail=stats.detail)
    success = stats.detail is None
    return GraphMaintenanceResponse(
        success=success,
        detail=stats.detail,
        cleared=stats.cleared,
        contacts_synced=stats.contacts_synced,
        relationships_synced=stats.relationships_synced,
        skipped_contacts=stats.skipped_contacts,
        skipped_messages=stats.skipped_messages,
    )
