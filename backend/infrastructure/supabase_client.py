"""
Supabase adapter — implements BrandRepository + ContentRepository.

REAL mode: uses the official supabase-py client + a stored RPC
`match_brand_chunks` that wraps pgvector cosine search.
MOCK mode: in-memory dict store that implements EXACTLY the same port,
including cosine-similarity semantic search over locally-stored
embeddings. Same API contract — the application layer cannot tell.

Mock mode also seeds a static set of demo users (the 3 roles required
by the challenge) so the role-based flow is fully exercisable without
Supabase Auth.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid5, NAMESPACE_DNS

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
from .embedding_service import cosine_similarity

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Demo users — used in mock mode (no Supabase Auth)
# ─────────────────────────────────────────────────────────────────────
def _stable_uuid(seed: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"alicorp.contentsuite.{seed}")


DEMO_USERS = {
    "creator@test.com": {
        "id": _stable_uuid("creator"),
        "email": "creator@test.com",
        "password": "Test1234!",
        "role": "creator",
    },
    "approver.a@test.com": {
        "id": _stable_uuid("approver_a"),
        "email": "approver.a@test.com",
        "password": "Test1234!",
        "role": "approver_a",
    },
    "approver.b@test.com": {
        "id": _stable_uuid("approver_b"),
        "email": "approver.b@test.com",
        "password": "Test1234!",
        "role": "approver_b",
    },
}


# ─────────────────────────────────────────────────────────────────────
# In-memory store (mock mode)
# ─────────────────────────────────────────────────────────────────────
class _InMemoryStore:
    """
    Process-wide singleton. Same store shared by Brand + Content repos
    so that cross-aggregate references (brand_id on content) resolve.
    """

    _instance: Optional["_InMemoryStore"] = None

    def __init__(self) -> None:
        self.brand_manuals: dict[UUID, BrandManual] = {}
        self.brand_chunks: dict[UUID, BrandChunk] = {}
        self.content_items: dict[UUID, ContentItem] = {}

    @classmethod
    def get(cls) -> "_InMemoryStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# ─────────────────────────────────────────────────────────────────────
# Real Supabase client wrapper
# ─────────────────────────────────────────────────────────────────────
def _build_supabase_client():
    settings = get_settings()
    if settings.supabase_mocked:
        return None
    try:
        from supabase import create_client

        return create_client(settings.supabase_url, settings.supabase_service_role_key)
    except Exception as e:  # pragma: no cover
        logger.warning(f"Supabase init failed: {e}. Falling back to mock.")
        return None


# ─────────────────────────────────────────────────────────────────────
# BrandRepository — Supabase or in-memory
# ─────────────────────────────────────────────────────────────────────
class SupabaseBrandRepository(BrandRepository):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = _build_supabase_client()
        self._store = _InMemoryStore.get()
        self._mocked = self._client is None
        if self._mocked:
            logger.info("SupabaseBrandRepository: MOCK mode (in-memory)")

    @property
    def is_mocked(self) -> bool:
        return self._mocked

    async def save_manual(self, manual: BrandManual) -> BrandManual:
        if self._mocked:
            self._store.brand_manuals[manual.id] = deepcopy(manual)
            return manual

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
        if self._mocked:
            return deepcopy(self._store.brand_manuals.get(manual_id))

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
        if self._mocked:
            return [
                deepcopy(m)
                for m in self._store.brand_manuals.values()
                if m.user_id == user_id
            ]
        resp = (
            self._client.table("brand_manuals")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )
        return [_row_to_manual(r) for r in (resp.data or [])]

    async def save_chunks(self, chunks: list[BrandChunk]) -> int:
        if self._mocked:
            for c in chunks:
                self._store.brand_chunks[c.id] = deepcopy(c)
            return len(chunks)

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
        if self._mocked:
            scored: list[tuple[BrandChunk, float]] = []
            for c in self._store.brand_chunks.values():
                if c.brand_id != brand_id:
                    continue
                if section_filter is not None and c.section != section_filter:
                    continue
                sim = cosine_similarity(query_embedding, c.embedding)
                if sim >= min_similarity:
                    scored.append((deepcopy(c), sim))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]

        # Real mode: call the SQL RPC defined in db/schema.sql
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
    )


# ─────────────────────────────────────────────────────────────────────
# ContentRepository — Supabase or in-memory
# ─────────────────────────────────────────────────────────────────────
class SupabaseContentRepository(ContentRepository):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = _build_supabase_client()
        self._store = _InMemoryStore.get()
        self._mocked = self._client is None
        if self._mocked:
            logger.info("SupabaseContentRepository: MOCK mode (in-memory)")

    @property
    def is_mocked(self) -> bool:
        return self._mocked

    async def save(self, item: ContentItem) -> ContentItem:
        if self._mocked:
            self._store.content_items[item.id] = deepcopy(item)
            return item
        self._client.table("content_items").upsert(_item_to_row(item)).execute()
        return item

    async def get(self, item_id: UUID) -> Optional[ContentItem]:
        if self._mocked:
            return deepcopy(self._store.content_items.get(item_id))
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
        if self._mocked:
            items = list(self._store.content_items.values())
            if creator_id is not None:
                items = [i for i in items if i.creator_id == creator_id]
            if status is not None:
                items = [i for i in items if i.status == status]
            if brand_id is not None:
                items = [i for i in items if i.brand_id == brand_id]
            items.sort(key=lambda x: x.created_at, reverse=True)
            return [deepcopy(i) for i in items[offset : offset + limit]]

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
        approver_b_id=UUID(r["approver_b_id"]) if r.get("approver_b_id") else None,
        audit_result=r.get("audit_result"),
        rejection_reason=r.get("rejection_reason"),
    )
