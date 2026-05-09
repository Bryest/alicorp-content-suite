"""Supabase adapters for BrandRepository and ContentRepository (pgvector + RPC)."""


import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from supabase import create_client

from ..config import get_settings
from ..domain.brand import BrandChunk, BrandManual, BrandRepository, BrandSection
from ..domain.content import (
    ApprovalStatus,
    ContentItem,
    ContentRepository,
    ContentType,
    ConflictItem,
    RetrievedChunkRef,
)

logger = logging.getLogger(__name__)


def _build_supabase_client():
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. "
            "Configure them in environment variables before starting the API."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# ─────────────────────────────────────────────────────────────────────
# BrandRepository — Supabase-backed
# ─────────────────────────────────────────────────────────────────────
class SupabaseBrandRepository(BrandRepository):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = _build_supabase_client()

    async def save_manual(self, manual: BrandManual) -> BrandManual:
        row = {
            "id": str(manual.id),
            "user_id": str(manual.user_id) if manual.user_id else None,
            "name": manual.name,
            "product_type": manual.product_type,
            "tone": manual.tone,
            "target_audience": manual.audience,
            "raw_manual": manual.raw_manual,
            "version": manual.version,
        }
        self._client.table("brand_manuals").upsert(row).execute()
        return manual

    async def get_manual(self, manual_id: UUID) -> Optional[BrandManual]:
        resp = (
            self._client.table("brand_manuals")
            .select("*")
            .eq("id", str(manual_id))
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return _row_to_manual(resp.data[0])

    async def list_manuals(self, user_id: UUID) -> list[BrandManual]:
        resp = (
            self._client.table("brand_manuals")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )
        return [_row_to_manual(r) for r in (resp.data or [])]

    async def save_chunks(self, chunks: list[BrandChunk]) -> int:
        rows = [
            {
                "id": str(c.id),
                "brand_id": str(c.brand_id),
                "section": c.section.value,
                "content": c.content,
                "embedding": c.embedding,
                "version": c.version,
            }
            for c in chunks
        ]
        if rows:
            self._client.table("brand_chunks").upsert(rows).execute()
        return len(rows)

    async def search_chunks(
        self,
        brand_id: UUID,
        query_embedding: list[float],
        top_k: int = 3,
        min_similarity: float = 0.5,
        section_filter: Optional[BrandSection] = None,
    ) -> list[tuple[BrandChunk, float]]:
        # Calls the SQL RPC defined in db/schema.sql, which wraps pgvector
        # cosine search and applies the similarity threshold server-side.
        resp = self._client.rpc(
            "match_brand_chunks",
            {
                "query_embedding": query_embedding,
                "p_brand_id": str(brand_id),
                "match_count": top_k,
                "min_similarity": min_similarity,
            },
        ).execute()
        rows = resp.data or []
        result: list[tuple[BrandChunk, float]] = []
        for r in rows:
            if section_filter is not None and r.get("section") != section_filter.value:
                continue
            result.append(
                (
                    BrandChunk(
                        id=UUID(r["id"]),
                        brand_id=UUID(r["brand_id"]),
                        section=BrandSection(r["section"]),
                        content=r["content"],
                        embedding=[],  # don't reload embedding for read paths
                    ),
                    float(r.get("similarity", 0.0)),
                )
            )
        return result


def _parse_dt(value) -> datetime:
    """Tolerant ISO timestamp parser. Defaults to now() only if value is missing/invalid."""
    if not value:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _row_to_manual(r: dict) -> BrandManual:
    return BrandManual(
        id=UUID(r["id"]),
        user_id=UUID(r["user_id"]) if r.get("user_id") else None,
        name=r["name"],
        product_type=r.get("product_type") or "",
        tone=r.get("tone") or "",
        audience=r.get("target_audience") or "",
        raw_manual=r.get("raw_manual") or "",
        version=int(r.get("version") or 1),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
    )


# ─────────────────────────────────────────────────────────────────────
# ContentRepository — Supabase-backed
# ─────────────────────────────────────────────────────────────────────
class SupabaseContentRepository(ContentRepository):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = _build_supabase_client()

    async def save(self, item: ContentItem) -> ContentItem:
        self._client.table("content_items").upsert(_item_to_row(item)).execute()
        return item

    async def get(self, item_id: UUID) -> Optional[ContentItem]:
        resp = (
            self._client.table("content_items")
            .select("*")
            .eq("id", str(item_id))
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return _row_to_item(resp.data[0])

    async def list(
        self,
        *,
        creator_id: Optional[UUID] = None,
        status: Optional[ApprovalStatus] = None,
        brand_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ContentItem]:
        q = self._client.table("content_items").select("*")
        if creator_id is not None:
            q = q.eq("creator_id", str(creator_id))
        if status is not None:
            q = q.eq("status", status.value)
        if brand_id is not None:
            q = q.eq("brand_id", str(brand_id))
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        resp = q.execute()
        return [_row_to_item(r) for r in (resp.data or [])]

    async def update(self, item: ContentItem) -> ContentItem:
        item.updated_at = datetime.now(timezone.utc)
        return await self.save(item)


def _item_to_row(item: ContentItem) -> dict:
    return {
        "id": str(item.id),
        "brand_id": str(item.brand_id),
        "creator_id": str(item.creator_id),
        "content_type": item.content_type.value,
        "original_request": item.original_request,
        "content": item.content,
        "status": item.status.value,
        "conflicts": [c.to_dict() for c in item.conflicts],
        "retrieved_chunks": [r.to_dict() for r in item.retrieved_chunks],
        "approver_a_id": str(item.approver_a_id) if item.approver_a_id else None,
        "approver_a_notes": item.approver_a_notes,
        "approver_a_at": item.approver_a_at.isoformat() if item.approver_a_at else None,
        "approver_b_id": str(item.approver_b_id) if item.approver_b_id else None,
        "audit_result": item.audit_result,
        "rejection_reason": item.rejection_reason,
    }


def _row_to_item(r: dict) -> ContentItem:
    return ContentItem(
        id=UUID(r["id"]),
        brand_id=UUID(r["brand_id"]),
        creator_id=UUID(r["creator_id"]),
        content_type=ContentType(r["content_type"]),
        original_request=r.get("original_request") or "",
        content=r.get("content"),
        status=ApprovalStatus(r.get("status") or "pending"),
        conflicts=[
            ConflictItem(
                rule=c.get("rule", ""),
                violation=c.get("violation", ""),
                suggestion=c.get("suggestion", ""),
            )
            for c in (r.get("conflicts") or [])
        ],
        retrieved_chunks=[
            RetrievedChunkRef(
                chunk_id=UUID(c["chunk_id"]),
                section=c["section"],
                similarity=float(c["similarity"]),
            )
            for c in (r.get("retrieved_chunks") or [])
        ],
        approver_a_id=UUID(r["approver_a_id"]) if r.get("approver_a_id") else None,
        approver_a_notes=r.get("approver_a_notes"),
        approver_a_at=_parse_dt(r["approver_a_at"]) if r.get("approver_a_at") else None,
        approver_b_id=UUID(r["approver_b_id"]) if r.get("approver_b_id") else None,
        audit_result=r.get("audit_result"),
        rejection_reason=r.get("rejection_reason"),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
    )
