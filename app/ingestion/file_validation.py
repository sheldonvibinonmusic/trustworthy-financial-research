"""
File validation for ingested documents.

Validates that an uploaded file is a readable PDF before any parsing attempt.
The check is intentionally strict: magic-byte verification plus a lightweight
page-count read.  Corrupted or password-protected files are rejected early so
that downstream parsers never receive invalid input.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import NamedTuple


class ValidationResult(NamedTuple):
    """Outcome of a single-file validation check."""

    is_valid: bool
    reason: str  # empty string when is_valid is True


# PDF files must start with the '%PDF-' magic string (hex 25 50 44 46 2D).
_PDF_MAGIC = b"%PDF-"


def validate_pdf(path: Path | str) -> ValidationResult:
    """Return a :class:`ValidationResult` for *path*.

    Checks performed (in order):
    1. The path exists and is a regular file.
    2. The first 5 bytes match the PDF magic signature.
    3. PyMuPDF can open the file and reports at least one page.

    No text extraction is performed here; this is purely a structural check.
    """
    path = Path(path)

    if not path.exists():
        return ValidationResult(False, f"File not found: {path}")

    if not path.is_file():
        return ValidationResult(False, f"Path is not a regular file: {path}")

    # --- Magic-byte check (fast, no external dependency) ---
    try:
        with path.open("rb") as fh:
            header = fh.read(len(_PDF_MAGIC))
    except OSError as exc:
        return ValidationResult(False, f"Cannot read file: {exc}")

    if header != _PDF_MAGIC:
        got = header[:8].hex(" ")
        return ValidationResult(
            False,
            f"Not a PDF file (expected magic {_PDF_MAGIC!r}, got bytes {got!r})",
        )

    # --- Structural check via PyMuPDF ---
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        try:
            if doc.is_encrypted:
                return ValidationResult(
                    False, "PDF is encrypted/password-protected; cannot parse"
                )
            page_count = doc.page_count
        finally:
            doc.close()
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(False, f"PyMuPDF cannot open file: {exc}")

    if page_count == 0:
        return ValidationResult(False, "PDF contains zero pages")

    return ValidationResult(True, "")
