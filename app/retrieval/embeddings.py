"""
BGE Embedding module for dense financial text retrieval.

Uses BAAI/bge-small-en-v1.5 via fastembed (ONNX runtime) with L2 normalization.
Includes a deterministic fallback embedder for offline/isolated environments.
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_BGE_MODEL = "BAAI/bge-small-en-v1.5"
BGE_SMALL_DIMENSION = 384


class BGEEmbedder:
    """
    BGE Embedder producing 384-dimensional dense vectors.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_BGE_MODEL,
        use_fallback_only: bool = False,
    ) -> None:
        self.model_name = model_name
        self.dimension = BGE_SMALL_DIMENSION
        self._model = None
        self._is_fallback = use_fallback_only

        if not use_fallback_only:
            try:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(model_name=model_name)
                logger.info("Initialized FastEmbed with BGE model: %s", model_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "FastEmbed BGE initialization failed (%s); using deterministic fallback embedder",
                    exc,
                )
                self._is_fallback = True

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of document chunks and return L2-normalized float vectors."""
        if not texts:
            return []

        if not self._is_fallback and self._model is not None:
            try:
                # FastEmbed returns an iterator of numpy arrays
                raw_embeddings = list(self._model.embed(list(texts)))
                return [self._normalize_vector(vec) for vec in raw_embeddings]
            except Exception as exc:  # noqa: BLE001
                logger.warning("BGE fastembed batch failed (%s); falling back", exc)

        return [self._fallback_embed(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query with BGE query instruction prefix where appropriate."""
        if not query.strip():
            return [0.0] * self.dimension

        # BGE models use an optional instruction prefix for queries
        query_text = f"Represent this sentence for searching relevant passages: {query}"

        if not self._is_fallback and self._model is not None:
            try:
                raw_iter = self._model.query_embed(query_text)
                vec = next(raw_iter)
                return self._normalize_vector(vec)
            except Exception as exc:  # noqa: BLE001
                logger.warning("BGE fastembed query failed (%s); falling back", exc)

        return self._fallback_embed(query_text)

    def _normalize_vector(self, vec: Sequence[float] | np.ndarray) -> list[float]:
        arr = np.asarray(vec, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()

    def _fallback_embed(self, text: str) -> list[float]:
        """
        Deterministic pseudo-embedding for testing or offline environments.
        Computes an L2-normalized 384-dimensional feature vector based on token hashes.
        """
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = text.lower().split()
        if not tokens:
            return vec.tolist()

        for token in tokens:
            # Deterministic bucket hashing
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % self.dimension
            val = ((int.from_bytes(digest[2:4], "big") % 1000) / 1000.0) - 0.5
            vec[idx] += val

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()


# Singleton default embedder instance
default_embedder = BGEEmbedder()
