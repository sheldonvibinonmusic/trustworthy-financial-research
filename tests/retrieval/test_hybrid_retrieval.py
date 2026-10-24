"""
Tests for Stage 1 and Stage 2 Hybrid Retrieval components:
- Persistent local / in-memory QdrantVectorStore
- BM25Index with financial tokenization
- HybridSearcher (Reciprocal Rank Fusion)
- ContextExpanderAndReranker (Context expansion & multi-feature reranking)
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.chunking import TextChunk
from app.retrieval.dense_search import QdrantVectorStore
from app.retrieval.hybrid_search import HybridSearcher
from app.retrieval.lexical_search import BM25Index, tokenize_financial
from app.retrieval.reranking import ContextExpanderAndReranker


def _sample_chunks() -> list[TextChunk]:
    return [
        TextChunk(
            chunk_id="chk_rev",
            document_id="doc_101",
            document_version="1.0",
            filename="report.pdf",
            page_number=1,
            section="Financial Performance",
            text="Total revenue was $4,200,000, representing an increase of 12% over 2023.",
            table_heading="Consolidated Revenues",
            units="$ in thousands",
            footnotes=["(1) Reflects restated segment data."],
            metadata={"company_name": "Acme Corp", "year": 2024},
        ),
        TextChunk(
            chunk_id="chk_debt",
            document_id="doc_101",
            document_version="1.0",
            filename="report.pdf",
            page_number=2,
            section="Liquidity and Capital Resources",
            text="Long term debt increased to $1,500,000 with a weighted average interest rate of 4.5%.",
            table_heading="Debt Obligations",
            units="$ in thousands",
            footnotes=[],
            metadata={"company_name": "Acme Corp", "year": 2024},
        ),
        TextChunk(
            chunk_id="chk_risk",
            document_id="doc_102",
            document_version="1.0",
            filename="competitor.pdf",
            page_number=1,
            section="Risk Factors",
            text="Macroeconomic volatility and interest rate changes may materially reduce liquidity.",
            table_heading=None,
            units=None,
            footnotes=[],
            metadata={"company_name": "Beta Inc", "year": 2024},
        ),
    ]


def test_qdrant_vector_store_in_memory_and_filter():
    store = QdrantVectorStore(storage_path=":memory:", collection_name="test_dense")
    chunks = _sample_chunks()
    count = store.add_chunks(chunks)
    assert count == 3
    assert store.get_chunk_count() == 3

    # Search without filter
    hits = store.search("total revenue growth", top_k=5)
    assert len(hits) >= 1
    assert any("revenue" in h[0]["text"].lower() for h in hits)

    # Search with document filter
    filtered_hits = store.search(
        "liquidity and debt",
        filters={"document_id": "doc_102"},
        top_k=5,
    )
    assert len(filtered_hits) >= 1
    for payload, _ in filtered_hits:
        assert payload["document_id"] == "doc_102"


def test_bm25_lexical_search_and_financial_tokens():
    tokens = tokenize_financial("Revenue of $4,200,000 grew by 15.5% in FY2024.")
    assert "$4,200,000" in tokens or "4,200,000" in tokens
    assert "15.5%" in tokens or "15.5" in tokens
    assert "fy2024" in tokens

    bm25 = BM25Index()
    bm25.add_chunks(_sample_chunks())
    assert bm25.get_chunk_count() == 3

    # Search exact dollar amount
    results = bm25.search("$4,200,000", top_k=2)
    assert len(results) >= 1
    top_payload, top_score = results[0]
    assert top_payload["chunk_id"] == "chk_rev"
    assert top_score > 0.0


def test_hybrid_searcher_reciprocal_rank_fusion():
    store = QdrantVectorStore(storage_path=":memory:", collection_name="test_rrf")
    bm25 = BM25Index()
    chunks = _sample_chunks()
    store.add_chunks(chunks)
    bm25.add_chunks(chunks)

    searcher = HybridSearcher(vector_store=store, bm25_index=bm25)
    fused = searcher.search(query="long term debt interest rate", top_k=3)

    assert len(fused) >= 1
    top_cand = fused[0]
    # The debt chunk should rank highest for this query
    assert top_cand.chunk_id == "chk_debt"
    assert top_cand.rrf_score > 0.0
    assert top_cand.retrieval_source in {"hybrid", "dense_only", "bm25_only"}


def test_context_expansion_and_reranking():
    store = QdrantVectorStore(storage_path=":memory:", collection_name="test_rerank")
    bm25 = BM25Index()
    chunks = _sample_chunks()
    store.add_chunks(chunks)
    bm25.add_chunks(chunks)

    searcher = HybridSearcher(vector_store=store, bm25_index=bm25)
    candidates = searcher.search(query="What was Acme Corp total revenue in 2024?", top_k=5)

    reranker = ContextExpanderAndReranker()
    reranked = reranker.expand_and_rerank(
        query="What was Acme Corp total revenue in 2024?",
        candidates=candidates,
        top_k=5,
    )

    assert len(reranked) >= 1
    top_payload, top_score = reranked[0]
    assert top_payload["chunk_id"] == "chk_rev"

    # Verify context reconstruction: table heading, units, footnotes must be in the expanded text
    expanded_text = top_payload["text"]
    assert "Consolidated Revenues" in expanded_text
    assert "$ in thousands" in expanded_text
    assert "Reflects restated segment data" in expanded_text
