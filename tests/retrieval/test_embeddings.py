"""
Tests for BGE embeddings.

Verifies:
1. Embeddings produce 384-dimensional vectors
2. L2 normalization (unit vector length)
3. Batch document embedding
4. Query embedding with instruction prefix
5. Deterministic fallback embedder reliability
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.retrieval.embeddings import BGEEmbedder, default_embedder


def test_bge_embeddings_dimension_and_normalization():
    embedder = default_embedder
    texts = [
        "Total revenue reached $4,200,000 for fiscal year 2024.",
        "Operating expenses increased by 8% due to research investments.",
    ]
    vectors = embedder.embed_documents(texts)

    assert len(vectors) == 2
    for vec in vectors:
        assert len(vec) == 384
        # Verify L2 norm is approximately 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_bge_query_embedding():
    embedder = default_embedder
    query = "What was the total revenue in fiscal 2024?"
    vec = embedder.embed_query(query)

    assert len(vec) == 384
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_bge_fallback_embedder_deterministic():
    embedder = BGEEmbedder(use_fallback_only=True)
    text = "Cash flow from operations was positive at $850,000."
    vec1 = embedder.embed_documents([text])[0]
    vec2 = embedder.embed_documents([text])[0]

    assert len(vec1) == 384
    assert vec1 == vec2
    norm = math.sqrt(sum(x * x for x in vec1))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)
