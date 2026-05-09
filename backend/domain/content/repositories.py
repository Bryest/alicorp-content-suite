"""Content repository port."""


from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from .entities import ContentItem
from .value_objects import ApprovalStatus


class ContentRepository(ABC):
    """Persistence port for ContentItem aggregates."""

    @abstractmethod
    async def save(self, item: ContentItem) -> ContentItem: ...

    @abstractmethod
    async def get(self, item_id: UUID) -> Optional[ContentItem]: ...

    @abstractmethod
    async def list(
        self,
        *,
        creator_id: Optional[UUID] = None,
        status: Optional[ApprovalStatus] = None,
        brand_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ContentItem]: ...

    @abstractmethod
    async def update(self, item: ContentItem) -> ContentItem: ...
