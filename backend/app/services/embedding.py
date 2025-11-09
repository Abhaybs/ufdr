from __future__ import annotations

import importlib
import logging
from typing import Any, Sequence

from ..config import get_settings

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()
_EMBEDDER: Any | None = None


def get_embedder() -> Any:
    """Lazily load and cache the shared sentence-transformer embedder."""
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            module = importlib.import_module("sentence_transformers")
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "sentence_transformers is not installed. Install Phase 3 requirements before using embeddings."
            ) from exc

        SentenceTransformer = getattr(module, "SentenceTransformer")
        logger.info("Loading embedding model %s", _SETTINGS.embedding_model_name)
        _EMBEDDER = SentenceTransformer(_SETTINGS.embedding_model_name)
    return _EMBEDDER


def encode_texts(texts: Sequence[str]) -> list[list[float]]:
    """Encode text into vector embeddings using the shared model."""
    if not texts:
        return []

    embedder = get_embedder()
    embeddings = embedder.encode(
        list(texts),
        batch_size=_SETTINGS.embedding_batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    if hasattr(embeddings, "tolist"):
        embeddings = embeddings.tolist()
    return embeddings
