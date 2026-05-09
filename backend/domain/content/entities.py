"""
Content context entities.

`ContentItem` is the aggregate root. It carries its full audit trail
through the approval state machine.
"""


from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from .value_objects import ApprovalStatus, ContentType


@dataclass(frozen=True)
class ConflictItem:
    """A single brand-rule violation detected at generation time."""

    rule: str
    violation: str
    suggestion: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "violation": self.violation, "suggestion": self.suggestion}


@dataclass(frozen=True)
class RetrievedChunkRef:
    """Trace of which RAG chunks were used during generation."""

    chunk_id: UUID
    section: str
    similarity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": str(self.chunk_id),
            "section": self.section,
            "similarity": round(self.similarity, 4),
        }


@dataclass
class ContentItem:
    """A generated piece of content moving through the approval flow."""

    brand_id: UUID
    creator_id: UUID
    content_type: ContentType
    original_request: str
    content: Optional[str] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    conflicts: list[ConflictItem] = field(default_factory=list)
    retrieved_chunks: list[RetrievedChunkRef] = field(default_factory=list)
    approver_a_id: Optional[UUID] = None
    approver_a_notes: Optional[str] = None
    approver_a_at: Optional[datetime] = None
    approver_b_id: Optional[UUID] = None
    audit_result: Optional[dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_blocked(self) -> bool:
        return bool(self.conflicts) and self.content is None

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
