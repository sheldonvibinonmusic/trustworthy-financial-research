"""
tests/ingestion/test_pdf_parser.py
===================================
Milestone 1 tests for PDF ingestion.

Verified by running: python -m pytest tests/ingestion/test_pdf_parser.py -v

Test cases
----------
1.  validate_pdf: real PDF → valid.
2.  validate_pdf: non-PDF file → invalid, meaningful reason.
3.  validate_pdf: non-existent path → invalid.
4.  validate_pdf: zero-byte file → invalid (no magic bytes).
5.  ingest_documents: real PDF → status "uploaded" or "uploaded_with_warnings".
6.  ingest_documents: page count matches actual PDF page count.
7.  ingest_documents: every page carries correct document_id and filename.
8.  ingest_documents: page numbers are 1-based and sequential.
9.  ingest_documents: document_id is unique across two separate calls.
10. ingest_documents: non-PDF file → status "failed", pages list empty.
11. ingest_documents: caller metadata is echoed in result.metadata.
12. ingest_documents: source_path is present in result.metadata.
13. ingest_documents: mixed valid/invalid list → both results returned.
14. ingest_documents: extracted text contains expected content from page 1.
15. ingest_documents: parser_used field is non-empty on success.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path when running without pip install.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.file_validation import validate_pdf
from app.ingestion.document_parser import ingest_documents

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample_annual_report.pdf"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_pdf(tmp_path: Path, name: str = "fake.pdf") -> Path:
    """Write a file that has a .pdf extension but is not a valid PDF."""
    p = tmp_path / name
    p.write_text("This is definitely not a PDF file.", encoding="utf-8")
    return p


def _make_empty_file(tmp_path: Path, name: str = "empty.pdf") -> Path:
    p = tmp_path / name
    p.write_bytes(b"")
    return p


# ===========================================================================
# 1-4: validate_pdf unit tests
# ===========================================================================


def test_validate_real_pdf_is_valid():
    """A genuine PDF fixture must pass validation."""
    result = validate_pdf(SAMPLE_PDF)
    assert result.is_valid, f"Expected valid PDF, got reason: {result.reason}"
    assert result.reason == ""


def test_validate_non_pdf_is_invalid(tmp_path):
    """A text file masquerading as PDF must be rejected."""
    fake = _make_fake_pdf(tmp_path)
    result = validate_pdf(fake)
    assert not result.is_valid
    assert result.reason != ""
    # Reason must mention the magic-byte problem, not be a generic fallback.
    assert "PDF" in result.reason or "magic" in result.reason or "Not" in result.reason


def test_validate_missing_path_is_invalid():
    """A non-existent path must return is_valid=False."""
    result = validate_pdf(Path("/this/path/does/not/exist.pdf"))
    assert not result.is_valid
    assert "not found" in result.reason.lower() or "no such" in result.reason.lower()


def test_validate_empty_file_is_invalid(tmp_path):
    """A zero-byte file must fail magic-byte check."""
    empty = _make_empty_file(tmp_path)
    result = validate_pdf(empty)
    assert not result.is_valid


# ===========================================================================
# 5-15: ingest_documents integration tests
# ===========================================================================


def test_ingest_real_pdf_status_is_not_failed():
    """Parsing the sample PDF must not produce status='failed'."""
    results = ingest_documents([SAMPLE_PDF])
    assert len(results) == 1
    r = results[0]
    assert r.status in {"uploaded", "uploaded_with_warnings"}, (
        f"Unexpected status '{r.status}'. Warnings: {r.warnings}"
    )


def test_ingest_real_pdf_page_count():
    """Parsed page count must match the fixture (3 pages)."""
    results = ingest_documents([SAMPLE_PDF])
    r = results[0]
    assert len(r.pages) == 3, (
        f"Expected 3 pages, got {len(r.pages)}. Status: {r.status}, Warnings: {r.warnings}"
    )


def test_ingest_pages_carry_document_id_and_filename():
    """Every ParsedPage must reference its parent document_id and filename."""
    results = ingest_documents([SAMPLE_PDF])
    r = results[0]
    for pg in r.pages:
        assert pg.document_id == r.document_id
        assert pg.filename == SAMPLE_PDF.name


def test_ingest_page_numbers_are_one_based_and_sequential():
    """Page numbers must start at 1 and increase by 1 per page."""
    results = ingest_documents([SAMPLE_PDF])
    r = results[0]
    page_nums = [pg.page_number for pg in r.pages]
    assert page_nums == list(range(1, len(r.pages) + 1)), (
        f"Page numbers not sequential: {page_nums}"
    )


def test_ingest_document_id_is_unique_across_calls():
    """Two separate ingest_documents calls must produce different document_ids."""
    r1 = ingest_documents([SAMPLE_PDF])[0]
    r2 = ingest_documents([SAMPLE_PDF])[0]
    assert r1.document_id != r2.document_id


def test_ingest_invalid_pdf_status_is_failed(tmp_path):
    """A non-PDF file must produce status='failed' with empty pages."""
    fake = _make_fake_pdf(tmp_path)
    results = ingest_documents([fake])
    assert len(results) == 1
    r = results[0]
    assert r.status == "failed"
    assert r.pages == []
    assert len(r.warnings) > 0


def test_ingest_caller_metadata_is_echoed():
    """Caller-supplied metadata must appear in result.metadata."""
    meta = {"company_name": "Example Corp", "document_type": "annual_report"}
    results = ingest_documents([SAMPLE_PDF], metadata=meta)
    r = results[0]
    assert r.metadata.get("company_name") == "Example Corp"
    assert r.metadata.get("document_type") == "annual_report"


def test_ingest_source_path_in_metadata():
    """result.metadata must contain 'source_path' pointing to the file."""
    results = ingest_documents([SAMPLE_PDF])
    r = results[0]
    assert "source_path" in r.metadata
    assert Path(r.metadata["source_path"]).exists()


def test_ingest_mixed_list_returns_both_results(tmp_path):
    """ingest_documents must return one result per input path, including failures."""
    fake = _make_fake_pdf(tmp_path)
    results = ingest_documents([SAMPLE_PDF, fake])
    assert len(results) == 2
    statuses = {r.filename: r.status for r in results}
    assert statuses[SAMPLE_PDF.name] in {"uploaded", "uploaded_with_warnings"}
    assert statuses[fake.name] == "failed"


def test_ingest_extracted_text_contains_expected_content():
    """Page 1 text must contain the fixture's cover-page content."""
    results = ingest_documents([SAMPLE_PDF])
    r = results[0]
    page1 = next(pg for pg in r.pages if pg.page_number == 1)
    combined = page1.text
    # The fixture inserts "Annual Report 2024" on page 1
    assert "Annual Report" in combined or "Example Corp" in combined or "2024" in combined, (
        f"Expected cover-page keywords in page 1 text. Got: {combined!r}"
    )


def test_ingest_parser_used_is_set_on_success():
    """parser_used must be a non-empty string when parsing succeeds."""
    results = ingest_documents([SAMPLE_PDF])
    r = results[0]
    if r.status != "failed":
        assert r.parser_used in {"docling", "pymupdf"}, (
            f"Unexpected parser_used value: {r.parser_used!r}"
        )
