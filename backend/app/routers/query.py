from __future__ import annotations

from fastapi import APIRouter

from ..schemas.query import QueryRequest, QueryResponse
from ..services.query import run_query

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def handle_query(payload: QueryRequest) -> QueryResponse:
    """Answer an investigator question using embeddings + Gemini."""
    return run_query(payload)
