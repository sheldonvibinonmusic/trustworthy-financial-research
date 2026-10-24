"""
Tests for structure-aware financial chunking.

Verifies:
1. Section heading detection
2. Financial table heading preservation
3. Unit detection (in millions, thousands, $, etc.)
4. Footnote detection and preservation
5. 1-based page numbers and sequence provenance
6. Document version and document ID propagation
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.document_parser import ParsedPage
from app.retrieval.chunking import StructureAwareChunker, TextChunk


def test_chunking_preserves_page_provenance_and_doc_id():
    pages = [
        ParsedPage(
            document_id="doc_abc123",
            filename="sample.pdf",
            page_number=1,
            text="Revenue Summary\nTotal revenue was $5,000,000 for fiscal 2024.",
        ),
        ParsedPage(
            document_id="doc_abc123",
            filename="sample.pdf",
            page_number=2,
            text="Risk Factors\nMarket risk is subject to macroeconomic fluctuation.",
        ),
    ]

    chunker = StructureAwareChunker(target_chunk_size=300)
    chunks = chunker.chunk_pages(
        pages=pages,
        document_id="doc_abc123",
        filename="sample.pdf",
        document_version="2.1",
        metadata={"company_name": "TestCorp"},
    )

    assert len(chunks) >= 2
    for c in chunks:
        assert c.document_id == "doc_abc123"
        assert c.filename == "sample.pdf"
        assert c.document_version == "2.1"
        assert c.metadata.get("company_name") == "TestCorp"
        assert c.page_number in {1, 2}
        assert c.total_chunks == len(chunks)

    # First chunk page 1, later chunk page 2
    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2


def test_chunking_detects_sections():
    pages = [
        ParsedPage(
            document_id="doc_001",
            filename="annual.pdf",
            page_number=1,
            text=(
                "Item 7. Management's Discussion and Analysis\n"
                "Operating revenue grew by 15% due to strong cloud adoption.\n"
                "Operating margins expanded by 200 bps.\n\n"
                "Note 2: Accounting Policies\n"
                "Revenue is recognized upon transfer of control to customers."
            ),
        )
    ]

    chunker = StructureAwareChunker(target_chunk_size=150)
    chunks = chunker.chunk_pages(pages, document_id="doc_001", filename="annual.pdf")

    sections = [c.section for c in chunks]
    assert any("Item 7" in s for s in sections)
    assert any("Note 2" in s for s in sections)


def test_chunking_preserves_table_headings_and_units():
    table_text = (
        "Statement of Operations\n"
        "(in millions, except per share amounts)\n"
        "Product Revenue: $3,200\n"
        "Service Revenue: $1,000\n"
        "Total Revenue: $4,200\n"
        "Operating Income: $840"
    )

    pages = [
        ParsedPage(
            document_id="doc_tbl",
            filename="financials.pdf",
            page_number=3,
            text=table_text,
        )
    ]

    chunker = StructureAwareChunker(target_chunk_size=400)
    chunks = chunker.chunk_pages(pages, document_id="doc_tbl", filename="financials.pdf")

    assert len(chunks) >= 1
    table_chunk = chunks[0]
    assert table_chunk.table_heading is not None
    assert "Statement of" in table_chunk.table_heading or "Operations" in table_chunk.table_heading
    assert table_chunk.units is not None
    assert "millions" in table_chunk.units.lower()


def test_chunking_preserves_footnotes():
    page_text = (
        "Revenue Summary\n"
        "North America: $2,500,000 (1)\n"
        "International: $1,700,000\n"
        "* Preliminary figures subject to final audit.\n"
        "(1) Includes deferred revenue adjustments."
    )

    pages = [
        ParsedPage(
            document_id="doc_fn",
            filename="report.pdf",
            page_number=4,
            text=page_text,
        )
    ]

    chunker = StructureAwareChunker(target_chunk_size=400)
    chunks = chunker.chunk_pages(pages, document_id="doc_fn", filename="report.pdf")

    assert len(chunks) >= 1
    c = chunks[0]
    assert len(c.footnotes) >= 1
    combined_fn = " ".join(c.footnotes)
    assert "Preliminary" in combined_fn or "Includes" in combined_fn or "*" in combined_fn
