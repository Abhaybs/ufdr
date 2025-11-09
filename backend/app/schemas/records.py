from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Contact(BaseModel):
    id: int
    display_name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None


class Message(BaseModel):
    id: int
    conversation_id: Optional[str] = None
    sender: Optional[str] = None
    receiver: Optional[str] = None
    timestamp: Optional[datetime] = Field(default=None, description="ISO formatted timestamp")
    body: Optional[str] = None
    direction: Optional[str] = None
    message_type: Optional[str] = None
    source: Optional[str] = None


class SystemInfoRecord(BaseModel):
    id: int
    info_key: str
    info_value: str
    category: Optional[str] = None
    source: Optional[str] = None


class ImageRecord(BaseModel):
    id: int
    file_path: str
    description: Optional[str] = None
    tags: Optional[str] = None
    detected_text: Optional[str] = None
    source: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int
