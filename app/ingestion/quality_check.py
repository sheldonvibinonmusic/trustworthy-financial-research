"""
Quality check module for ingested PDF documents.

Performs heuristic and structural checks on parsed pages and documents to detect:
- Low text density (indicating scanned pages that require OCR)
- High non-printable / garbled character ratios
- Empty or whitespace-only pages
- Missing metadata or suspicious text patterns
"""

from __future__ import annotations

import re
from typing import Any, Sequence


def check_page_text_quality(
    page_number: int,
    text: str,
    min_char_threshold: int = 40,
) -> list[str]:
    """Inspect text of a single page and return a list of warnings if quality is poor."""
    warnings: list[str] = []
    stripped = text.strip()

    if not stripped:
        warnings.append(f"Page {page_number} is blank; may require OCR")
        return warnings

    if len(stripped) < min_char_threshold:
        warnings.append(
            f"Page {page_number} has very low text volume ({len(stripped)} chars); "
            "may be an image, cover graphic, or require OCR"
        )

    # Check for garbled / non-printable characters
    printable_chars = sum(1 for c in stripped if c.isprintable() or c in "\r\n\t")
    ratio = printable_chars / len(stripped) if stripped else 1.0
    if ratio < 0.85:
        warnings.append(
            f"Page {page_number} contains high proportion of unprintable/corrupted characters "
            f"({(1.0 - ratio) * 100:.1f}% corrupted)"
        )

    # Check for excessive repetition of single characters (often OCR or font glitch)
    if re.search(r"(.)\1{20,}", stripped):
        warnings.append(
            f"Page {page_number} contains suspicious character repetition; text extraction may be corrupted"
        )

    return warnings


def check_document_quality(
    filename: str,
    pages_count: int,
    all_warnings: Sequence[str],
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    """Inspect document-level characteristics and return top-level warnings."""
    warnings: list[str] = []

    if pages_count == 0:
        warnings.append(f"Document '{filename}' has 0 extracted pages")

    # If all pages have OCR warnings
    blank_page_count = sum(1 for w in all_warnings if "blank" in w.lower() or "ocr" in w.lower())
    if pages_count > 0 and blank_page_count == pages_count:
        warnings.append(
            f"Document '{filename}' appears to be a scanned document without embedded text; "
            "all pages require OCR"
        )

    meta = metadata or {}
    if not meta.get("company_name") and not meta.get("title"):
        warnings.append(f"Document '{filename}' lacks company_name or title metadata")

    return warnings
