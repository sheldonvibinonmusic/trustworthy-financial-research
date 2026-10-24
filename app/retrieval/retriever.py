"""
High-level two-stage hybrid retrieval interface.

Provides:
- index_documents(document_ids, ...)
- retrieve_evidence(query, filters, top_k=15)
- retrieve_counter_evidence(claim, filters, top_k=15)

Preserves:
- evidence_id, chunk_id, document_id, document_version, filename
- page_number (1-based), section
- table_heading, units, footnotes
- multi-feature rerank scores

Generates explicit warnings when evidence is missing or confidence is low.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from app.ingestion.registry import registry as default_registry
from app.retrieval.chunking import StructureAwareChunker, TextChunk
from app.retrieval.dense_search import QdrantVectorStore
from app.retrieval.embeddings import BGEEmbedder, default_embedder
from app.retrieval.hybrid_search import HybridSearcher
from app.retrieval.lexical_search import BM25Index
from app.retrieval.reranking import ContextExpanderAndReranker

if TYPE_CHECKING:
    from app.ingestion.document_parser import DocumentParseResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public Evidence Models (isolated from core-backend schemas until merge)
# ---------------------------------------------------------------------------


@dataclass
class EvidenceItem:
    """An individual piece of retrieved evidence with complete provenance."""

    evidence_id: str
    chunk_id: str
    document_id: str
    document_version: str
    filename: str
    page_number: int  # 1-based
    section: str
    text: str
    table_heading: str | None = None
    units: str | None = None
    footnotes: list[str] = field(default_factory=list)
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary matching the API contract evidence_items structure."""
        return {
            "evidence_id": self.evidence_id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_version": self.document_version,
            "filename": self.filename,
            "page_number": self.page_number,
            "section": self.section,
            "text": self.text,
            "table_heading": self.table_heading,
            "units": self.units,
            "footnotes": self.footnotes,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class RetrievalResult:
    """Outcome of an evidence retrieval query."""

    query: str
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_candidates: int = 0


# ---------------------------------------------------------------------------
# Retrieval Engine Core
# ---------------------------------------------------------------------------


class RetrievalEngine:
    """
    Two-stage hybrid retrieval engine coordinating chunking, BGE vector search,
    BM25 lexical search, RRF fusion, and context-expanded reranking.
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
        embedder: BGEEmbedder | None = None,
        chunker: StructureAwareChunker | None = None,
    ) -> None:
        self.embedder = embedder or default_embedder
        self.chunker = chunker or StructureAwareChunker()
        self.vector_store = QdrantVectorStore(
            storage_path=storage_path,
            embedder=self.embedder,
        )
        self.bm25_index = BM25Index()
        self.hybrid_searcher = HybridSearcher(
            vector_store=self.vector_store,
            bm25_index=self.bm25_index,
        )
        self.reranker = ContextExpanderAndReranker()

    def index_documents(
        self,
        document_ids: Sequence[str | DocumentParseResult] | None = None,
    ) -> dict[str, Any]:
        """
        Index parsed documents into dense Qdrant storage and lexical BM25 index.

        Parameters
        ----------
        document_ids:
            List of document IDs (str) or DocumentParseResult objects.
            If None or empty, all registered documents in the ingestion registry are indexed.

        Returns
        -------
        dict with indexing statistics and any warnings.
        """
        warnings: list[str] = []
        docs_to_index: list[DocumentParseResult] = []

        if not document_ids:
            docs_to_index = default_registry.list_all()
            if not docs_to_index:
                warnings.append("No documents found in ingestion registry to index.")
                return {
                    "status": "failed",
                    "indexed_documents": 0,
                    "indexed_chunks": 0,
                    "warnings": warnings,
                }
        else:
            for item in document_ids:
                if isinstance(item, str):
                    doc = default_registry.get(item)
                    if doc is None:
                        warnings.append(f"Document ID '{item}' not found in registry; skipping.")
                    else:
                        docs_to_index.append(doc)
                else:
                    docs_to_index.append(item)

        total_chunks: list[TextChunk] = []
        for doc in docs_to_index:
            if doc.status == "failed" or not doc.pages:
                warnings.append(
                    f"Document '{doc.filename}' ({doc.document_id}) has status '{doc.status}' "
                    "or empty pages; skipped indexing."
                )
                continue

            chunks = self.chunker.chunk_document(doc)
            total_chunks.extend(chunks)

        if not total_chunks:
            warnings.append("No text chunks generated from input documents.")
            return {
                "status": "failed",
                "indexed_documents": len(docs_to_index),
                "indexed_chunks": 0,
                "warnings": warnings,
            }

        # Index into Qdrant and BM25
        dense_count = self.vector_store.add_chunks(total_chunks)
        lexical_count = self.bm25_index.add_chunks(total_chunks)

        logger.info(
            "Indexed %d documents: %d dense points, %d lexical chunks",
            len(docs_to_index),
            dense_count,
            lexical_count,
        )

        return {
            "status": "indexed",
            "indexed_documents": len(docs_to_index),
            "indexed_chunks": len(total_chunks),
            "dense_points": dense_count,
            "lexical_chunks": lexical_count,
            "warnings": warnings,
        }

    def retrieve_evidence(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 15,
        min_confidence_score: float = 0.15,
    ) -> RetrievalResult:
        """
        Retrieve source evidence for a query through two-stage hybrid search.

        Stage 1: Dense + BM25 search merged via Reciprocal Rank Fusion.
        Stage 2: Context expansion (table headings, units, footnotes) and multi-feature reranking.

        Returns a RetrievalResult with explicit warnings if evidence is missing or weak.
        """
        warnings: list[str] = []
        stripped_query = query.strip()

        if not stripped_query:
            return RetrievalResult(
                query=query,
                evidence_items=[],
                warnings=["Query is empty; no evidence can be retrieved."],
                total_candidates=0,
            )

        if self.vector_store.get_chunk_count() == 0 and self.bm25_index.get_chunk_count() == 0:
            return RetrievalResult(
                query=query,
                evidence_items=[],
                warnings=[
                    "Index is empty. Ingest and index documents before retrieving evidence."
                ],
                total_candidates=0,
            )

        # Stage 1: Hybrid candidate generation
        candidates = self.hybrid_searcher.search(
            query=stripped_query,
            filters=filters,
            top_k=50,
        )

        if not candidates:
            msg = f"No candidate passages matched query: '{query}'"
            if filters:
                msg += f" with filters {filters}"
            warnings.append(msg)
            return RetrievalResult(
                query=query,
                evidence_items=[],
                warnings=warnings,
                total_candidates=0,
            )

        # Stage 2: Context expansion and reranking
        reranked = self.reranker.expand_and_rerank(
            query=stripped_query,
            candidates=candidates,
            top_k=top_k,
        )

        # Generate EvidenceItem objects with provenance
        evidence_items: list[EvidenceItem] = []
        for payload, score in reranked:
            ev_id = f"ev_{uuid.uuid4().hex[:12]}"
            item = EvidenceItem(
                evidence_id=ev_id,
                chunk_id=payload.get("chunk_id", ""),
                document_id=payload.get("document_id", ""),
                document_version=payload.get("document_version", "1.0"),
                filename=payload.get("filename", ""),
                page_number=int(payload.get("page_number", 1)),
                section=payload.get("section", "General"),
                text=payload.get("text", ""),
                table_heading=payload.get("table_heading"),
                units=payload.get("units"),
                footnotes=payload.get("footnotes", []),
                score=score,
                metadata=payload.get("metadata", {}),
            )
            evidence_items.append(item)

        # Confidence checks and warning generation
        top_score = evidence_items[0].score if evidence_items else 0.0
        if top_score < min_confidence_score:
            warnings.append(
                f"Low confidence: highest evidence relevance score is {top_score:.2f} "
                f"(threshold is {min_confidence_score:.2f}) for query: '{query}'."
            )

        return RetrievalResult(
            query=query,
            evidence_items=evidence_items,
            warnings=warnings,
            total_candidates=len(candidates),
        )

    def retrieve_counter_evidence(
        self,
        claim: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 15,
    ) -> RetrievalResult:
        """
        Retrieve potential counter-evidence, risk factors, or contradictory disclosures
        related to a claim.
        """
        # Formulate counter-evidence search query
        counter_query = (
            f"risks inconsistencies exceptions restatements decrease losses disputes: {claim}"
        )
        res = self.retrieve_evidence(
            query=counter_query,
            filters=filters,
            top_k=top_k,
        )
        if not res.evidence_items:
            res.warnings.append(f"No counter-evidence or contradictions identified for claim: '{claim}'.")
        return res


# ---------------------------------------------------------------------------
# Global default engine and public functions
# ---------------------------------------------------------------------------

_default_engine: RetrievalEngine | None = None


def get_default_engine() -> RetrievalEngine:
    """Lazy initialize the default retrieval engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = RetrievalEngine()
    return _default_engine


def index_documents(
    document_ids: Sequence[str | DocumentParseResult] | None = None,
    engine: RetrievalEngine | None = None,
) -> dict[str, Any]:
    """
    Index documents into the hybrid retrieval subsystem.

    Parameters
    ----------
    document_ids:
        List of document ID strings (looked up in ingestion registry) or
        DocumentParseResult instances. If None, indexes all registered documents.
    engine:
        Optional custom RetrievalEngine instance (defaults to global engine).
    """
    target_engine = engine or get_default_engine()
    return target_engine.index_documents(document_ids)


def retrieve_evidence(
    query: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 15,
    engine: RetrievalEngine | None = None,
) -> RetrievalResult:
    """
    Retrieve evidence for a research query with page-level provenance.

    Parameters
    ----------
    query:
        The research query or claim to substantiate.
    filters:
        Optional metadata filters (e.g. `{"document_id": "...", "company_name": "..."}`).
    top_k:
        Maximum number of passages to return (default 15).
    engine:
        Optional custom RetrievalEngine instance.
    """
    target_engine = engine or get_default_engine()
    return target_engine.retrieve_evidence(query=query, filters=filters, top_k=top_k)


def retrieve_counter_evidence(
    claim: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 15,
    engine: RetrievalEngine | None = None,
) -> RetrievalResult:
    """
    Retrieve counter-evidence, risk factors, or opposing disclosures for a claim.
    """
    target_engine = engine or get_default_engine()
    return target_engine.retrieve_counter_evidence(claim=claim, filters=filters, top_k=top_k)
