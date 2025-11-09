from __future__ import annotations

import json
import logging
import mimetypes
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from fastapi import HTTPException, UploadFile, status

from ..db import get_connection
from ..schemas.ingestion import IngestionSummary
from ..services.embedding import encode_texts
from ..services.graph import get_graph_client
from ..services.llm import get_gemini_client, get_gemini_vision_client
from ..services.vector_store import get_vector_store
from ..config import get_settings
from ..utils.graph import canonicalize_actor, compose_display_name
from ..utils.file_ops import (
    UploadPersistenceError,
    UploadStorageFullError,
    persist_upload,
)

logger = logging.getLogger(__name__)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".heic", ".heif", ".tiff"}
TEXT_FIELDS = ["text", "body", "message", "content", "value", "notes"]
TIMESTAMP_FIELDS = ["timestamp", "date", "created", "sent", "received", "time", "modified"]
SENDER_FIELDS = ["sender", "from", "author", "handle", "address", "account", "source"]
RECEIVER_FIELDS = ["receiver", "to", "target", "recipient", "destination"]
CONVERSATION_FIELDS = ["conversation", "thread", "chat", "dialog", "room"]
DIRECTION_FIELDS = ["direction", "is_from_me", "incoming", "outgoing", "type"]
MESSAGE_TYPE_FIELDS = ["type", "message_type", "category", "service"]


SETTINGS = get_settings()
GRAPH_CLIENT = get_graph_client()
CONTACT_ALIAS_MAP: Dict[str, str] = {}
VECTOR_STORE = get_vector_store()


@dataclass
class UFDRSources:
    report: Optional[Path] = None
    message_dbs: List[Path] = field(default_factory=list)
    contact_dbs: List[Path] = field(default_factory=list)
    contact_xml_files: List[Path] = field(default_factory=list)
    system_plists: List[Path] = field(default_factory=list)
    image_files: List[Path] = field(default_factory=list)


@dataclass
class GraphStats:
    contacts_registered: int = 0
    relationships_registered: int = 0
    seen_contact_identifiers: set[str] = field(default_factory=set)
    seen_message_ids: set[str] = field(default_factory=set)


@dataclass
class EmbeddingRecord:
    vector_id: str
    text: str
    metadata: Dict[str, str]


@dataclass
class ImageInventoryRecord:
    id: int
    file_path: Path
    relative_path: Path
    metadata: Dict[str, object]


def ingest_ufdr_archive(upload: UploadFile) -> IngestionSummary:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Uploaded file is missing a filename")

    try:
        archive_path, extraction_dir = persist_upload(upload)
    except UploadStorageFullError as exc:
        logger.warning("Uploads directory is out of space: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Uploads storage is full. Clear old ingests in storage/uploads or free disk space before retrying.",
        ) from exc
    except UploadPersistenceError as exc:
        logger.exception("Failed to persist UFDR upload")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extraction_dir)
    except zipfile.BadZipFile as exc:
        logger.exception("Failed to extract UFDR archive")
        raise HTTPException(status_code=400, detail="UFDR archive is corrupt or not a valid ZIP") from exc

    report_path = next(extraction_dir.rglob("report.xml"), None)
    sources = discover_sources(extraction_dir, report_path)

    notes: List[str] = []
    CONTACT_ALIAS_MAP.clear()
    graph_stats = GraphStats()

    if not sources.message_dbs and not sources.contact_dbs:
        notes.append("No obvious message or contact databases were discovered. Review the extraction manually.")

    messages_ingested = 0
    message_embedding_records: List[EmbeddingRecord] = []
    for database_path in sources.message_dbs:
        try:
            processed, embeddings = ingest_messages_from_sqlite(database_path, graph_stats)
            messages_ingested += processed
            message_embedding_records.extend(embeddings)
            notes.append(f"Parsed {processed} messages from {database_path.relative_to(extraction_dir)}")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed parsing messages from %s", database_path)
            notes.append(f"Failed parsing messages from {database_path.name}: {exc}")

    contacts_ingested = 0
    for database_path in sources.contact_dbs:
        try:
            processed = ingest_contacts_from_sqlite(database_path, graph_stats)
            contacts_ingested += processed
            notes.append(f"Parsed {processed} contacts from {database_path.relative_to(extraction_dir)}")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed parsing contacts from %s", database_path)
            notes.append(f"Failed parsing contacts from {database_path.name}: {exc}")

    for xml_path in sources.contact_xml_files:
        try:
            processed = ingest_contacts_from_xml(xml_path, graph_stats)
            contacts_ingested += processed
            notes.append(f"Parsed {processed} contacts from {xml_path.relative_to(extraction_dir)}")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed parsing contacts XML from %s", xml_path)
            notes.append(f"Failed parsing contacts XML {xml_path.name}: {exc}")

    system_records_ingested = 0
    for plist_path in sources.system_plists:
        try:
            processed = ingest_system_info_from_plist(plist_path)
            system_records_ingested += processed
            notes.append(f"Parsed {processed} system records from {plist_path.relative_to(extraction_dir)}")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed parsing plist from %s", plist_path)
            notes.append(f"Failed parsing system plist {plist_path.name}: {exc}")

    image_embedding_records: List[EmbeddingRecord] = []
    image_count, new_images = log_image_inventory(sources.image_files, extraction_dir)
    images_captioned = 0
    if image_count:
        notes.append(f"Logged {image_count} image references for Phase 3 processing")
    if new_images:
        try:
            images_captioned, image_embedding_records = describe_and_index_images(new_images)
            if images_captioned:
                notes.append(f"Generated captions for {images_captioned} images")
            else:
                notes.append(
                    f"No image captions generated across {len(new_images)} attempts; review logs for vision errors"
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed generating image descriptions")
            notes.append(f"Image captioning failed: {exc}")

    if VECTOR_STORE.is_enabled():
        combined_records = message_embedding_records + image_embedding_records
        if combined_records:
            try:
                _index_embeddings(combined_records)
                if message_embedding_records and image_embedding_records:
                    detail = f"{len(message_embedding_records)} messages and {len(image_embedding_records)} images"
                elif message_embedding_records:
                    detail = f"{len(message_embedding_records)} messages"
                else:
                    detail = f"{len(image_embedding_records)} images"
                notes.append(f"Stored embeddings for {detail}")
            except RuntimeError as exc:
                logger.error("Vector store indexing failed: %s", exc)
                notes.append(f"Vector store indexing failed: {exc}")
        else:
            notes.append("Vector store enabled but no content suitable for embeddings was found")
    else:
        notes.append("Vector store disabled; set VECTOR_STORE_ENABLED=1 to enable embeddings")

    if GRAPH_CLIENT.is_enabled():
        if graph_stats.contacts_registered or graph_stats.relationships_registered:
            notes.append(
                f"Neo4j graph updated ({graph_stats.contacts_registered} contacts, {graph_stats.relationships_registered} message links)"
            )
        else:
            notes.append("Neo4j graph integration enabled; no new contacts or message links were added")
    else:
        notes.append("Neo4j integration skipped (set NEO4J_ENABLED=1 and install Phase 2 requirements to enable)")

    summary = IngestionSummary(
        archive_name=upload.filename,
        extraction_id=extraction_dir.name,
        notes=notes,
        messages_ingested=messages_ingested,
        contacts_ingested=contacts_ingested,
        system_records_ingested=system_records_ingested,
        images_logged=image_count,
        images_captioned=images_captioned,
    )
    return summary


def discover_sources(extraction_dir: Path, report_path: Optional[Path]) -> UFDRSources:
    sources = UFDRSources(report=report_path)

    for path in extraction_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        name_lower = path.name.lower()

        if suffix in {".sqlite", ".db"}:
            if any(keyword in name_lower for keyword in ("sms", "message", "chat", "imessage", "mms", "whatsapp")):
                sources.message_dbs.append(path)
            elif "contact" in name_lower or "addressbook" in name_lower:
                sources.contact_dbs.append(path)
        elif suffix == ".xml" and "contact" in name_lower:
            sources.contact_xml_files.append(path)
        elif suffix == ".plist":
            sources.system_plists.append(path)
        elif suffix in IMAGE_EXTENSIONS:
            sources.image_files.append(path)

    return sources


def ingest_messages_from_sqlite(db_path: Path, graph_stats: GraphStats | None = None) -> Tuple[int, List[EmbeddingRecord]]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    total_ingested = 0
    embedding_records: List[EmbeddingRecord] = []

    try:
        tables = list(_iter_user_tables(connection))
        for table_name, columns in tables:
            if not _looks_like_message_table(columns):
                continue
            processed, records = _ingest_messages_from_table(connection, db_path, table_name, columns, graph_stats)
            total_ingested += processed
            embedding_records.extend(records)
    finally:
        connection.close()

    return total_ingested, embedding_records


def ingest_contacts_from_sqlite(db_path: Path, graph_stats: GraphStats | None = None) -> int:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    total_ingested = 0

    try:
        tables = list(_iter_user_tables(connection))
        for table_name, columns in tables:
            if not _looks_like_contact_table(columns):
                continue
            total_ingested += _ingest_contacts_from_table(connection, db_path, table_name, columns, graph_stats)
    finally:
        connection.close()

    return total_ingested


def ingest_contacts_from_xml(xml_path: Path, graph_stats: GraphStats | None = None) -> int:
    try:
        import xml.etree.ElementTree as ET
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("xml.etree.ElementTree is unavailable in this environment") from exc

    count = 0
    tree = ET.parse(xml_path)
    root = tree.getroot()

    with get_connection() as conn:
        cursor = conn.cursor()
        for contact_elem in root.findall(".//contact"):
            display_name = contact_elem.findtext("displayName")
            given_name = contact_elem.findtext("firstName")
            family_name = contact_elem.findtext("lastName")
            phone_number = contact_elem.findtext("phone")
            email = contact_elem.findtext("email")
            raw_data = json.dumps({child.tag: child.text for child in contact_elem})

            cursor.execute(
                """
                INSERT INTO contacts (external_id, display_name, given_name, family_name, phone_number, email, source, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{xml_path.name}:{count}",
                    display_name,
                    given_name,
                    family_name,
                    phone_number,
                    email,
                    str(xml_path),
                    raw_data,
                ),
            )
            _register_contact_with_graph(
                display_name=display_name,
                given_name=given_name,
                family_name=family_name,
                phone_number=phone_number,
                email=email,
                source=str(xml_path),
                graph_stats=graph_stats,
            )
            count += 1
        conn.commit()

    return count


def ingest_system_info_from_plist(plist_path: Path) -> int:
    try:
        import plistlib
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("plistlib is unavailable in this environment") from exc

    count = 0
    with plist_path.open("rb") as handle:
        plist_data = plistlib.load(handle)

    def _flatten(prefix: str, value: object) -> Iterable[tuple[str, str]]:
        if isinstance(value, dict):
            for key, nested_value in value.items():
                nested_prefix = f"{prefix}.{key}" if prefix else str(key)
                yield from _flatten(nested_prefix, nested_value)
        elif isinstance(value, list):
            for index, nested_value in enumerate(value):
                nested_prefix = f"{prefix}[{index}]"
                yield from _flatten(nested_prefix, nested_value)
        else:
            yield prefix, str(value)

    flattened = list(_flatten("", plist_data))

    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in flattened:
            cursor.execute(
                """
                INSERT INTO system_info (info_key, info_value, category, source)
                VALUES (?, ?, ?, ?)
                """,
                (
                    key,
                    value,
                    plist_path.stem,
                    str(plist_path),
                ),
            )
            count += 1
        conn.commit()

    return count


def log_image_inventory(image_paths: Sequence[Path], extraction_dir: Path) -> Tuple[int, List[ImageInventoryRecord]]:
    if not image_paths:
        return 0, []

    records: List[ImageInventoryRecord] = []
    seen_paths: set[str] = set()

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        processed = 0
        for image_path in image_paths:
            normalized_path = str(image_path)
            if normalized_path in seen_paths:
                continue
            seen_paths.add(normalized_path)
            processed += 1
            try:
                relative_path = image_path.relative_to(extraction_dir)
            except ValueError:
                relative_path = image_path

            metadata = _build_image_metadata(image_path=image_path, relative_path=relative_path, extraction_dir=extraction_dir)

            cursor.execute(
                """
                INSERT OR IGNORE INTO images (file_path, relative_path, source, metadata, caption_status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    normalized_path,
                    str(relative_path),
                    "ufdr",
                    json.dumps(metadata, default=_safe_json_default),
                    "pending",
                ),
            )

            if cursor.rowcount > 0:
                image_id = cursor.lastrowid
                records.append(
                    ImageInventoryRecord(
                        id=image_id,
                        file_path=Path(normalized_path),
                        relative_path=Path(relative_path),
                        metadata=metadata,
                    )
                )
            else:
                existing_row = cursor.execute(
                    "SELECT id, caption_status, metadata FROM images WHERE file_path = ?",
                    (normalized_path,),
                ).fetchone()
                if existing_row is None:
                    continue

                image_id = existing_row[0]
                existing_status = existing_row[1] or ""
                try:
                    existing_metadata = json.loads(existing_row[2]) if existing_row[2] else {}
                except json.JSONDecodeError:
                    existing_metadata = {}
                merged_metadata = {**existing_metadata, **metadata}
                cursor.execute(
                    """
                    UPDATE images
                    SET relative_path = ?, source = ?, metadata = ?
                    WHERE id = ?
                    """,
                    (
                        str(relative_path),
                        "ufdr",
                        json.dumps(merged_metadata, default=_safe_json_default),
                        image_id,
                    ),
                )
                if existing_status.lower() != "done":
                    cursor.execute(
                        "UPDATE images SET caption_status = ? WHERE id = ?",
                        ("pending", image_id),
                    )
                    records.append(
                        ImageInventoryRecord(
                            id=image_id,
                            file_path=Path(normalized_path),
                            relative_path=Path(relative_path),
                            metadata=merged_metadata,
                        )
                    )

        conn.commit()

    return processed, records


def describe_and_index_images(records: Sequence[ImageInventoryRecord]) -> Tuple[int, List[EmbeddingRecord]]:
    if not records:
        return 0, []

    vision_client = get_gemini_vision_client()
    embeddings: List[EmbeddingRecord] = []
    successes = 0

    with get_connection() as conn:
        cursor = conn.cursor()
        for record in records:
            timestamp_iso = datetime.now(timezone.utc).isoformat()
            try:
                description = vision_client.describe_image(record.file_path)
                tag_string = ", ".join(description.tags) if description.tags else None
                vector_id = f"img:{record.id}"
                metadata_update = {**record.metadata, "tags": description.tags, "caption": description.caption}
                if description.detected_text:
                    metadata_update["detected_text"] = description.detected_text

                cursor.execute(
                    """
                    UPDATE images
                    SET description = ?, tags = ?, detected_text = ?, vector_id = ?, caption_status = ?, caption_error = NULL, last_captioned_at = ?, metadata = ?
                    WHERE id = ?
                    """,
                    (
                        description.caption,
                        tag_string,
                        description.detected_text,
                        vector_id,
                        "done",
                        timestamp_iso,
                        json.dumps(metadata_update, default=_safe_json_default),
                        record.id,
                    ),
                )
                successes += 1

                embedding_text_parts = [description.caption]
                if description.tags:
                    embedding_text_parts.append(f"Tags: {', '.join(description.tags)}")
                if description.detected_text:
                    embedding_text_parts.append(f"Detected text: {description.detected_text}")
                embedding_text = "\n".join(embedding_text_parts)

                embedding_metadata: Dict[str, str] = {
                    "type": "image",
                    "image_id": str(record.id),
                    "relative_path": str(record.relative_path),
                    "source": "ufdr",
                    "caption_source": "gemini_vision",
                }
                embedding_metadata["caption"] = description.caption[:256]
                if description.tags:
                    embedding_metadata["tags"] = ", ".join(description.tags)

                embeddings.append(
                    EmbeddingRecord(
                        vector_id=vector_id,
                        text=embedding_text,
                        metadata=embedding_metadata,
                    )
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Image captioning failed for %s: %s", record.file_path, exc)
                cursor.execute(
                    """
                    UPDATE images
                    SET caption_status = ?, caption_error = ?, last_captioned_at = ?
                    WHERE id = ?
                    """,
                    (
                        "failed",
                        str(exc)[:512],
                        timestamp_iso,
                        record.id,
                    ),
                )
        conn.commit()

    return successes, embeddings


def _build_image_metadata(*, image_path: Path, relative_path: Path, extraction_dir: Path) -> Dict[str, object]:
    metadata: Dict[str, object] = {
        "file_path": str(image_path),
        "relative_path": str(relative_path),
        "extraction_id": extraction_dir.name,
    }

    try:
        stat_result = image_path.stat()
    except (FileNotFoundError, OSError):
        stat_result = None

    if stat_result:
        metadata["size_bytes"] = stat_result.st_size
        metadata["modified_at"] = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc).isoformat()
        metadata["created_at"] = datetime.fromtimestamp(stat_result.st_ctime, tz=timezone.utc).isoformat()

    mime_type, _ = mimetypes.guess_type(str(image_path))
    if mime_type:
        metadata["mime_type"] = mime_type
    elif image_path.suffix.lower() in {".heic", ".heif"}:
        metadata["mime_type"] = "image/heic"

    return metadata


def _iter_user_tables(connection: sqlite3.Connection) -> Iterable[tuple[str, List[str]]]:
    cursor = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    )
    for row in cursor.fetchall():
        name = row[0]
        info_cursor = connection.execute(f"PRAGMA table_info('{name}')")
        columns = [info_row[1] for info_row in info_cursor.fetchall()]
        yield name, columns


def _looks_like_message_table(columns: Sequence[str]) -> bool:
    lowered = [column.lower() for column in columns]
    return any(field in lowered for field in TEXT_FIELDS) and any(field in lowered for field in TIMESTAMP_FIELDS)


def _looks_like_contact_table(columns: Sequence[str]) -> bool:
    lowered = [column.lower() for column in columns]
    return ("contact" in lowered or any(field in lowered for field in ("first", "last", "name"))) and any(field in lowered for field in ("phone", "number", "email", "address"))


def _ingest_messages_from_table(
    connection: sqlite3.Connection,
    db_path: Path,
    table_name: str,
    columns: Sequence[str],
    graph_stats: GraphStats | None = None,
) -> Tuple[int, List[EmbeddingRecord]]:
    cursor = connection.execute(f"SELECT rowid AS _rowid_, * FROM '{table_name}'")
    rows = cursor.fetchall()
    if not rows:
        return 0, []

    ingested = 0
    embedding_records: List[EmbeddingRecord] = []
    with get_connection() as target_conn:
        target_cursor = target_conn.cursor()
        for row in rows:
            payload = dict(zip([column.lower() for column in ["_rowid_"] + list(columns)], row))
            message_body = _pick_first_value(payload, TEXT_FIELDS)
            timestamp_raw = _pick_first_value(payload, TIMESTAMP_FIELDS)
            timestamp_iso = _safe_parse_timestamp(timestamp_raw)
            sender = _pick_first_value(payload, SENDER_FIELDS)
            receiver = _pick_first_value(payload, RECEIVER_FIELDS)
            conversation_id = _pick_first_value(payload, CONVERSATION_FIELDS)
            direction = _pick_first_value(payload, DIRECTION_FIELDS)
            message_type = _pick_first_value(payload, MESSAGE_TYPE_FIELDS)

            external_id = f"{db_path.name}:{table_name}:{payload.get('_rowid_')}"
            vector_id = None
            if message_body and message_body.strip():
                vector_id = f"msg:{external_id}"

            target_cursor.execute(
                """
                INSERT OR IGNORE INTO messages (
                    external_id,
                    conversation_id,
                    sender,
                    receiver,
                    timestamp,
                    body,
                    direction,
                    message_type,
                    attachments,
                    source,
                    raw_data,
                    vector_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_id,
                    conversation_id,
                    sender,
                    receiver,
                    timestamp_iso,
                    message_body,
                    direction,
                    message_type,
                    payload.get("attachments"),
                    str(db_path),
                    json.dumps(payload, default=_safe_json_default),
                    vector_id,
                ),
            )
            inserted = target_cursor.rowcount > 0
            if inserted:
                ingested += 1
            elif vector_id:
                target_cursor.execute(
                    """
                    UPDATE messages
                    SET vector_id = COALESCE(vector_id, ?)
                    WHERE external_id = ?
                    """,
                    (vector_id, external_id),
                )

            _register_message_with_graph(
                message_id=external_id,
                sender=sender,
                receiver=receiver,
                timestamp_iso=timestamp_iso,
                message_body=message_body,
                conversation_id=conversation_id,
                source=str(db_path),
                graph_stats=graph_stats,
            )

            if vector_id:
                metadata = {
                    "external_id": external_id,
                    "conversation_id": conversation_id or "",
                    "sender": sender or "",
                    "receiver": receiver or "",
                    "timestamp": timestamp_iso or "",
                    "source": str(db_path),
                    "table": table_name,
                }
                embedding_records.append(EmbeddingRecord(vector_id=vector_id, text=message_body, metadata=metadata))
        target_conn.commit()

    return ingested, embedding_records


def _ingest_contacts_from_table(
    connection: sqlite3.Connection,
    db_path: Path,
    table_name: str,
    columns: Sequence[str],
    graph_stats: GraphStats | None = None,
) -> int:
    cursor = connection.execute(f"SELECT rowid AS _rowid_, * FROM '{table_name}'")
    rows = cursor.fetchall()
    if not rows:
        return 0

    ingested = 0
    with get_connection() as target_conn:
        target_cursor = target_conn.cursor()
        for row in rows:
            payload = dict(zip([column.lower() for column in ["_rowid_"] + list(columns)], row))
            display_name = _pick_first_value(payload, ["display_name", "name", "full_name", "fullname"]) or _compose_display_name(payload)
            given_name = payload.get("first") or payload.get("given") or payload.get("firstname")
            family_name = payload.get("last") or payload.get("surname") or payload.get("lastname")
            phone_number = _pick_first_value(payload, ["phone", "phone_number", "number", "mobile", "msisdn", "home", "work"])
            email = _pick_first_value(payload, ["email", "email_address", "mail"])

            target_cursor.execute(
                """
                INSERT INTO contacts (
                    external_id,
                    display_name,
                    given_name,
                    family_name,
                    phone_number,
                    email,
                    source,
                    raw_data
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{db_path.name}:{table_name}:{payload.get('_rowid_')}",
                    display_name,
                    given_name,
                    family_name,
                    phone_number,
                    email,
                    str(db_path),
                    json.dumps(payload, default=_safe_json_default),
                ),
            )
            ingested += 1

            _register_contact_with_graph(
                display_name=display_name,
                given_name=given_name,
                family_name=family_name,
                phone_number=phone_number,
                email=email,
                source=str(db_path),
                graph_stats=graph_stats,
            )
        target_conn.commit()

    return ingested


def _register_contact_with_graph(
    *,
    display_name: Optional[str],
    given_name: Optional[str],
    family_name: Optional[str],
    phone_number: Optional[str],
    email: Optional[str],
    source: str,
    graph_stats: GraphStats | None,
) -> None:
    if not GRAPH_CLIENT.is_enabled():
        return

    identifiers: List[tuple[str, str]] = []
    for raw in (phone_number, email):
        canonical = canonicalize_actor(raw)
        if canonical:
            identifiers.append((canonical, raw or canonical))

    if not identifiers and display_name:
        canonical = canonicalize_actor(display_name)
        if canonical:
            identifiers.append((canonical, display_name))

    preferred_name = display_name or compose_display_name(given_name, family_name) or (identifiers[0][1] if identifiers else None)

    for canonical, raw in identifiers:
        success = GRAPH_CLIENT.register_person(
            identifier=canonical,
            display_name=preferred_name,
            given_name=given_name,
            family_name=family_name,
            raw_identifier=raw,
            source=source,
        )
        if success:
            if graph_stats is not None and canonical not in graph_stats.seen_contact_identifiers:
                graph_stats.seen_contact_identifiers.add(canonical)
                graph_stats.contacts_registered += 1
            alias_value = preferred_name or raw
            if alias_value:
                CONTACT_ALIAS_MAP[canonical] = alias_value


def _register_message_with_graph(
    *,
    message_id: str,
    sender: Optional[str],
    receiver: Optional[str],
    timestamp_iso: Optional[str],
    message_body: Optional[str],
    conversation_id: Optional[str],
    source: str,
    graph_stats: GraphStats | None,
) -> None:
    if not GRAPH_CLIENT.is_enabled():
        return

    sender_id = canonicalize_actor(sender)
    receiver_id = canonicalize_actor(receiver)

    if not sender_id or not receiver_id:
        return

    sender_label = CONTACT_ALIAS_MAP.get(sender_id) or sender or sender_id
    receiver_label = CONTACT_ALIAS_MAP.get(receiver_id) or receiver or receiver_id

    success = GRAPH_CLIENT.register_message(
        message_id=message_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        timestamp=timestamp_iso,
        body=message_body,
        conversation_id=conversation_id,
        sender_label=sender_label,
        receiver_label=receiver_label,
        source=source,
    )

    if success:
        if graph_stats is not None and message_id not in graph_stats.seen_message_ids:
            graph_stats.seen_message_ids.add(message_id)
            graph_stats.relationships_registered += 1
        CONTACT_ALIAS_MAP[sender_id] = sender_label
        CONTACT_ALIAS_MAP[receiver_id] = receiver_label


def _index_embeddings(records: Sequence[EmbeddingRecord]) -> None:
    if not records or not VECTOR_STORE.is_enabled():
        return

    texts = [record.text for record in records]
    embeddings = encode_texts(texts)
    if not embeddings:
        return

    ids = [record.vector_id for record in records]
    metadatas = [record.metadata for record in records]

    VECTOR_STORE.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)


def _pick_first_value(payload: Dict[str, object], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return str(payload[key])
    return None


def _compose_display_name(payload: Dict[str, object]) -> Optional[str]:
    parts = [payload.get("first"), payload.get("middle"), payload.get("last")]
    filtered = [str(part) for part in parts if part]
    return " ".join(filtered) if filtered else None


def _safe_parse_timestamp(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except ValueError:
            return str(value)
    else:
        # Heuristic: many mobile databases use seconds since 2001-01-01 (Apple epoch)
        APPLE_EPOCH_OFFSET = 978307200
        if numeric_value > 1e12:
            numeric_value /= 1000
        if numeric_value > APPLE_EPOCH_OFFSET:
            numeric_value -= APPLE_EPOCH_OFFSET
        try:
            parsed = datetime.fromtimestamp(numeric_value, tz=timezone.utc)
            return parsed.isoformat()
        except (OverflowError, ValueError):
            return str(value)


def _safe_json_default(value: object) -> object:
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return str(value)
