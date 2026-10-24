"""
Stage 2 Context Expansion and Multi-Feature Reranking.

Performs:
1. Candidate deduplication
2. Structural context reconstruction (table headings, units, and footnotes)
3. Multi-feature financial reranking combining dense cosine similarity,
   BM25 lexical overlap, financial numerical/period precision, and table bonuses.
4. Bounded passage selection preserving full source provenance.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Sequence

from app.retrieval.lexical_search import tokenize_financial

if TYPE_CHECKING:
    from app.retrieval.hybrid_search import HybridCandidate

logger = logging.getLogger(__name__)

# Financial metrics and numerical tokens pattern
_NUMERIC_PATTERN = re.compile(r"[\$\€\£]?\d+(?:,\d+)*(?:\.\d+)?%?")


class ContextExpanderAndReranker:
    """
    Second-stage ranker that reconstructs table/footnote context and reranks passages.
    """

    def __init__(
        self,
        dense_weight: float = 0.45,
        lexical_weight: float = 0.35,
        numeric_match_weight: float = 0.15,
        table_structure_weight: float = 0.05,
    ) -> None:
        self.dense_weight = dense_weight
        self.lexical_weight = lexical_weight
        self.numeric_match_weight = numeric_match_weight
        self.table_structure_weight = table_structure_weight

    def expand_and_rerank(
        self,
        query: str,
        candidates: Sequence[HybridCandidate],
        top_k: int = 15,
    ) -> list[tuple[dict[str, Any], float]]:
        """
        Deduplicate, reconstruct context, and rerank candidates.

        Returns list of (expanded_payload, rerank_score) sorted descending by score.
        """
        if not candidates:
            return []

        # 1. Deduplicate by chunk_id
        seen_ids: set[str] = set()
        unique_candidates: list[HybridCandidate] = []
        for cand in candidates:
            if cand.chunk_id not in seen_ids:
                seen_ids.add(cand.chunk_id)
                unique_candidates.append(cand)

        # 2. Extract query financial entities/numbers
        query_tokens = set(tokenize_financial(query))
        query_numbers = set(_NUMERIC_PATTERN.findall(query))

        reranked: list[tuple[dict[str, Any], float]] = []

        for cand in unique_candidates:
            payload = dict(cand.payload)

            # Reconstruct context: table headings, units, footnotes
            expanded_text = self._reconstruct_context(payload)
            payload["text"] = expanded_text

            # Compute multi-feature score
            score = self._compute_rerank_score(
                cand=cand,
                expanded_text=expanded_text,
                query_tokens=query_tokens,
                query_numbers=query_numbers,
            )
            reranked.append((payload, score))

        # Sort descending by rerank score
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked[:top_k]

    def _reconstruct_context(self, payload: dict[str, Any]) -> str:
        """
        Ensure table headings, units, and footnotes are clearly represented
        in the retrieved text so downstream judges and calculators have full context.
        """
        base_text = payload.get("text", "")
        section = payload.get("section")
        table_heading = payload.get("table_heading")
        units = payload.get("units")
        footnotes = payload.get("footnotes", [])

        header_parts: list[str] = []
        if section and section not in base_text:
            header_parts.append(f"[Section: {section}]")
        if table_heading and table_heading not in base_text:
            header_parts.append(f"[Table: {table_heading}]")
        if units and units not in base_text:
            header_parts.append(f"[Units: {units}]")

        header = " ".join(header_parts)
        if header:
            text = f"{header}\n{base_text}"
        else:
            text = base_text

        # Append footnotes if present and not already in text
        if footnotes:
            unseen_footnotes = [fn for fn in footnotes if fn not in text]
            if unseen_footnotes:
                text = f"{text}\n[Footnotes: {'; '.join(unseen_footnotes)}]"

        return text

    def _compute_rerank_score(
        self,
        cand: HybridCandidate,
        expanded_text: str,
        query_tokens: set[str],
        query_numbers: set[str],
    ) -> float:
        """Calculate combined multi-feature score."""
        # Dense component (bounded [0, 1])
        dense_comp = 0.0
        if cand.dense_score is not None:
            # Cosine similarity typically in [-1, 1], normalize to [0, 1]
            dense_comp = max(0.0, min(1.0, (cand.dense_score + 1.0) / 2.0))

        # Lexical token overlap component
        text_tokens = set(tokenize_financial(expanded_text))
        lexical_overlap = 0.0
        if query_tokens:
            intersection = query_tokens.intersection(text_tokens)
            lexical_overlap = len(intersection) / len(query_tokens)

        # Numerical & currency match component
        numeric_comp = 0.0
        if query_numbers:
            text_numbers = set(_NUMERIC_PATTERN.findall(expanded_text))
            num_intersection = query_numbers.intersection(text_numbers)
            numeric_comp = len(num_intersection) / len(query_numbers)
        else:
            # If query had no specific numbers, inherit lexical overlap
            numeric_comp = lexical_overlap

        # Structural table / units bonus
        table_bonus = 0.0
        if cand.payload.get("table_heading") or cand.payload.get("units"):
            table_bonus = 1.0

        score = (
            self.dense_weight * dense_comp
            + self.lexical_weight * lexical_overlap
            + self.numeric_match_weight * numeric_comp
            + self.table_structure_weight * table_bonus
        )

        return float(round(score, 4))
