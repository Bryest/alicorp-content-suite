"""
Pydantic I/O schemas — kept separate from domain entities so the wire
contract can evolve independently of the domain model.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Auth ──────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    email: str
    role: str


# ── Brand DNA ─────────────────────────────────────────────────
class BrandDNARequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    product_type: str = Field(min_length=2, max_length=200)
    tone: str = Field(min_length=2, max_length=300)
    audience: str = Field(min_length=2, max_length=300)
    visual_rules: Optional[str] = ""
    forbidden_words: list[str] = Field(default_factory=list)
    key_messages: list[str] = Field(default_factory=list)

    @field_validator("forbidden_words", "key_messages", mode="before")
    @classmethod
    def _coerce_lists(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


class BrandDNAResponse(BaseModel):
    brand_id: UUID
    name: str
    sections_embedded: int
    sections: dict[str, str]
    raw_manual: str
    message: str


class BrandSummary(BaseModel):
    brand_id: UUID
    name: str
    product_type: str
    created_at: str


# ── Generation ────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    brand_id: UUID
    content_type: str = Field(
        description="One of: product_description, video_script, image_prompt, social_post, tagline"
    )
    request: str = Field(min_length=3, max_length=1500)


class ConflictDTO(BaseModel):
    rule: str
    violation: str
    suggestion: str = ""


class RetrievedChunkDTO(BaseModel):
    chunk_id: UUID
    section: str
    similarity: float


class GenerateResponse(BaseModel):
    content_id: Optional[UUID] = None
    content: Optional[str] = None
    conflicts: list[ConflictDTO] = []
    retrieved_chunks: list[RetrievedChunkDTO] = []
    status: str


class ContentDetail(BaseModel):
    content_id: UUID
    brand_id: UUID
    creator_id: UUID
    content_type: str
    original_request: str
    content: Optional[str] = None
    status: str
    conflicts: list[ConflictDTO] = []
    retrieved_chunks: list[RetrievedChunkDTO] = []
    approver_a_notes: Optional[str] = None
    audit_result: Optional[dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    created_at: str
    updated_at: str


# ── Approval (Approver A) ─────────────────────────────────────
class TextDecisionRequest(BaseModel):
    decision: str = Field(description="approved_text | rejected")
    notes: Optional[str] = None


class TextDecisionResponse(BaseModel):
    content_id: UUID
    status: str
    approver_a_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


# ── Image Audit (Approver B) ──────────────────────────────────
class CheckDTO(BaseModel):
    rule: str
    passed: bool
    note: str = ""


class AuditResponse(BaseModel):
    content_id: UUID
    status: str
    audit_result: Optional[dict[str, Any]] = None
    rejection_reason: Optional[str] = None


# ── Health ────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    mock_mode: dict[str, bool]
