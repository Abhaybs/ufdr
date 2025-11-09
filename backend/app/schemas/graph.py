from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    group: str = "person"
    title: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    focus: List[str]
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class GraphMaintenanceResponse(BaseModel):
    success: bool
    detail: Optional[str] = None
    cleared: bool = False
    contacts_synced: int = 0
    relationships_synced: int = 0
    skipped_contacts: int = 0
    skipped_messages: int = 0
