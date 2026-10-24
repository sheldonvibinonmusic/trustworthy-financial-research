"""
app.ingestion
=============

PDF ingestion pipeline (Milestone 1: validation + parsing).

Public API::

    from app.ingestion import ingest_documents
    from app.ingestion.document_parser import DocumentParseResult, ParsedPage
    from app.ingestion.file_validation import validate_pdf
"""

from app.ingestion.document_parser import (
    DocumentParseResult,
    ParsedPage,
    ingest_documents,
)
from app.ingestion.file_validation import validate_pdf
from app.ingestion.registry import DocumentRegistry, registry

__all__ = [
    "ingest_documents",
    "validate_pdf",
    "DocumentParseResult",
    "ParsedPage",
    "DocumentRegistry",
    "registry",
]
