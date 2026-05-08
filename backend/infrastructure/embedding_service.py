"""
Embedding service adapter.

REAL mode: Google text-embedding-004 (768-dim) via google.generativeai.
MOCK mode: deterministic hash-based 768-dim vector. Same input → same
vector. Different inputs → measurably different vectors. Cosine similarity
is meaningful enough for the demo flow to behave like real RAG.

The mock embedder is *not* random — it's a stable hash projection so
that semantic-ish similarity holds: two strings that share many tokens
will land closer than two unrelated strings, which is enough for the
threshold logic to demonstrate correctly.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Literal

from ..config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768
TaskType = Literal["retrieval_document", "retrieval_query"]


def _tokenize(text: str) -> list[str]:
    """Lowercase word-level tokenizer used by the mock embedder."""
    return re.findall(r"[a-záéíóúñü0-9]+", (text or "").lower())


def _mock_embed(text: str) -> list[float]:
    """
    Deterministic 768-dim embedding via token-level hashing.

    Each token contributes weight to a fixed bucket determined by its
    md5 hash. The vector is L2-normalized so cosine similarity stays
    well-behaved.
    """
    vec = [0.0] * EMBEDDING_DIM
    tokens = _tokenize(text) or ["__empty__"]
    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).digest()
        # use 4 different bytes to spread the signal
        for offset in range(0, 16, 4):
            bucket = int.from_bytes(h[offset : offset + 2], "big") % EMBEDDING_DIM
            sign = 1.0 if h[offset + 2] & 1 else -1.0
            vec[bucket] += sign * (1.0 + (h[offset + 3] / 255.0))
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class EmbeddingService:
    """Port-shaped wrapper around either Google embeddings or the mock."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if not self.settings.google_mocked:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.settings.google_api_key)
                self._client = genai
                logger.info("EmbeddingService: using Google text-embedding-004")
            except Exception as e:  # pragma: no cover — defensive
                logger.warning(f"EmbeddingService: failed to init Google client: {e}. Falling back to mock.")
                self._client = None
        if self._client is None:
            logger.info("EmbeddingService: MOCK mode (deterministic hash embeddings)")

    @property
    def is_mocked(self) -> bool:
        return self._client is None

    async def embed(self, text: str, task_type: TaskType = "retrieval_document") -> list[float]:
        if self._client is None:
            return _mock_embed(text)
        try:
            result = self._client.embed_content(
                model=self.settings.gemini_embedding_model,
                content=text,
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIM,
            )
            vec = list(result["embedding"])
            # gemini-embedding-001 requires manual L2-normalization for non-3072 dims
            n = math.sqrt(sum(x * x for x in vec)) or 1.0
            return [x / n for x in vec]
        except Exception as e:
            logger.warning(f"EmbeddingService: real call failed, falling back to mock: {e}")
            return _mock_embed(text)

    async def embed_batch(self, texts: list[str], task_type: TaskType = "retrieval_document") -> list[list[float]]:
        return [await self.embed(t, task_type) for t in texts]


# ── helpers ──────────────────────────────────────────────────────────
def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        # If dims mismatch (e.g. mock vs real switched mid-session), treat as zero.
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
