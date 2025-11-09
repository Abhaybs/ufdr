from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Iterable, Sequence

import chromadb
from chromadb import PersistentClient
from chromadb.api import Collection
from chromadb.config import Settings as ChromaSettings

try:
    import posthog  # type: ignore
except Exception:  # pragma: no cover - posthog is optional
    posthog = None  # type: ignore

from ..config import get_settings
from .embedding import encode_texts

logger = logging.getLogger(__name__)


def _patch_posthog_capture() -> None:
    """Adapt modern posthog signature to what Chroma expects."""
    if posthog is None:
        return
    try:
        capture = getattr(posthog, "capture")
        signature = inspect.signature(capture)
        positional_required = [
            p
            for p in signature.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            and p.default is inspect._empty
        ]
        if len(positional_required) > 1:
            return

        if getattr(posthog, "api_key", None) in (None, ""):
            project_key = getattr(posthog, "project_api_key", "") or "disabled"
            setattr(posthog, "api_key", project_key)

        def _legacy_capture(distinct_id: str, event: str, properties: dict | None = None, **kwargs) -> object:
            payload = {"distinct_id": distinct_id, **kwargs}
            if properties is not None:
                payload["properties"] = properties
            return capture(event, **payload)

        setattr(posthog, "capture", _legacy_capture)
    except Exception:  # pragma: no cover - defensive guard
        logger.debug("Skipping posthog capture patch", exc_info=True)


_patch_posthog_capture()


class VectorStore:
    """Wrapper around ChromaDB persistence for UFDR content."""

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.vector_store_enabled:
            self._client: PersistentClient | None = None
            self._collection: Collection | None = None
            return

        persist_dir: Path = self._settings.vector_store_dir
        persist_dir.mkdir(parents=True, exist_ok=True)

        db_settings = ChromaSettings(
            is_persistent=True,
            persist_directory=str(persist_dir),
            anonymized_telemetry=False,  # disable background telemetry to avoid noisy stderr
        )
        logger.info("Initializing ChromaDB client at %s", persist_dir)
        self._client = chromadb.PersistentClient(path=str(persist_dir), settings=db_settings)
        self._collection = self._client.get_or_create_collection(name=self._settings.vector_collection_name)

    def is_enabled(self) -> bool:
        return bool(self._collection)

    def collection(self) -> Collection:
        if not self._collection:
            raise RuntimeError("Vector store is disabled")
        return self._collection

    def upsert(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, str]] | None = None,
        documents: Sequence[str] | None = None,
    ) -> None:
        if not self.is_enabled():
            return
        self.collection().upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def delete(self, ids: Iterable[str]) -> None:
        if not self.is_enabled():
            return
        # Chroma API expects a list; convert iterables to list explicitly
        id_list = list(ids)
        if not id_list:
            return
        self.collection().delete(ids=id_list)

    def query(self, query_embeddings: Sequence[Sequence[float]], n_results: int = 10) -> dict:
        if not self.is_enabled():
            raise RuntimeError("Vector store is disabled")
        return self.collection().query(query_embeddings=query_embeddings, n_results=n_results)

    def similarity_search(
        self,
        query: str,
        *,
        n_results: int = 5,
        where: dict[str, object] | None = None,
    ) -> dict:
        if not self.is_enabled():
            raise RuntimeError("Vector store is disabled")
        embeddings = encode_texts([query])
        if not embeddings:
            return {"ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]}
        return self.collection().query(
            query_embeddings=embeddings,
            n_results=n_results,
            where=where,
        )


VECTOR_STORE = VectorStore()


def get_vector_store() -> VectorStore:
    return VECTOR_STORE
