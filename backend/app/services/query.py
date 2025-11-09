from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Tuple

from fastapi import HTTPException, status

from ..config import get_settings
from ..schemas.query import EvidenceItem, QueryRequest, QueryResponse
from .llm import get_gemini_client
from .vector_store import get_vector_store

logger = logging.getLogger(__name__)
_SETTINGS = get_settings()


def _normalize_metadata(raw: Dict[str, object] | None) -> Dict[str, str]:
    if not raw:
        return {}
    normalized: Dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        normalized[key] = str(value)
    return normalized


def _build_context_sections(evidence: List[EvidenceItem]) -> List[str]:
    sections: List[str] = []
    for item in evidence:
        metadata_str = ", ".join(f"{k}: {v}" for k, v in item.metadata.items())
        header = f"Evidence {item.id} (score={item.score:.4f})" if item.score is not None else f"Evidence {item.id}"
        section = f"{header}\n{item.text.strip()}"
        if metadata_str:
            section += f"\nMetadata: {metadata_str}"
        sections.append(section)
    return sections


def _build_conversation(turns: Iterable[Tuple[str, str]] | None) -> List[Tuple[str, str]]:
    if not turns:
        return []
    sequence: List[Tuple[str, str]] = []
    for role, message in turns:
        if not message:
            continue
        sequence.append((role, message))
    return sequence


def run_query(payload: QueryRequest) -> QueryResponse:
    if not _SETTINGS.vector_store_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vector store is disabled")
    if not _SETTINGS.gemini_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gemini integration is not configured")

    store = get_vector_store()
    if not store.is_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vector store is not initialized")

    top_k = payload.top_k or _SETTINGS.query_default_top_k
    top_k = max(1, min(top_k, 20))

    filters = payload.filters or None
    try:
        results = store.similarity_search(payload.question, n_results=top_k, where=filters)
    except RuntimeError as exc:
        logger.exception("Vector search failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    ids_list = (results.get("ids") or [[]])[0]
    scores_list = (results.get("distances") or [[]])[0]
    documents_list = (results.get("documents") or [[]])[0]
    metadatas_list = (results.get("metadatas") or [[]])[0]

    evidence_items: List[EvidenceItem] = []
    for idx, doc in enumerate(documents_list):
        if not doc:
            continue
        evidence_id = ids_list[idx] if idx < len(ids_list) else f"evidence-{idx}"
        score = scores_list[idx] if idx < len(scores_list) else None
        if score is not None:
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = None
        metadata = _normalize_metadata(metadatas_list[idx] if idx < len(metadatas_list) else None)
        evidence_items.append(
            EvidenceItem(
                id=evidence_id,
                text=doc,
                score=score,
                metadata=metadata,
            )
        )

    context_sections = _build_context_sections(evidence_items)

    conversation_turns = None
    if payload.conversation:
        conversation_turns = _build_conversation([(turn.role, turn.content) for turn in payload.conversation])

    try:
        gemini_client = get_gemini_client()
        answer = gemini_client.generate_answer(
            question=payload.question,
            context_sections=context_sections,
            conversation=conversation_turns,
        )
    except RuntimeError as exc:
        logger.exception("Gemini generation failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    response = QueryResponse(
        answer=answer,
        evidence=evidence_items,
        model=gemini_client.model_name(),
    )
    return response
