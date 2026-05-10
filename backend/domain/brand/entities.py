"""
Brand context entities.

`BrandManual` is the aggregate root. `BrandChunk` is the embedded RAG unit
— one per canonical section.
"""


from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from .value_objects import BrandSection


@dataclass
class BrandChunk:
    """
    A single embedded section of a brand manual.

    `embedding` is kept as plain list[float] in the domain — the
    infrastructure adapter is responsible for serializing to pgvector.
    """

    brand_id: UUID
    section: BrandSection
    content: str
    embedding: list[float] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise ValueError("BrandChunk content cannot be empty")


@dataclass
class BrandManual:
    """Aggregate root — the brand's structured rule book."""

    name: str
    product_type: str
    tone: str
    audience: str
    raw_manual: str
    sections: dict[BrandSection, str] = field(default_factory=dict)
    forbidden_words: list[str] = field(default_factory=list)
    user_id: Optional[UUID] = None
    id: UUID = field(default_factory=uuid4)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("BrandManual.name is required")
        if not self.product_type or not self.product_type.strip():
            raise ValueError("BrandManual.product_type is required")

    def chunks(self) -> list[BrandChunk]:
        """Materialize one BrandChunk per non-empty section."""
        result = []
        for section in BrandSection.all():
            content = self.sections.get(section, "").strip()
            if content:
                result.append(
                    BrandChunk(
                        brand_id=self.id,
                        section=section,
                        content=content,
                        version=self.version,
                    )
                )
        return result
