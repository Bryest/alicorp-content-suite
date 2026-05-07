"""Domain-layer unit tests — pure Python, no I/O."""

from __future__ import annotations

import pytest

from backend.domain.brand import (
    BrandManual,
    BrandSection,
    ForbiddenWords,
)
from backend.domain.content import (
    ApprovalStateMachine,
    ApprovalStatus,
    ContentItem,
    ContentType,
    InvalidTransitionError,
)
from uuid import uuid4


def test_forbidden_words_normalizes():
    fw = ForbiddenWords.from_iterable([" Cheap ", "diet", "DIET", "", None])
    assert "cheap" in fw.words
    assert "diet" in fw.words
    assert len(fw) == 2


def test_forbidden_words_contains_case_insensitive():
    fw = ForbiddenWords.from_iterable(["cheap", "diet"])
    hits = fw.contains("This is a Cheap diet snack.")
    assert "cheap" in hits and "diet" in hits


def test_brand_manual_chunks_skips_empty_sections():
    m = BrandManual(
        name="X",
        product_type="snack",
        tone="fun",
        audience="genz",
        raw_manual="raw",
        sections={
            BrandSection.TONE: "tone here",
            BrandSection.FORBIDDEN: "",  # skipped
            BrandSection.MESSAGING: "msg",
        },
    )
    sections = [c.section for c in m.chunks()]
    assert BrandSection.TONE in sections
    assert BrandSection.MESSAGING in sections
    assert BrandSection.FORBIDDEN not in sections


def _new_pending_item() -> ContentItem:
    return ContentItem(
        brand_id=uuid4(),
        creator_id=uuid4(),
        content_type=ContentType.PRODUCT_DESCRIPTION,
        original_request="x",
        content="some copy",
        status=ApprovalStatus.PENDING,
    )


def test_state_machine_happy_path():
    item = _new_pending_item()
    aa = uuid4()
    ApprovalStateMachine.approve_text(item, aa, "looks good")
    assert item.status == ApprovalStatus.APPROVED_TEXT
    assert item.approver_a_id == aa

    ab = uuid4()
    ApprovalStateMachine.finalize_image_audit(
        item, ab, {"compliant": True, "checks": [], "summary": "ok"}
    )
    assert item.status == ApprovalStatus.APPROVED


def test_state_machine_rejects_illegal_transition():
    item = _new_pending_item()
    # Cannot go straight to image audit before text approval
    with pytest.raises(InvalidTransitionError):
        ApprovalStateMachine.finalize_image_audit(
            item, uuid4(), {"compliant": True}
        )


def test_state_machine_image_audit_failure_routes_to_rejected():
    item = _new_pending_item()
    ApprovalStateMachine.approve_text(item, uuid4())
    ApprovalStateMachine.finalize_image_audit(
        item,
        uuid4(),
        {"compliant": False, "checks": [], "summary": "bad logo"},
    )
    assert item.status == ApprovalStatus.REJECTED
    assert item.rejection_reason == "bad logo"
