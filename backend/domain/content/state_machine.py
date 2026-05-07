"""
Approval state machine.

Encodes the legal status transitions for a `ContentItem`. The state
machine itself is pure — it holds no infrastructure references and
mutates the entity in place.

Diagram:

    PENDING ──Approver A approves──▶ APPROVED_TEXT ──Approver B audits──▶ APPROVED
       │                                  │                                  │
       └──Approver A rejects──▶ REJECTED  └──Approver B rejects──▶ REJECTED  │
                                                                             │
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .entities import ContentItem
from .value_objects import ApprovalStatus, ApproverRole


class InvalidTransitionError(Exception):
    """Raised when an actor tries to make a transition not permitted by their role/state."""


# Transitions keyed by (current_status, actor_role) → set of legal next statuses.
_TRANSITIONS: dict[tuple[ApprovalStatus, ApproverRole], set[ApprovalStatus]] = {
    (ApprovalStatus.PENDING, ApproverRole.APPROVER_A): {
        ApprovalStatus.APPROVED_TEXT,
        ApprovalStatus.REJECTED,
    },
    (ApprovalStatus.APPROVED_TEXT, ApproverRole.APPROVER_B): {
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
    },
}


class ApprovalStateMachine:
    """Operates on a `ContentItem` aggregate."""

    @staticmethod
    def can_transition(
        item: ContentItem, actor: ApproverRole, target: ApprovalStatus
    ) -> bool:
        legal = _TRANSITIONS.get((item.status, actor), set())
        return target in legal

    @staticmethod
    def approve_text(
        item: ContentItem,
        actor_id: UUID,
        notes: str | None = None,
    ) -> ContentItem:
        if not ApprovalStateMachine.can_transition(
            item, ApproverRole.APPROVER_A, ApprovalStatus.APPROVED_TEXT
        ):
            raise InvalidTransitionError(
                f"Cannot APPROVE_TEXT from status={item.status.value} as approver_a"
            )
        item.status = ApprovalStatus.APPROVED_TEXT
        item.approver_a_id = actor_id
        item.approver_a_notes = notes
        item.approver_a_at = datetime.now(timezone.utc)
        item.touch()
        return item

    @staticmethod
    def reject_text(
        item: ContentItem,
        actor_id: UUID,
        reason: str,
    ) -> ContentItem:
        if not ApprovalStateMachine.can_transition(
            item, ApproverRole.APPROVER_A, ApprovalStatus.REJECTED
        ):
            raise InvalidTransitionError(
                f"Cannot REJECT (text stage) from status={item.status.value} as approver_a"
            )
        item.status = ApprovalStatus.REJECTED
        item.approver_a_id = actor_id
        item.rejection_reason = reason
        item.approver_a_at = datetime.now(timezone.utc)
        item.touch()
        return item

    @staticmethod
    def finalize_image_audit(
        item: ContentItem,
        actor_id: UUID,
        audit_result: dict[str, Any],
    ) -> ContentItem:
        compliant = bool(audit_result.get("compliant", False))
        target = ApprovalStatus.APPROVED if compliant else ApprovalStatus.REJECTED
        if not ApprovalStateMachine.can_transition(item, ApproverRole.APPROVER_B, target):
            raise InvalidTransitionError(
                f"Cannot transition from status={item.status.value} to {target.value} as approver_b"
            )
        item.status = target
        item.approver_b_id = actor_id
        item.audit_result = audit_result
        if not compliant:
            item.rejection_reason = audit_result.get(
                "summary", "Image failed multimodal brand audit"
            )
        item.touch()
        return item
