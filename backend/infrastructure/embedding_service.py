"""Gemini embedding adapter (text-embedding-001, 768-dim via MRL truncation)."""

import logging
import math
from typing import Literal

import google.generativeai as genai

from ..config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768
TaskType = Literal["retrieval_document", "retrieval_query"]


class EmbeddingService:
    """Port-shaped wrapper around the Gemini embeddings API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY must be set. Configure it in environment "
                "variables before starting the API."
            )
        genai.configure(api_key=self.settings.google_api_key)
        self._client = genai
        logger.info(f"EmbeddingService: ready ({self.settings.gemini_embedding_model})")

    async def embed(self, text: str, task_type: TaskType = "retrieval_document") -> list[float]:
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

    async def embed_batch(self, texts: list[str], task_type: TaskType = "retrieval_document") -> list[list[float]]:
        return [await self.embed(t, task_type) for t in texts]
