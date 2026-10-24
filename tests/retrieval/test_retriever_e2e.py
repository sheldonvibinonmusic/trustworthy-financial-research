"""
End-to-end integration tests for Ingestion and Two-Stage Hybrid Retrieval.

Covers the full pipeline:
1. Ingest sample PDF with ingest_documents(paths, metadata)
2. Index into hybrid storage with index_documents(document_ids)
3. Retrieve evidence with retrieve_evidence(query, filters, top_k=15)
4. Verify page provenance, document IDs, versions, and evidence IDs
5. Verify warnings when query is empty, index is empty, or no evidence found
6. Verify counter-evidence retrieval for financial claims
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion import ingest_documents
from app.retrieval import (
    EvidenceItem,
    RetrievalEngine,
    index_documents,
    retrieve_counter_evidence,
    retrieve_evidence,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample_annual_report.pdf"


@pytest.fixture
def test_engine(tmp_path):
    """Create an isolated test RetrievalEngine with an in-memory/temp storage path."""
    return RetrievalEngine(storage_path=str(tmp_path / "qdrant_test"))


def test_full_pipeline_ingest_index_retrieve(test_engine):
    # 1. Ingest sample PDF
    meta = {"company_name": "Example Corp", "fiscal_year": 2024, "document_version": "1.0"}
    parse_results = ingest_documents([SAMPLE_PDF], metadata=meta)
    assert len(parse_results) == 1
    doc_res = parse_results[0]
    assert doc_res.status in {"uploaded", "uploaded_with_warnings"}
    assert len(doc_res.pages) == 3

    # 2. Index documents
    idx_res = index_documents([doc_res.document_id], engine=test_engine)
    assert idx_res["status"] == "indexed"
    assert idx_res["indexed_documents"] == 1
    assert idx_res["indexed_chunks"] >= 3

    # 3. Retrieve evidence for financial query
    query = "What is the Total Revenue and Net Income?"
    ret_res = retrieve_evidence(query=query, top_k=5, engine=test_engine)

    assert ret_res.query == query
    assert len(ret_res.evidence_items) >= 1
    assert ret_res.total_candidates > 0

    # 4. Validate complete provenance on EvidenceItem
    top_item: EvidenceItem = ret_res.evidence_items[0]
    assert top_item.evidence_id.startswith("ev_")
    assert top_item.chunk_id.startswith("chunk_")
    assert top_item.document_id == doc_res.document_id
    assert top_item.document_version == "1.0"
    assert top_item.filename == SAMPLE_PDF.name
    assert top_item.page_number in {1, 2, 3}
    assert top_item.score > 0.0
    assert len(top_item.text) > 0
    # Revenue data is on page 2 in the sample PDF fixture
    revenue_items = [ev for ev in ret_res.evidence_items if "$4,200,000" in ev.text or "Revenue" in ev.text]
    assert len(revenue_items) >= 1
    assert revenue_items[0].page_number == 2


def test_retrieval_with_metadata_filters(test_engine):
    meta = {"company_name": "Example Corp", "ticker": "EXMP"}
    parse_results = ingest_documents([SAMPLE_PDF], metadata=meta)
    doc_id = parse_results[0].document_id
    index_documents([doc_id], engine=test_engine)

    # Retrieval with matching filter
    matching = retrieve_evidence(
        query="operating income",
        filters={"company_name": "Example Corp"},
        engine=test_engine,
    )
    assert len(matching.evidence_items) >= 1

    # Retrieval with non-matching filter should return 0 items and a warning
    non_matching = retrieve_evidence(
        query="operating income",
        filters={"company_name": "Different Corp"},
        engine=test_engine,
    )
    assert len(non_matching.evidence_items) == 0
    assert len(non_matching.warnings) >= 1


def test_retrieval_missing_evidence_warnings(test_engine):
    # 1. Empty query warning
    empty_res = retrieve_evidence(query="", engine=test_engine)
    assert len(empty_res.evidence_items) == 0
    assert any("empty" in w.lower() for w in empty_res.warnings)

    # 2. Empty index warning (engine has no docs indexed yet)
    fresh_engine = RetrievalEngine(storage_path=":memory:")
    no_index_res = retrieve_evidence(query="unindexed query", engine=fresh_engine)
    assert len(no_index_res.evidence_items) == 0
    assert any("empty" in w.lower() for w in no_index_res.warnings)


def test_retrieve_counter_evidence(test_engine):
    meta = {"company_name": "Example Corp"}
    parse_results = ingest_documents([SAMPLE_PDF], metadata=meta)
    index_documents([parse_results[0].document_id], engine=test_engine)

    # Risk Factors are on page 3 of fixture
    claim = "Example Corp has no liquidity or market risks"
    counter_res = retrieve_counter_evidence(claim=claim, top_k=5, engine=test_engine)

    assert len(counter_res.evidence_items) >= 1
    # Check that risk factors section on page 3 is found
    risk_found = any("risk" in ev.text.lower() for ev in counter_res.evidence_items)
    assert risk_found
