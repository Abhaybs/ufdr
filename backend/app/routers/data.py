from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

from ..db import get_connection
from ..schemas.records import ImageRecord, Message, PaginatedResponse, SystemInfoRecord

router = APIRouter(prefix="/api", tags=["data"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


@router.get("/messages", response_model=PaginatedResponse)
def list_messages(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    search: str | None = Query(default=None, description="Optional text search across message body"),
) -> PaginatedResponse:
    params: List[Any] = []
    where_clause = ""
    if search:
        where_clause = "WHERE body LIKE ?"
        params.append(f"%{search}%")

    with get_connection(readonly=True) as conn:
        cursor = conn.cursor()
        total_query = f"SELECT COUNT(*) FROM messages {where_clause}"
        total = cursor.execute(total_query, params).fetchone()[0]

        data_query = (
            f"SELECT id, conversation_id, sender, receiver, timestamp, body, direction, message_type, source "
            f"FROM messages {where_clause} ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?"
        )
        data_params = params + [limit, offset]
        rows = cursor.execute(data_query, data_params).fetchall()

    items = [
        Message(
            id=row[0],
            conversation_id=row[1],
            sender=row[2],
            receiver=row[3],
            timestamp=row[4],
            body=row[5],
            direction=row[6],
            message_type=row[7],
            source=row[8],
        )
        for row in rows
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/contacts", response_model=PaginatedResponse)
def list_contacts(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    search: str | None = Query(default=None, description="Search across display name, phone, or email"),
) -> PaginatedResponse:
    params: List[Any] = []
    where_clause = ""
    if search:
        where_clause = "WHERE display_name LIKE ? OR phone_number LIKE ? OR email LIKE ?"
        like_pattern = f"%{search}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    with get_connection(readonly=True) as conn:
        cursor = conn.cursor()
        total_query = f"SELECT COUNT(*) FROM contacts {where_clause}"
        total = cursor.execute(total_query, params).fetchone()[0]

        data_query = (
            f"SELECT id, display_name, given_name, family_name, phone_number, email, source "
            f"FROM contacts {where_clause} ORDER BY display_name ASC LIMIT ? OFFSET ?"
        )
        data_params = params + [limit, offset]
        rows = cursor.execute(data_query, data_params).fetchall()

    items: List[Dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "display_name": row[1],
                "given_name": row[2],
                "family_name": row[3],
                "phone_number": row[4],
                "email": row[5],
                "source": row[6],
            }
        )

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/system-info", response_model=PaginatedResponse)
def list_system_info(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    category: str | None = Query(default=None),
) -> PaginatedResponse:
    params: List[Any] = []
    where_clause = ""
    if category:
        where_clause = "WHERE category = ?"
        params.append(category)

    with get_connection(readonly=True) as conn:
        cursor = conn.cursor()
        total_query = f"SELECT COUNT(*) FROM system_info {where_clause}"
        total = cursor.execute(total_query, params).fetchone()[0]

        data_query = (
            f"SELECT id, info_key, info_value, category, source "
            f"FROM system_info {where_clause} ORDER BY info_key ASC LIMIT ? OFFSET ?"
        )
        data_params = params + [limit, offset]
        rows = cursor.execute(data_query, data_params).fetchall()

    items = [
        SystemInfoRecord(
            id=row[0],
            info_key=row[1],
            info_value=row[2],
            category=row[3],
            source=row[4],
        )
        for row in rows
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/images", response_model=PaginatedResponse)
def list_images(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse:
    with get_connection(readonly=True) as conn:
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        data_query = (
            "SELECT id, relative_path, description, tags, detected_text, source "
            "FROM images ORDER BY id ASC LIMIT ? OFFSET ?"
        )
        rows = cursor.execute(data_query, (limit, offset)).fetchall()

    items = [
        ImageRecord(
            id=row[0],
            file_path=row[1],
            description=row[2],
            tags=row[3],
            detected_text=row[4],
            source=row[5],
        )
        for row in rows
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
