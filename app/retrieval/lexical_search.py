"""
BM25 lexical retrieval for financial text and numerical disclosures.

Uses rank_bm25 with a financial-aware tokenizer that preserves:
- Dollar and currency amounts ($4,200,000, €10M)
- Percentages (15.5%, 2%)
- Fiscal years and periods (2024, FY23, Q3)
- Accounting acronyms (EBITDA, GAAP, EPS, RoE)
- Section identifiers and line item names
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Sequence

from rank_bm25 import BM25Okapi

if TYPE_CHECKING:
    from app.retrieval.chunking import TextChunk

logger = logging.getLogger(__name__)

# Pattern to extract financial tokens, amounts, percentages, and words
_FINANCIAL_TOKEN_RE = re.compile(
    r"[\$\€\£]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?|[A-Za-z0-9_\-]+",
    re.IGNORECASE,
)


def tokenize_financial(text: str) -> list[str]:
    """Tokenize text preserving numbers, currency, percentages, and financial terms."""
    if not text:
        return []
    return _FINANCIAL_TOKEN_RE.findall(text.lower())


class BM25Index:
    """
    In-memory BM25 lexical index supporting financial tokenization and metadata filtering.
    """

    def __init__(self) -> None:
        self._chunks: list[dict[str, Any]] = []
        self._corpus_tokens: list[list[str]] = []
        self._bm25: BM25Okapi | None = None

    def add_chunks(self, chunks: Sequence[TextChunk]) -> int:
        """Add chunks to the lexical index and recompute BM25 statistics."""
        if not chunks:
            return 0

        # Avoid duplicating chunks already indexed
        existing_ids = {c["chunk_id"] for c in self._chunks}
        new_chunks = [chk for chk in chunks if chk.chunk_id not in existing_ids]

        if not new_chunks:
            return 0

        for chk in new_chunks:
            payload = chk.to_dict()
            self._chunks.append(payload)
            # Tokenize both text and structural context (table headings, units, footnotes)
            full_lexical_text = f"{chk.section} {chk.table_heading or ''} {chk.units or ''} {chk.text} {' '.join(chk.footnotes)}"
            tokens = tokenize_financial(full_lexical_text)
            self._corpus_tokens.append(tokens)

        # Re-build BM25 index with all corpus tokens
        self._bm25 = BM25Okapi(self._corpus_tokens)
        logger.info("BM25 index updated: %d total chunks", len(self._chunks))
        return len(new_chunks)

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 50,
    ) -> list[tuple[dict[str, Any], float]]:
        """
        Execute BM25 lexical search against indexed chunks.

        Returns list of (payload, bm25_score) tuples sorted in descending score order.
        """
        if not self._bm25 or not self._chunks:
            return []

        query_tokens = tokenize_financial(query)
        if not query_tokens:
            return []

        raw_scores = self._bm25.get_scores(query_tokens)

        candidates: list[tuple[dict[str, Any], float]] = []
        for idx, score in enumerate(raw_scores):
            if score <= 0.0:
                continue
            payload = self._chunks[idx]

            # Apply metadata filters
            if filters and not self._matches_filter(payload, filters):
                continue

            candidates.append((payload, float(score)))

        # Sort descending by BM25 score
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def get_chunk_count(self) -> int:
        """Return the number of chunks indexed."""
        return len(self._chunks)

    def clear(self) -> None:
        """Reset the BM25 index."""
        self._chunks.clear()
        self._corpus_tokens.clear()
        self._bm25 = None

    def _matches_filter(self, payload: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if payload satisfies all filter conditions."""
        meta = payload.get("metadata", {})
        for key, expected in filters.items():
            if expected is None:
                continue
            # Check top-level payload keys or inside metadata dict
            actual = payload.get(key)
            if actual is None:
                actual = meta.get(key)

            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True
