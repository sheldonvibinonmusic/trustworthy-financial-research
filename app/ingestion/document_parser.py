"""
PDF document parser for the ingestion pipeline.

Design goals
------------
* Docling is attempted first (layout-aware, table-preserving).
* PyMuPDF is used as an automatic fallback when Docling is unavailable or
  raises an unrecoverable error.
* A failed parse is never marked successful.  Fabricated text is never
  inserted.
* Every extracted page carries its 1-based page number and document-level
  metadata so that downstream retrieval can always reconstruct full provenance.

Isolated output types
---------------------
The shared ``app.schemas`` package is not yet merged onto this branch.
These dataclasses use the exact field names defined in API_CONTRACT.md and
PROJECT_BRIEF.md.  They will be adapted to the shared Pydantic models once the
core-backend branch is merged.

Public surface
--------------
``ingest_documents(paths, metadata)`` — the only function callers need.
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ingestion.file_validation import validate_pdf
from app.ingestion.quality_check import check_document_quality, check_page_text_quality
from app.ingestion.registry import registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Isolated output dataclasses
# (Field names match API_CONTRACT.md §2 and PROJECT_BRIEF.md §4)
# ---------------------------------------------------------------------------


@dataclass
class ParsedPage:
    """Text content for a single PDF page with full provenance."""

    document_id: str
    filename: str
    page_number: int  # 1-based
    text: str
    char_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


@dataclass
class DocumentParseResult:
    """
    Outcome of parsing one PDF file.

    ``status`` values mirror the upload-response contract::

        "uploaded"            – validation passed; parsing succeeded
        "uploaded_with_warnings" – parsing succeeded but some pages had issues
        "failed"              – validation or parsing failed; ``pages`` is empty
    """

    document_id: str
    filename: str
    status: str  # "uploaded" | "uploaded_with_warnings" | "failed"
    pages: list[ParsedPage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Metadata echoed from caller + extracted from document
    metadata: dict[str, Any] = field(default_factory=dict)
    # Parser used for transparency
    parser_used: str = ""
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_doc_id() -> str:
    """Generate a document ID that is stable within a single process run."""
    return f"doc_{uuid.uuid4().hex[:12]}"


def _try_docling(path: Path, document_id: str, filename: str) -> list[ParsedPage] | None:
    """
    Attempt to parse *path* with Docling.

    Returns a list of :class:`ParsedPage` objects on success, or ``None`` when
    Docling is not installed or raises an unrecoverable error.  Warnings are
    embedded inside each page's ``warnings`` list.
    """
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import]
    except ImportError:
        logger.debug("Docling not installed; skipping Docling parser")
        return None

    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document

        pages: list[ParsedPage] = []

        # Docling organises text into elements with page references.
        # We group them by page number to reconstruct per-page text blocks.
        page_texts: dict[int, list[str]] = {}
        page_warnings: dict[int, list[str]] = {}

        for element in doc.texts:
            prov = getattr(element, "prov", None)
            if prov:
                # prov is a list of ProvenanceItem objects
                for p in prov:
                    pg = getattr(p, "page_no", None)
                    if pg is not None:
                        page_texts.setdefault(pg, []).append(element.text)
            else:
                # No provenance — attach to page 0 sentinel with a warning
                page_texts.setdefault(0, []).append(element.text)
                page_warnings.setdefault(0, []).append(
                    "Element has no page provenance; assigned to sentinel page 0"
                )

        for pg_num in sorted(page_texts):
            text = "\n".join(page_texts[pg_num])
            warns = page_warnings.get(pg_num, [])
            pages.append(
                ParsedPage(
                    document_id=document_id,
                    filename=filename,
                    page_number=pg_num,
                    text=text,
                    warnings=warns,
                )
            )

        if not pages:
            logger.warning("Docling returned no text elements for %s", path)
            return None

        return pages

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Docling failed for %s (%s); will fall back to PyMuPDF",
            path,
            exc,
            exc_info=True,
        )
        return None


def _try_pymupdf(path: Path, document_id: str, filename: str) -> list[ParsedPage] | None:
    """
    Parse *path* with PyMuPDF (fitz).

    Returns a list of :class:`ParsedPage` objects on success, or ``None`` when
    PyMuPDF is not available or the file cannot be read.
    """
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # type: ignore[import]
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed; cannot parse PDF")
        return None

    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # noqa: BLE001
        logger.error("PyMuPDF cannot open %s: %s", path, exc)
        return None

    pages: list[ParsedPage] = []
    try:
        for i in range(doc.page_count):
            pg = doc.load_page(i)
            page_number = i + 1  # 1-based
            warns: list[str] = []

            try:
                text = pg.get_text("text")  # plain text extraction
            except Exception as exc:  # noqa: BLE001
                warns.append(f"Page {page_number} text extraction failed: {exc}")
                text = ""

            if not text.strip():
                warns.append(
                    f"Page {page_number} yielded no text; may require OCR"
                )

            pages.append(
                ParsedPage(
                    document_id=document_id,
                    filename=filename,
                    page_number=page_number,
                    text=text,
                    warnings=warns,
                )
            )
    finally:
        doc.close()

    return pages if pages else None


def _extract_pymupdf_metadata(path: Path) -> dict[str, Any]:
    """
    Return the PDF metadata dictionary from PyMuPDF, or an empty dict on error.
    """
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # type: ignore[import]

        doc = fitz.open(str(path))
        try:
            meta = dict(doc.metadata)  # keys: title, author, subject, …
        finally:
            doc.close()
        return meta
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Core parse function (single file)
# ---------------------------------------------------------------------------


def _parse_single_pdf(
    path: Path,
    caller_metadata: dict[str, Any],
) -> DocumentParseResult:
    """
    Validate and parse a single PDF.  Never fabricates text or marks a failed
    parse as successful.
    """
    filename = path.name
    document_id = _make_doc_id()
    t0 = time.monotonic()

    # 1. Validate ----------------------------------------------------------
    validation = validate_pdf(path)
    if not validation.is_valid:
        logger.warning("Validation failed for %s: %s", path, validation.reason)
        return DocumentParseResult(
            document_id=document_id,
            filename=filename,
            status="failed",
            warnings=[f"Validation failed: {validation.reason}"],
            metadata=caller_metadata,
            elapsed_seconds=time.monotonic() - t0,
        )

    # 2. Extract PDF-level metadata ----------------------------------------
    doc_metadata: dict[str, Any] = {
        **caller_metadata,
        **_extract_pymupdf_metadata(path),
        "source_path": str(path.resolve()),
    }

    # 3. Parse (Docling first, PyMuPDF fallback) ---------------------------
    parse_warnings: list[str] = []
    pages: list[ParsedPage] | None = None
    parser_used = ""

    pages = _try_docling(path, document_id, filename)
    if pages is not None:
        parser_used = "docling"
    else:
        parse_warnings.append(
            "Docling unavailable or failed; using PyMuPDF fallback"
        )
        pages = _try_pymupdf(path, document_id, filename)
        if pages is not None:
            parser_used = "pymupdf"

    if pages is None:
        return DocumentParseResult(
            document_id=document_id,
            filename=filename,
            status="failed",
            warnings=parse_warnings + ["All parsers failed; no text extracted"],
            metadata=doc_metadata,
            parser_used=parser_used,
            elapsed_seconds=time.monotonic() - t0,
        )

        # Run page-level text quality checks
        for pg in pages:
            q_warns = check_page_text_quality(pg.page_number, pg.text)
            pg.warnings.extend(q_warns)

    # 4. Collect per-page warnings ----------------------------------------
    all_page_warnings: list[str] = []
    if pages:
        for pg in pages:
            all_page_warnings.extend(pg.warnings)

    all_warnings = parse_warnings + all_page_warnings

    # Document-level quality check
    if pages is not None:
        doc_q_warns = check_document_quality(
            filename=filename,
            pages_count=len(pages),
            all_warnings=all_warnings,
            metadata=doc_metadata,
        )
        all_warnings.extend(doc_q_warns)

    status = "uploaded_with_warnings" if all_warnings else "uploaded"

    res = DocumentParseResult(
        document_id=document_id,
        filename=filename,
        status=status,
        pages=pages if pages else [],
        warnings=all_warnings,
        metadata=doc_metadata,
        parser_used=parser_used,
        elapsed_seconds=time.monotonic() - t0,
    )
    return res


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_documents(
    paths: list[Path | str],
    metadata: dict[str, Any] | None = None,
) -> list[DocumentParseResult]:
    """
    Validate and parse a list of PDF files.

    Parameters
    ----------
    paths:
        File-system paths to the PDF files to ingest.
    metadata:
        Optional caller-supplied metadata (e.g. ``company_name``,
        ``document_type``) that is merged into every
        :attr:`DocumentParseResult.metadata`.

    Returns
    -------
    list[DocumentParseResult]
        One result per input path.  Results for failed files are included
        (``status == "failed"``); they are never silently dropped.

    Notes
    -----
    * Processing is sequential; parallelism is deferred to a later milestone.
    * A result with ``status == "failed"`` contains an empty ``pages`` list.
      Callers must not treat ``failed`` results as having usable text.
    * Ingested documents are stored in the document registry for downstream indexing.
    """
    caller_metadata: dict[str, Any] = metadata or {}
    results: list[DocumentParseResult] = []

    for raw_path in paths:
        path = Path(raw_path)
        logger.info("Ingesting %s", path)
        result = _parse_single_pdf(path, dict(caller_metadata))
        logger.info(
            "  → %s  parser=%s  pages=%d  warnings=%d  elapsed=%.2fs",
            result.status,
            result.parser_used or "none",
            len(result.pages),
            len(result.warnings),
            result.elapsed_seconds,
        )
        if result.status != "failed":
            registry.register(result)
        results.append(result)

    return results
