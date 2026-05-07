"""
Stdlib + asyncio smoke test of the full stack without FastAPI.

Exercises:
  * BrandService.create_brand_manual (Module I)
  * ContentService.generate          (Module II — happy path)
  * ContentService.generate          (Module II — forbidden-word block)
  * AuditService.decide_text         (Module III A)
  * AuditService.audit_image         (Module III B)
  * Tracer side effects              (Module IV — stdout traces)

Run:
    python3 -m backend.tests.smoke_e2e_no_fastapi
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.audit_service import AuditService
from backend.application.brand_service import BrandService
from backend.application.content_service import ContentService
from backend.domain.content import ApprovalStatus, ContentType
from backend.infrastructure.embedding_service import EmbeddingService
from backend.infrastructure.gemini_client import GeminiClient
from backend.infrastructure.groq_client import GroqClient
from backend.infrastructure.langfuse_client import get_tracer
from backend.infrastructure.supabase_client import (
    DEMO_USERS,
    SupabaseBrandRepository,
    SupabaseContentRepository,
)


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


async def main() -> int:
    creator_id = DEMO_USERS["creator@test.com"]["id"]
    approver_a_id = DEMO_USERS["approver.a@test.com"]["id"]
    approver_b_id = DEMO_USERS["approver.b@test.com"]["id"]

    # ── Wire up ──────────────────────────────────────────────
    brand_repo = SupabaseBrandRepository()
    content_repo = SupabaseContentRepository()
    embedder = EmbeddingService()
    groq = GroqClient()
    gemini = GeminiClient()
    tracer = get_tracer()

    brand_svc = BrandService(brand_repo, groq, embedder, tracer)
    content_svc = ContentService(brand_repo, content_repo, groq, embedder, tracer)
    audit_svc = AuditService(content_repo, brand_repo, gemini, embedder, tracer)

    assert all(
        c.is_mocked
        for c in (embedder, groq, gemini)
    ), "Expected mock mode; remove env keys to retry"
    _ok("All adapters initialized in MOCK mode")

    # ── Module I ─────────────────────────────────────────────
    brand = await brand_svc.create_brand_manual(
        user_id=creator_id,
        payload={
            "name": "QuinoaSnack Pro",
            "product_type": "Healthy snack with quinoa",
            "tone": "Fun but professional",
            "audience": "Gen Z, 18-26",
            "visual_rules": "Lime green dominant, white background, logo min 80px",
            "forbidden_words": ["cheap", "diet", "artificial"],
            "key_messages": ["real ingredients", "sustainable", "energizing"],
        },
    )
    assert brand["sections_embedded"] == 5, brand
    assert {"TONE", "AUDIENCE", "FORBIDDEN", "VISUAL", "MESSAGING"} <= set(brand["sections"])
    _ok(f"Module I — brand_id={brand['brand_id'][:8]}…  5 sections embedded")
    brand_id = UUID(brand["brand_id"])

    # ── Module II — happy path ───────────────────────────────
    gen = await content_svc.generate(
        creator_id=creator_id,
        brand_id=brand_id,
        content_type=ContentType.PRODUCT_DESCRIPTION,
        request="Write a short Instagram description for our snack",
    )
    assert gen["status"] == "pending", gen
    assert gen["content_id"], gen
    assert gen["content"], gen
    assert gen["retrieved_chunks"], gen
    _ok(
        f"Module II happy — content saved, "
        f"chunks={[c['section'] for c in gen['retrieved_chunks']]}"
    )
    content_id = UUID(gen["content_id"])

    # ── Module II — forbidden-word block ─────────────────────
    blocked = await content_svc.generate(
        creator_id=creator_id,
        brand_id=brand_id,
        content_type=ContentType.PRODUCT_DESCRIPTION,
        request="Write copy describing it as a cheap diet snack",
    )
    assert blocked["status"] == "blocked", blocked
    assert blocked["content"] is None
    assert blocked["content_id"] is None  # NOT persisted
    assert blocked["conflicts"], blocked
    _ok(f"Module II conflict — generation blocked, {len(blocked['conflicts'])} conflict(s)")

    # ── Module III A — text approval ─────────────────────────
    text_decision = await audit_svc.decide_text(
        content_id=content_id,
        actor_id=approver_a_id,
        decision="approved_text",
        notes="tone is on-brand",
    )
    assert text_decision["status"] == "approved_text", text_decision
    _ok("Module III A — text approved by Approver A")

    # ── Module III B — image audit ───────────────────────────
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4096
    final = await audit_svc.audit_image(
        content_id=content_id,
        actor_id=approver_b_id,
        image_bytes=fake_png,
        mime_type="image/png",
    )
    assert final["status"] in {"approved", "rejected"}, final
    assert final["audit_result"], final
    assert "checks" in final["audit_result"]
    _ok(
        f"Module III B — image audited, status={final['status']}, "
        f"checks={len(final['audit_result']['checks'])}"
    )

    # ── Verify content is now in repository in correct state ─
    saved = await content_repo.get(content_id)
    assert saved is not None
    assert saved.status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}
    _ok(f"Persistence — final status persisted as {saved.status.value}")

    # ── Listing ──────────────────────────────────────────────
    items = await content_repo.list(brand_id=brand_id)
    assert len(items) >= 1
    _ok(f"Listing — {len(items)} item(s) found for brand")

    print()
    print("✅  Full creator → approver-a → approver-b flow works end-to-end in mock mode.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
