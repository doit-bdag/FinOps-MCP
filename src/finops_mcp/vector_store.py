"""Firestore vector store — upsert, search, list, get, delete."""

from __future__ import annotations

import hashlib
import logging
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))

# Lazy-loaded Firestore client (minimizes cold start)
_db = None
_collection_ref = None


def _get_collection(collection_name: str):
    """Lazily initialize Firestore client and return the collection ref."""
    global _db, _collection_ref
    if _db is None:
        from google.cloud import firestore

        from finops_mcp import config

        _db = firestore.Client(database=config.FIRESTORE_DATABASE)
        logger.info("Firestore client initialized (database=%s)", config.FIRESTORE_DATABASE)
    if _collection_ref is None or _collection_ref.id != collection_name:
        _collection_ref = _db.collection(collection_name)
    return _collection_ref


def _make_doc_id(url: str, chunk_index: int) -> str:
    """Deterministic document ID: sha256(url + str(chunk_index))."""
    return hashlib.sha256(f"{url}{chunk_index}".encode()).hexdigest()


def upsert_chunk(chunk: dict[str, Any], collection_name: str) -> str:
    """Upsert a single chunk into Firestore with its embedding vector.

    The chunk dict must contain: url, title, section_header, chunk_index,
    text, embedding (list[float]).

    Returns the document ID.
    """
    from google.cloud.firestore_v1.vector import Vector

    collection = _get_collection(collection_name)
    doc_id = _make_doc_id(chunk["url"], chunk["chunk_index"])

    collection.document(doc_id).set(
        {
            "url": chunk["url"],
            "title": chunk["title"],
            "section_header": chunk.get("section_header", ""),
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
            "embedding": Vector(chunk["embedding"]),
            "crawled_at": datetime.now(timezone.utc),
        }
    )
    return doc_id


def search(
    query_embedding: list[float],
    collection_name: str,
    top_k: int = 5,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Vector similarity search using Firestore find_nearest (COSINE).

    Applies optional URL prefix filter post-query since Firestore vector
    search doesn't support composite filters with find_nearest.
    """
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
    from google.cloud.firestore_v1.vector import Vector

    collection = _get_collection(collection_name)

    # Fetch extra results if we need to filter
    fetch_limit = top_k * 3 if source_filter else top_k

    vector_query = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_embedding),
        distance_measure=DistanceMeasure.COSINE,
        limit=fetch_limit,
        distance_result_field="similarity_score",
    )

    results = []
    for doc in vector_query.get():
        data = doc.to_dict()
        # Remove the raw embedding from results
        data.pop("embedding", None)
        data["id"] = doc.id
        results.append(data)

    if source_filter:
        results = [r for r in results if r.get("url", "").startswith(source_filter)]

    return results[:top_k]


def list_sources(
    collection_name: str,
    limit: int = 20,
    offset: int = 0
) -> dict[str, Any]:
    """List unique source URLs with pagination.
    
    Returns a dictionary conforming to standard pagination metadata:
    total, count, offset, items, has_more, next_offset.
    """
    collection = _get_collection(collection_name)

    # Fetch all docs (url, title, crawled_at) — no embedding to save bandwidth
    docs = collection.select(["url", "title", "crawled_at"]).stream()

    sources: dict[str, dict[str, Any]] = {}
    for doc in docs:
        data = doc.to_dict()
        url = data.get("url", "")
        if url not in sources:
            sources[url] = {
                "url": url,
                "title": data.get("title", ""),
                "chunk_count": 0,
                "crawled_at": data.get("crawled_at"),
            }
        sources[url]["chunk_count"] += 1

    distinct_sources = sorted(sources.values(), key=lambda x: x["url"])
    total = len(distinct_sources)
    sliced = distinct_sources[offset : offset + limit]
    
    return {
        "total": total,
        "count": len(sliced),
        "offset": offset,
        "items": sliced,
        "has_more": total > (offset + limit),
        "next_offset": offset + limit if total > (offset + limit) else None
    }


def get_page(url: str, collection_name: str) -> dict[str, Any] | None:
    """Reconstruct a full page from its chunks, ordered by chunk_index."""
    collection = _get_collection(collection_name)

    docs = (
        collection.where("url", "==", url)
        .order_by("chunk_index")
        .select(["url", "title", "text", "chunk_index", "crawled_at"])
        .stream()
    )

    chunks = [doc.to_dict() for doc in docs]
    if not chunks:
        return None

    return {
        "url": url,
        "title": chunks[0].get("title", ""),
        "full_text": "\n\n".join(c["text"] for c in chunks),
        "chunk_count": len(chunks),
        "crawled_at": chunks[0].get("crawled_at"),
    }


def url_exists(url: str, collection_name: str) -> bool:
    """Check if any chunk for a given URL already exists in Firestore."""
    collection = _get_collection(collection_name)
    docs = collection.where("url", "==", url).limit(1).stream()
    return any(True for _ in docs)


def delete_collection(collection_name: str, batch_size: int = 500) -> int:
    """Delete all documents in the collection. Returns count deleted."""
    collection = _get_collection(collection_name)
    deleted = 0

    while True:
        docs = list(collection.limit(batch_size).stream())
        if not docs:
            break
        for doc in docs:
            doc.reference.delete()
            deleted += 1
        logger.info("Deleted %d documents so far...", deleted)

    return deleted


def collection_is_empty(collection_name: str) -> bool:
    """Check if the collection has any documents."""
    collection = _get_collection(collection_name)
    docs = collection.limit(1).stream()
    return not any(True for _ in docs)


# ── Structured document helpers (non-vector) ─────────────────────────────────


def upsert_structured_doc(
    doc: dict[str, Any], collection_name: str, doc_id: str
) -> str:
    """Upsert a structured document (no embedding vector) by explicit ID."""
    from datetime import datetime, timezone

    collection = _get_collection(collection_name)
    doc["updated_at"] = datetime.now(timezone.utc)
    collection.document(doc_id).set(doc)
    return doc_id


def get_structured_doc(doc_id: str, collection_name: str) -> dict[str, Any] | None:
    """Get a structured document by its ID."""
    collection = _get_collection(collection_name)
    doc = collection.document(doc_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None


def search_structured(
    field: str, value: str, collection_name: str
) -> list[dict[str, Any]]:
    """Exact match query on a field in a structured collection."""
    collection = _get_collection(collection_name)
    docs = collection.where(field, "==", value).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results


def list_structured_docs(
    collection_name: str, limit: int = 100
) -> list[dict[str, Any]]:
    """List all documents in a structured collection."""
    collection = _get_collection(collection_name)
    docs = collection.limit(limit).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results


def fuzzy_search_structured(
    field: str, query: str, collection_name: str
) -> list[dict[str, Any]]:
    """Case-insensitive search using a lowercase_name field convention.

    Documents should store a ``lowercase_<field>`` field for fuzzy matching.
    This performs a Firestore range query that acts as a prefix search.
    """
    collection = _get_collection(collection_name)
    lower_field = f"lowercase_{field}"
    lower_query = query.lower().strip()

    docs = (
        collection.where(lower_field, ">=", lower_query)
        .where(lower_field, "<=", lower_query + "\uf8ff")
        .stream()
    )
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results
