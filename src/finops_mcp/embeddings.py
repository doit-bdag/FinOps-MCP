"""Vertex AI text-embedding-005 client with lazy init and batching."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))

# Lazy-loaded model instance (minimizes Cloud Run cold start)
_model = None


def _get_model(project: str, location: str):
    """Lazily initialize the Vertex AI TextEmbeddingModel."""
    global _model
    if _model is None:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel

        vertexai.init(project=project, location=location)
        _model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        logger.info("Vertex AI text-embedding-005 model initialized")
    return _model


def get_embeddings(
    texts: list[str],
    project: str,
    location: str,
) -> list[list[float]]:
    """Embed a list of texts for document ingestion.

    Uses task_type=RETRIEVAL_DOCUMENT. Batches in chunks of 250
    (Vertex AI limit per request).
    """
    model = _get_model(project, location)
    embeddings: list[list[float]] = []
    batch_size = 250

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        results = model.get_embeddings(batch, task_type="RETRIEVAL_DOCUMENT")
        embeddings.extend([r.values for r in results])
        logger.info(
            "Embedded batch %d–%d of %d texts",
            i,
            min(i + batch_size, len(texts)),
            len(texts),
        )

    return embeddings


def get_query_embedding(
    query: str,
    project: str,
    location: str,
) -> list[float]:
    """Embed a single query for retrieval.

    Uses task_type=RETRIEVAL_QUERY for better retrieval quality.
    """
    model = _get_model(project, location)
    results = model.get_embeddings([query], task_type="RETRIEVAL_QUERY")
    return results[0].values
