from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class IngestionSummary(BaseModel):
    archive_name: str
    extraction_id: str
    notes: List[str]
    messages_ingested: int
    contacts_ingested: int
    system_records_ingested: int
    images_logged: int
    images_captioned: int


class IngestionResponse(BaseModel):
    success: bool
    summary: IngestionSummary
    detail: Optional[str] = None
