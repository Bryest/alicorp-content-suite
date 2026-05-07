"""Content context value objects + enums."""

from __future__ import annotations

from enum import Enum


class ContentType(str, Enum):
    PRODUCT_DESCRIPTION = "product_description"
    VIDEO_SCRIPT = "video_script"
    IMAGE_PROMPT = "image_prompt"
    SOCIAL_POST = "social_post"
    TAGLINE = "tagline"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED_TEXT = "approved_text"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"  # generation blocked by RAG conflict — never persisted


class ApproverRole(str, Enum):
    """Used by the state machine to authorize transitions."""

    APPROVER_A = "approver_a"
    APPROVER_B = "approver_b"
