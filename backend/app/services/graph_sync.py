from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..db import get_connection
from ..services.graph import get_graph_client
from ..utils.graph import canonicalize_actor, compose_display_name

logger = logging.getLogger(__name__)


@dataclass
class GraphResyncStats:
    cleared: bool = False
    contacts_synced: int = 0
    relationships_synced: int = 0
    skipped_contacts: int = 0
    skipped_messages: int = 0
    detail: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return {
            "cleared": self.cleared,
            "contacts_synced": self.contacts_synced,
            "relationships_synced": self.relationships_synced,
            "skipped_contacts": self.skipped_contacts,
            "skipped_messages": self.skipped_messages,
            "detail": self.detail,
            "success": self.detail is None,
        }

def reset_graph() -> GraphResyncStats:
    client = get_graph_client()
    stats = GraphResyncStats()
    if not client.is_enabled():
        stats.detail = "Neo4j integration is disabled"
        return stats

    stats.cleared = client.clear_all()
    if not stats.cleared:
        stats.detail = "Failed to clear Neo4j graph"
    return stats

def resync_graph(clear_first: bool = False) -> GraphResyncStats:
    client = get_graph_client()
    stats = GraphResyncStats()
    if not client.is_enabled():
        stats.detail = "Neo4j integration is disabled"
        return stats

    if clear_first:
        stats.cleared = client.clear_all()
        if not stats.cleared:
            stats.detail = "Failed to clear Neo4j graph"
            return stats

    alias_map: Dict[str, str] = {}
    seen_contacts: set[str] = set()

    try:
        with get_connection(readonly=True) as conn:
            cursor = conn.cursor()

            for row in cursor.execute(
                """
                SELECT display_name, given_name, family_name, phone_number, email, source
                FROM contacts
                """
            ):
                display_name, given_name, family_name, phone_number, email, source = row
                identifiers: List[Tuple[str, str]] = []
                for raw in (phone_number, email):
                    canonical = canonicalize_actor(raw)
                    if canonical:
                        identifiers.append((canonical, raw or canonical))

                if not identifiers:
                    composed = display_name or compose_display_name(given_name, family_name)
                    canonical = canonicalize_actor(composed)
                    if canonical:
                        identifiers.append((canonical, composed or canonical))

                if not identifiers:
                    stats.skipped_contacts += 1
                    continue

                preferred_name = display_name or compose_display_name(given_name, family_name) or identifiers[0][1]

                for canonical, raw in identifiers:
                    if canonical in seen_contacts:
                        alias_map[canonical] = preferred_name or raw
                        continue
                    success = client.register_person(
                        identifier=canonical,
                        display_name=preferred_name,
                        given_name=given_name,
                        family_name=family_name,
                        raw_identifier=raw,
                        source=source,
                    )
                    if success:
                        seen_contacts.add(canonical)
                        alias_map[canonical] = preferred_name or raw
                        stats.contacts_synced += 1
                    else:
                        stats.skipped_contacts += 1

            for row in cursor.execute(
                """
                SELECT external_id, sender, receiver, timestamp, body, conversation_id, source
                FROM messages
                """
            ):
                message_id, sender, receiver, timestamp, body, conversation_id, source = row
                sender_id = canonicalize_actor(sender)
                receiver_id = canonicalize_actor(receiver)
                if not sender_id or not receiver_id:
                    stats.skipped_messages += 1
                    continue

                sender_label = alias_map.get(sender_id) or sender
                receiver_label = alias_map.get(receiver_id) or receiver

                success = client.register_message(
                    message_id=message_id,
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    timestamp=timestamp,
                    body=body,
                    conversation_id=conversation_id,
                    sender_label=sender_label,
                    receiver_label=receiver_label,
                    source=source,
                )
                if success:
                    stats.relationships_synced += 1
                    alias_map.setdefault(sender_id, sender_label)
                    alias_map.setdefault(receiver_id, receiver_label)
                else:
                    stats.skipped_messages += 1

    except Exception as exc:  # pragma: no cover - operational failure
        logger.exception("Failed during Neo4j resync")
        stats.detail = str(exc)

    return stats
