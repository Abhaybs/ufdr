from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from ..config import get_settings
from ..schemas.graph import GraphEdge, GraphNode, GraphResponse

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - neo4j optional for Phase 2+
    GraphDatabase = None  # type: ignore[assignment]


class GraphClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = bool(settings.neo4j_enabled)
        self._database = settings.neo4j_database
        self._driver = None

        if not self._enabled:
            logger.info("Neo4j integration disabled via settings")
            return

        if GraphDatabase is None:
            logger.warning("neo4j driver not installed; graph features disabled")
            self._enabled = False
            return

        try:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            self._ensure_constraints()
            logger.info("Connected to Neo4j at %s", settings.neo4j_uri)
        except Exception:  # pragma: no cover - connection failure
            logger.exception("Failed to initialize Neo4j driver; graph features disabled")
            self._driver = None
            self._enabled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_enabled(self) -> bool:
        return self._enabled and self._driver is not None

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()

    def clear_all(self) -> bool:
        if not self.is_enabled():
            return False

        def _tx(tx) -> None:
            tx.run("MATCH (n) DETACH DELETE n")

        try:
            assert self._driver is not None
            with self._driver.session(database=self._database) as session:
                session.execute_write(_tx)
            return True
        except Exception:  # pragma: no cover - runtime failure
            logger.exception("Failed to clear Neo4j database")
            return False

    def register_person(
        self,
        identifier: str,
        *,
        display_name: Optional[str] = None,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        raw_identifier: Optional[str] = None,
        source: Optional[str] = None,
    ) -> bool:
        if not self.is_enabled() or not identifier:
            return False

        params = {
            "id": identifier,
            "display_name": display_name,
            "given_name": given_name,
            "family_name": family_name,
            "raw_identifier": raw_identifier or identifier,
            "source": source,
        }

        def _tx(tx) -> None:
            tx.run(
                """
                MERGE (p:Person {id: $id})
                SET p.raw_identifier = coalesce(p.raw_identifier, $raw_identifier),
                    p.last_seen_source = $source
                SET p.display_name = CASE
                        WHEN $display_name IS NOT NULL AND (p.display_name IS NULL OR p.display_name = p.raw_identifier) THEN $display_name
                        ELSE p.display_name
                    END,
                    p.given_name = CASE
                        WHEN $given_name IS NOT NULL AND (p.given_name IS NULL OR p.given_name = '') THEN $given_name
                        ELSE p.given_name
                    END,
                    p.family_name = CASE
                        WHEN $family_name IS NOT NULL AND (p.family_name IS NULL OR p.family_name = '') THEN $family_name
                        ELSE p.family_name
                    END
                """,
                **params,
            )

        try:
            assert self._driver is not None
            with self._driver.session(database=self._database) as session:
                session.execute_write(_tx)
            return True
        except Exception:  # pragma: no cover - runtime failure
            logger.exception("Failed to register person %s in Neo4j", identifier)
            return False

    def register_message(
        self,
        *,
        message_id: str,
        sender_id: str,
        receiver_id: str,
        timestamp: Optional[str],
        body: Optional[str],
        conversation_id: Optional[str],
        sender_label: Optional[str] = None,
        receiver_label: Optional[str] = None,
        source: Optional[str] = None,
    ) -> bool:
        if not self.is_enabled():
            return False
        if not message_id or not sender_id or not receiver_id:
            return False

        params = {
            "message_id": message_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "timestamp": timestamp,
            "body": body,
            "conversation_id": conversation_id,
            "sender_label": sender_label or sender_id,
            "receiver_label": receiver_label or receiver_id,
            "source": source,
        }

        def _tx(tx) -> None:
            tx.run(
                """
                MERGE (sender:Person {id: $sender_id})
                SET sender.display_name = CASE
                        WHEN sender.display_name IS NULL AND $sender_label IS NOT NULL THEN $sender_label
                        ELSE sender.display_name
                    END,
                    sender.last_seen_source = $source
                MERGE (receiver:Person {id: $receiver_id})
                SET receiver.display_name = CASE
                        WHEN receiver.display_name IS NULL AND $receiver_label IS NOT NULL THEN $receiver_label
                        ELSE receiver.display_name
                    END,
                    receiver.last_seen_source = $source
                MERGE (sender)-[rel:MESSAGED {message_id: $message_id}]->(receiver)
                SET rel.timestamp = $timestamp,
                    rel.body = $body,
                    rel.conversation_id = $conversation_id,
                    rel.source = $source
                """,
                **params,
            )

        try:
            assert self._driver is not None
            with self._driver.session(database=self._database) as session:
                session.execute_write(_tx)
            return True
        except Exception:  # pragma: no cover - runtime failure
            logger.exception("Failed to register message %s in Neo4j", message_id)
            return False

    def fetch_person_graph(self, term: str, limit: int = 200) -> GraphResponse:
        if not self.is_enabled() or not term:
            return GraphResponse(focus=[], nodes=[], edges=[])

        term_lower = term.strip().lower()

        def _tx(tx) -> GraphResponse:
            centers_records = tx.run(
                """
                MATCH (p:Person)
                WHERE toLower(p.id) CONTAINS $term
                   OR toLower(coalesce(p.display_name, '')) CONTAINS $term
                RETURN DISTINCT p AS person
                """,
                term=term_lower,
            ).data()

            if not centers_records:
                return GraphResponse(focus=[], nodes=[], edges=[])

            center_nodes = [record["person"] for record in centers_records]
            center_ids = [node["id"] for node in center_nodes if "id" in node]

            relationship_records = tx.run(
                """
                MATCH (center:Person)-[rel:MESSAGED]->(other:Person)
                WHERE center.id IN $center_ids
                RETURN center AS center_node, rel, other AS other_node, 'outgoing' AS direction
                UNION ALL
                MATCH (center:Person)<-[rel:MESSAGED]-(other:Person)
                WHERE center.id IN $center_ids
                RETURN center AS center_node, rel, other AS other_node, 'incoming' AS direction
                LIMIT $limit
                """,
                center_ids=center_ids,
                limit=limit,
            )

            node_map: Dict[str, GraphNode] = {}
            edge_map: Dict[str, GraphEdge] = {}

            for node in center_nodes:
                node_id = node.get("id")
                if not node_id:
                    continue
                node_map[node_id] = _node_from_record(node, focus=True)

            for record in relationship_records:
                center_node = record["center_node"]
                other_node = record["other_node"]
                rel = record["rel"]
                direction = record["direction"]

                center_id = center_node.get("id") if center_node else None
                other_id = other_node.get("id") if other_node else None
                if not center_id or not other_id:
                    continue

                if center_id not in node_map:
                    node_map[center_id] = _node_from_record(center_node)
                if other_id not in node_map:
                    node_map[other_id] = _node_from_record(other_node)

                if direction == "outgoing":
                    source_id, target_id = center_id, other_id
                else:
                    source_id, target_id = other_id, center_id

                edge_id = rel.get("message_id") if hasattr(rel, "get") else None
                if not edge_id:
                    edge_id = f"{source_id}->{target_id}:{getattr(rel, 'id', 'rel')}"

                edge_data = _relationship_dict(rel)
                edge_data["direction"] = direction

                edge_map.setdefault(
                    edge_id,
                    GraphEdge(
                        id=str(edge_id),
                        source=str(source_id),
                        target=str(target_id),
                        label=_pick_edge_label(rel),
                        data=edge_data,
                    ),
                )

            focus_ids = [node_id for node_id, node in node_map.items() if node.data.get("focus")]
            return GraphResponse(
                focus=focus_ids,
                nodes=list(node_map.values()),
                edges=list(edge_map.values()),
            )

        try:
            assert self._driver is not None
            with self._driver.session(database=self._database) as session:
                return session.execute_read(_tx)
        except Exception:  # pragma: no cover - runtime failure
            logger.exception("Failed to fetch graph view for term '%s'", term)
            return GraphResponse(focus=[], nodes=[], edges=[])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_constraints(self) -> None:
        if self._driver is None:
            return

        def _tx(tx) -> None:
            tx.run(
                "CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE"
            )

        with self._driver.session(database=self._database) as session:
            session.execute_write(_tx)


def _node_from_record(node: Any, *, focus: bool = False) -> GraphNode:
    properties = dict(node)
    node_id = properties.get("id") or properties.get("raw_identifier") or properties.get("display_name")
    if node_id is None:
        node_id = "unknown"
    label = properties.get("display_name") or properties.get("raw_identifier") or node_id
    node_data = dict(properties)
    if focus:
        node_data["focus"] = True
    return GraphNode(
        id=str(node_id),
        label=str(label),
        group="person",
        title=properties.get("raw_identifier"),
        data=node_data,
    )


def _relationship_dict(rel: Any) -> Dict[str, Any]:
    if hasattr(rel, "items"):
        return dict(rel)
    try:
        return {"message_id": getattr(rel, "id", None)}
    except Exception:  # pragma: no cover - fallback
        return {}


@lru_cache(maxsize=1)
def get_graph_client() -> GraphClient:
    return GraphClient()


def _pick_edge_label(rel: Any) -> Optional[str]:
    if hasattr(rel, "get"):
        timestamp = rel.get("timestamp")
        if timestamp:
            return str(timestamp)
        conversation_id = rel.get("conversation_id")
        if conversation_id:
            return str(conversation_id)
    return None
