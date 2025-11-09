from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from ..schemas.ingestion import IngestionResponse
from ..services.ufdr_ingest import ingest_ufdr_archive

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/ufdr", response_model=IngestionResponse)
async def upload_ufdr_archive(file: UploadFile = File(...)) -> IngestionResponse:
    summary = ingest_ufdr_archive(file)
    return IngestionResponse(success=True, summary=summary)
