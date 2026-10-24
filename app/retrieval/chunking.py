"""
Structure-aware chunking for financial documents.

Preserves:
- Document IDs, versions, and filenames
- 1-based page numbers and active section headings
- Financial table headings, column structures, and unit declarations
- Footnotes and notes references
- Chunk order and total document chunks for context expansion
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ingestion.document_parser import DocumentParseResult, ParsedPage


@dataclass
class TextChunk:
    """A single structure-aware chunk of document text with full provenance."""

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
    chunk_index: int = 0
    total_chunks: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for storage payloads."""
        return {
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
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "metadata": self.metadata,
        }


# Regular expressions for structure detection
_SECTION_HEADING_PATTERNS = [
    re.compile(r"^(?:Item\s+[0-9A-Za-z\.]+|Part\s+[IVX]+|Note\s+\d+)[:\s].*", re.IGNORECASE),
    re.compile(r"^(?:Revenue|Income|Balance\s+Sheet|Cash\s+Flows?|Risk\s+Factors|Management'?s\s+Discussion|Financial\s+Condition|Accounting\s+Policies|Liquidity|Capital\s+Resources)(?:\s+(?:Summary|Statement|Analysis|Overview|Reconciliation|Policies))?\s*[:\-]?\s*$", re.IGNORECASE),
]

_UNIT_PATTERNS = [
    re.compile(r"\((?:in\s+)?(?:\$|usd|eur|€|gbp|£)?\s*(millions|billions|thousands)(?:[,\s]+except[^\)]*)?\)", re.IGNORECASE),
    re.compile(r"(?:in\s+)(millions|billions|thousands)\s*(?:of\s+dollars)?", re.IGNORECASE),
    re.compile(r"\b(?:usd|\$|eur|€|gbp|£)\b", re.IGNORECASE),
    re.compile(r"\b(?:percent|percentage|%|bps|basis\s+points)\b", re.IGNORECASE),
]

_FOOTNOTE_PATTERNS = [
    re.compile(r"^(?:\*+|\†|\([0-9a-z]\)|\[\d+\]|Note\s*:|Footnote\s*:)\s+(.*)", re.IGNORECASE),
]

_TABLE_ROW_PATTERN = re.compile(
    r"^(?:.*(?:\s{2,}|\t|\|).*[\$\d,]+.*|.*[:]\s*[\$\d,]+.*)$"
)


class StructureAwareChunker:
    """
    Chunks parsed financial documents while preserving structural context:
    sections, table headings, units, and footnotes.
    """

    def __init__(
        self,
        target_chunk_size: int = 500,
        chunk_overlap: int = 80,
        min_chunk_size: int = 60,
    ) -> None:
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, doc: DocumentParseResult) -> list[TextChunk]:
        """Chunk an entire DocumentParseResult preserving document-level metadata."""
        version = str(doc.metadata.get("document_version", "1.0"))
        return self.chunk_pages(
            pages=doc.pages,
            document_id=doc.document_id,
            filename=doc.filename,
            document_version=version,
            metadata=doc.metadata,
        )

    def chunk_pages(
        self,
        pages: list[ParsedPage],
        document_id: str,
        filename: str,
        document_version: str = "1.0",
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Chunk a list of ParsedPage objects sequentially."""
        meta = metadata or {}
        raw_chunks: list[TextChunk] = []

        current_section = "General"
        active_table_heading: str | None = None
        active_units: str | None = None

        for page in pages:
            page_text = page.text or ""
            if not page_text.strip():
                continue

            lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
            page_footnotes: list[str] = []

            # First pass: identify footnotes on the page
            clean_lines: list[str] = []
            for line in lines:
                is_fn = False
                for fn_pat in _FOOTNOTE_PATTERNS:
                    m = fn_pat.match(line)
                    if m:
                        page_footnotes.append(line)
                        is_fn = True
                        break
                if not is_fn:
                    clean_lines.append(line)

            # Second pass: group lines into structural blocks (paragraphs, tables)
            current_block: list[str] = []
            is_in_table = False

            for line in clean_lines:
                # Check for section heading
                if self._is_section_heading(line):
                    if current_block:
                        self._process_block(
                            lines=current_block,
                            page_number=page.page_number,
                            document_id=document_id,
                            document_version=document_version,
                            filename=filename,
                            section=current_section,
                            table_heading=active_table_heading if is_in_table else None,
                            units=active_units,
                            footnotes=page_footnotes,
                            metadata=meta,
                            output=raw_chunks,
                        )
                        current_block = []
                        is_in_table = False
                    current_section = line
                    active_table_heading = None
                    continue

                # Check for table title or unit declaration
                table_title = self._detect_table_title(line)
                if table_title:
                    active_table_heading = table_title
                    is_in_table = True

                detected_unit = self._detect_units(line)
                if detected_unit:
                    active_units = detected_unit

                # Check if line looks like a tabular row
                if _TABLE_ROW_PATTERN.match(line):
                    is_in_table = True

                current_block.append(line)

                # If block reached target size, flush
                block_len = sum(len(l) for l in current_block)
                if block_len >= self.target_chunk_size:
                    self._process_block(
                        lines=current_block,
                        page_number=page.page_number,
                        document_id=document_id,
                        document_version=document_version,
                        filename=filename,
                        section=current_section,
                        table_heading=active_table_heading if is_in_table else None,
                        units=active_units,
                        footnotes=page_footnotes,
                        metadata=meta,
                        output=raw_chunks,
                    )
                    # Handle overlap if not a pure table
                    if not is_in_table and len(current_block) > 2:
                        current_block = current_block[-1:]
                    else:
                        current_block = []
                        is_in_table = False

            # Flush remaining block on this page
            if current_block:
                self._process_block(
                    lines=current_block,
                    page_number=page.page_number,
                    document_id=document_id,
                    document_version=document_version,
                    filename=filename,
                    section=current_section,
                    table_heading=active_table_heading if is_in_table else None,
                    units=active_units,
                    footnotes=page_footnotes,
                    metadata=meta,
                    output=raw_chunks,
                )

        # Set total_chunks and sequential 0-based chunk_index
        total = len(raw_chunks)
        for idx, chk in enumerate(raw_chunks):
            chk.chunk_index = idx
            chk.total_chunks = total

        return raw_chunks

    def _process_block(
        self,
        lines: list[str],
        page_number: int,
        document_id: str,
        document_version: str,
        filename: str,
        section: str,
        table_heading: str | None,
        units: str | None,
        footnotes: list[str],
        metadata: dict[str, Any],
        output: list[TextChunk],
    ) -> None:
        """Create a TextChunk from lines with full structural provenance."""
        text = "\n".join(lines).strip()
        if len(text) < self.min_chunk_size and output:
            # Merge very small trailing fragment into the previous chunk if same page
            prev = output[-1]
            if prev.page_number == page_number and prev.section == section:
                prev.text = prev.text + "\n" + text
                return

        chunk_id = f"chunk_{document_id[:8]}_p{page_number}_c{len(output)}"
        chunk = TextChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            document_version=document_version,
            filename=filename,
            page_number=page_number,
            section=section,
            text=text,
            table_heading=table_heading,
            units=units,
            footnotes=list(footnotes),
            metadata=dict(metadata),
        )
        output.append(chunk)

    def _is_section_heading(self, line: str) -> bool:
        if len(line) > 100:
            return False
        for pat in _SECTION_HEADING_PATTERNS:
            if pat.match(line):
                return True
        # All caps short heading (e.g. "CONSOLIDATED STATEMENTS OF OPERATIONS")
        if line.isupper() and 4 < len(line) < 60:
            return True
        return False

    def _detect_table_title(self, line: str) -> str | None:
        if len(line) < 80 and any(
            k in line.lower()
            for k in [
                "table",
                "summary",
                "schedule",
                "statement of",
                "balance sheet",
                "statements",
                "reconciliation",
            ]
        ):
            return line
        return None

    def _detect_units(self, line: str) -> str | None:
        for pat in _UNIT_PATTERNS:
            m = pat.search(line)
            if m:
                return m.group(0)
        return None
