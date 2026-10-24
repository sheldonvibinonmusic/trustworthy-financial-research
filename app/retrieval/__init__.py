"""
app.retrieval
=============

Two-stage hybrid retrieval subsystem for financial research.

Public API::

    from app.retrieval import (
        index_documents,
        retrieve_evidence,
        retrieve_counter_evidence,
        EvidenceItem,
        RetrievalResult,
        TextChunk,
        StructureAwareChunker,
        BGEEmbedder,
        QdrantVectorStore,
        BM25Index,
        HybridSearcher,
        RetrievalEngine,
    )
"""

from app.retrieval.chunking import StructureAwareChunker, TextChunk
from app.retrieval.dense_search import QdrantVectorStore
from app.retrieval.embeddings import BGEEmbedder, default_embedder
from app.retrieval.hybrid_search import HybridCandidate, HybridSearcher
from app.retrieval.lexical_search import BM25Index, tokenize_financial
from app.retrieval.reranking import ContextExpanderAndReranker
from app.retrieval.retriever import (
    EvidenceItem,
    RetrievalEngine,
    RetrievalResult,
    get_default_engine,
    index_documents,
    retrieve_counter_evidence,
    retrieve_evidence,
)

__all__ = [
    "index_documents",
    "retrieve_evidence",
    "retrieve_counter_evidence",
    "EvidenceItem",
    "RetrievalResult",
    "TextChunk",
    "StructureAwareChunker",
    "BGEEmbedder",
    "default_embedder",
    "QdrantVectorStore",
    "BM25Index",
    "tokenize_financial",
    "HybridCandidate",
    "HybridSearcher",
    "ContextExpanderAndReranker",
    "RetrievalEngine",
    "get_default_engine",
]
