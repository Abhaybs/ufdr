from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, constr


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant", "system"] = Field(..., description="Speaker role for multi-turn context")
    content: constr(strip_whitespace=True, min_length=1)


class QueryRequest(BaseModel):
    question: constr(strip_whitespace=True, min_length=1)
    filters: Optional[Dict[str, str]] = Field(default=None, description="Optional metadata filters for vector search")
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    conversation: Optional[List[ConversationTurn]] = Field(
        default=None,
        description="Optional prior conversation history for the LLM",
    )


class EvidenceItem(BaseModel):
    id: str
    text: str
    score: Optional[float] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str
    evidence: List[EvidenceItem]
    model: str
