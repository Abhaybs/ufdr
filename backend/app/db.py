from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import get_settings


settings = get_settings()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT,
            display_name TEXT,
            given_name TEXT,
            family_name TEXT,
            phone_number TEXT,
            email TEXT,
            source TEXT,
            raw_data TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT,
            conversation_id TEXT,
            sender TEXT,
            receiver TEXT,
            timestamp TEXT,
            body TEXT,
            direction TEXT,
            message_type TEXT,
            attachments TEXT,
            source TEXT,
            raw_data TEXT,
            vector_id TEXT
        );

        CREATE TABLE IF NOT EXISTS system_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            info_key TEXT,
            info_value TEXT,
            category TEXT,
            source TEXT
        );

        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            relative_path TEXT,
            description TEXT,
            tags TEXT,
            detected_text TEXT,
            source TEXT,
            metadata TEXT,
            vector_id TEXT,
            caption_status TEXT,
            caption_error TEXT,
            last_captioned_at TEXT
        );
        """
    )
    _ensure_column(cursor, "messages", "vector_id", "ALTER TABLE messages ADD COLUMN vector_id TEXT")
    _ensure_column(cursor, "images", "vector_id", "ALTER TABLE images ADD COLUMN vector_id TEXT")
    _ensure_column(cursor, "images", "caption_status", "ALTER TABLE images ADD COLUMN caption_status TEXT")
    _ensure_column(cursor, "images", "caption_error", "ALTER TABLE images ADD COLUMN caption_error TEXT")
    _ensure_column(cursor, "images", "last_captioned_at", "ALTER TABLE images ADD COLUMN last_captioned_at TEXT")
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_vector_id
        ON messages(vector_id)
        WHERE vector_id IS NOT NULL
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_images_vector_id
        ON images(vector_id)
        WHERE vector_id IS NOT NULL
        """
    )
    connection.commit()


@contextmanager
def get_connection(readonly: bool = False) -> Iterator[sqlite3.Connection]:
    db_path = settings.sqlite_path
    if readonly:
        uri = f"file:{db_path}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
    else:
        ensure_parent(db_path)
        connection = sqlite3.connect(db_path, check_same_thread=False)
    try:
        _ensure_schema(connection)
        yield connection
    finally:
        connection.close()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_column(cursor: sqlite3.Cursor, table_name: str, column_name: str, alter_statement: str) -> None:
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        cursor.execute(alter_statement)
