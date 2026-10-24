"""
Stage 1 Hybrid Retrieval using Reciprocal Rank Fusion (RRF).

Combines dense vector search (BGE embeddings in Qdrant) with lexical search
(BM25 with financial tokenization) into a single unified candidate pool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.retrieval.dense_search import QdrantVectorStore
from app.retrieval.lexical_search import BM25Index

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60


@dataclass
class HybridCandidate:
    """A candidate chunk resulting from hybrid dense + lexical retrieval."""

    chunk_id: str
    payload: dict[str, Any]
    rrf_score: float
    dense_score: float | None = None
    dense_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    retrieval_source: str = "hybrid"  # "hybrid" | "dense_only" | "bm25_only"


class HybridSearcher:
    """
    Executes dense and lexical retrieval in parallel and merges candidates via RRF.
    """

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        bm25_index: BM25Index,
        rrf_k: int = DEFAULT_RRF_K,
        dense_weight: float = 1.0,
        bm25_weight: float = 1.0,
    ) -> None:
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 50,
    ) -> list[HybridCandidate]:
        """
        Execute dense and BM25 searches and fuse results using Reciprocal Rank Fusion.

        Returns top_k fused candidates sorted by descending RRF score.
        """
        # Fetch candidate pools from both sources
        dense_hits = self.vector_store.search(query=query, filters=filters, top_k=top_k)
        bm25_hits = self.bm25_index.search(query=query, filters=filters, top_k=top_k)

        candidates_map: dict[str, HybridCandidate] = {}

        # 1. Process dense candidates (1-based rank)
        for rank, (payload, d_score) in enumerate(dense_hits, start=1):
            c_id = payload.get("chunk_id", f"unknown_dense_{rank}")
            rrf_contrib = self.dense_weight / (self.rrf_k + rank)
            candidates_map[c_id] = HybridCandidate(
                chunk_id=c_id,
                payload=payload,
                rrf_score=rrf_contrib,
                dense_score=d_score,
                dense_rank=rank,
                retrieval_source="dense_only",
            )

        # 2. Process BM25 candidates
        for rank, (payload, b_score) in enumerate(bm25_hits, start=1):
            c_id = payload.get("chunk_id", f"unknown_bm25_{rank}")
            rrf_contrib = self.bm25_weight / (self.rrf_k + rank)

            if c_id in candidates_map:
                cand = candidates_map[c_id]
                cand.rrf_score += rrf_contrib
                cand.bm25_score = b_score
                cand.bm25_rank = rank
                cand.retrieval_source = "hybrid"
            else:
                candidates_map[c_id] = HybridCandidate(
                    chunk_id=c_id,
                    payload=payload,
                    rrf_score=rrf_contrib,
                    bm25_score=b_score,
                    bm25_rank=rank,
                    retrieval_source="bm25_only",
                )

        # Sort descending by RRF score
        sorted_candidates = sorted(
            candidates_map.values(), key=lambda c: c.rrf_score, reverse=True
        )

        logger.debug(
            "Hybrid search query='%s': dense=%d, bm25=%d, fused=%d",
            query,
            len(dense_hits),
            len(bm25_hits),
            len(sorted_candidates),
        )

        return sorted_candidates[:top_k]
