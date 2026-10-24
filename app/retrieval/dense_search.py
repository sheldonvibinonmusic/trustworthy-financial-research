"""
Persistent local Qdrant indexing and dense search.

Stores 384-dimensional BGE embeddings with full payload provenance:
- document_id, document_version, filename
- page_number, section
- table_heading, units, footnotes
- chunk_index, total_chunks, metadata
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.retrieval.embeddings import BGEEmbedder, default_embedder

if TYPE_CHECKING:
    from app.retrieval.chunking import TextChunk

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "financial_chunks"
DEFAULT_STORAGE_PATH = "./data/qdrant_storage"


class QdrantVectorStore:
    """
    Manages a persistent local Qdrant collection for dense retrieval.
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedder: BGEEmbedder | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.embedder = embedder or default_embedder
        self.storage_path = str(storage_path) if storage_path else DEFAULT_STORAGE_PATH

        if self.storage_path == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            path_obj = Path(self.storage_path)
            path_obj.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(path_obj))

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedder.dimension,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection: %s", self.collection_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not check/create Qdrant collection: %s", exc)

    def add_chunks(self, chunks: Sequence[TextChunk]) -> int:
        """Embed and upsert chunks into the Qdrant collection."""
        if not chunks:
            return 0

        texts = [chk.text for chk in chunks]
        embeddings = self.embedder.embed_documents(texts)

        points: list[PointStruct] = []
        for chk, emb in zip(chunks, embeddings):
            # Deterministic UUID from chunk_id ensures idempotent indexing
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chk.chunk_id))
            payload = chk.to_dict()
            points.append(
                PointStruct(
                    id=point_id,
                    vector=emb,
                    payload=payload,
                )
            )

        # Batch upsert
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("Indexed %d chunks in Qdrant (%s)", len(points), self.collection_name)
        return len(points)

    def search(
        self,
        query: str | list[float],
        filters: dict[str, Any] | None = None,
        top_k: int = 50,
    ) -> list[tuple[dict[str, Any], float]]:
        """
        Execute dense vector search against the Qdrant collection.

        Returns list of (payload, cosine_similarity_score).
        """
        if isinstance(query, str):
            if not query.strip():
                return []
            query_vector = self.embedder.embed_query(query)
        else:
            query_vector = query

        qdrant_filter = self._build_filter(filters)

        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
            )
            hits: list[tuple[dict[str, Any], float]] = []
            for pt in results.points:
                payload = pt.payload or {}
                hits.append((payload, float(pt.score)))
            return hits
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant query failed: %s", exc)
            return []

    def get_chunk_count(self) -> int:
        """Return the number of vectors stored in the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception:  # noqa: BLE001
            return 0

    def clear_collection(self) -> None:
        """Delete and re-create collection (for testing or re-indexing)."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:  # noqa: BLE001
            pass
        self._ensure_collection()

    def _build_filter(self, filters: dict[str, Any] | None) -> Filter | None:
        """Convert a dictionary of filters into a Qdrant Filter object."""
        if not filters:
            return None

        must_conditions: list[FieldCondition] = []
        for key, val in filters.items():
            if val is None:
                continue
            if isinstance(val, (list, tuple, set)):
                must_conditions.append(
                    FieldCondition(key=key, match=MatchAny(any=list(val)))
                )
            else:
                must_conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=val))
                )

        if not must_conditions:
            return None

        return Filter(must=must_conditions)
