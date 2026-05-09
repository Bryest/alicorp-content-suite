"""
Brand repository port.

Abstract interface — no implementation, no infrastructure imports.
The application layer depends on this; adapters in `infrastructure/`
implement it.
"""


from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from .entities import BrandChunk, BrandManual
from .value_objects import BrandSection


class BrandRepository(ABC):
    """Persistence port for brand manuals + their embedded chunks."""

    @abstractmethod
    async def save_manual(self, manual: BrandManual) -> BrandManual: ...

    @abstractmethod
    async def get_manual(self, manual_id: UUID) -> Optional[BrandManual]: ...

    @abstractmethod
    async def list_manuals(self, user_id: UUID) -> list[BrandManual]: ...

    @abstractmethod
    async def save_chunks(self, chunks: list[BrandChunk]) -> int:
        """Persist embedded chunks. Returns number saved."""
        ...

    @abstractmethod
    async def search_chunks(
        self,
        brand_id: UUID,
        query_embedding: list[float],
        top_k: int = 3,
        min_similarity: float = 0.5,
        section_filter: Optional[BrandSection] = None,
    ) -> list[tuple[BrandChunk, float]]:
        """
        Semantic search over a brand's chunks.

        Returns chunks paired with their cosine similarity score.
        """
        ...
