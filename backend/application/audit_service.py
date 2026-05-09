"""AuditService — Module III. Approver A text decision + Approver B Gemini Vision audit."""


import logging
import time
from typing import Any, Optional
from uuid import UUID

from ..domain.brand import BrandRepository, BrandSection
from ..domain.content import (
    ApprovalStateMachine,
    ApprovalStatus,
    ContentItem,
    ContentRepository,
    InvalidTransitionError,
)
from ..infrastructure.embedding_service import EmbeddingService
from ..infrastructure.gemini_client import GeminiClient
from ..infrastructure.langfuse_client import Tracer

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(
        self,
        content_repo: ContentRepository,
        brand_repo: BrandRepository,
        gemini: GeminiClient,
        embedder: EmbeddingService,
        tracer: Tracer,
    ) -> None:
        self.content_repo = content_repo
        self.brand_repo = brand_repo
        self.gemini = gemini
        self.embedder = embedder
        self.tracer = tracer

    # ─────────────────────────────────────────────────────────────
    # Approver A
    # ─────────────────────────────────────────────────────────────
    async def decide_text(
        self,
        *,
        content_id: UUID,
        actor_id: UUID,
        decision: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        item = await self.content_repo.get(content_id)
        if item is None:
            raise ValueError(f"Content item {content_id} not found")

        with self.tracer.trace(
            "audit-text-decision",
            input_data={
                "content_id": str(content_id),
                "actor_id": str(actor_id),
                "decision": decision,
            },
        ) as t:
            try:
                if decision == "approved_text":
                    ApprovalStateMachine.approve_text(item, actor_id, notes)
                elif decision == "rejected":
                    ApprovalStateMachine.reject_text(
                        item, actor_id, notes or "Rejected by Approver A"
                    )
                else:
                    raise ValueError(
                        f"Invalid decision '{decision}'. Allowed: approved_text | rejected"
                    )
            except InvalidTransitionError as e:
                t.set_output({"error": str(e), "status": item.status.value})
                raise

            await self.content_repo.update(item)
            output = {
                "content_id": str(item.id),
                "status": item.status.value,
                "approver_a_notes": item.approver_a_notes,
                "rejection_reason": item.rejection_reason,
            }
            t.span(
                "state-transition",
                output_data=output,
                latency_ms=0,
                metadata={"new_status": item.status.value},
            )
            t.set_output(output)
            return output

    # ─────────────────────────────────────────────────────────────
    # Approver B
    # ─────────────────────────────────────────────────────────────
    async def audit_image(
        self,
        *,
        content_id: UUID,
        actor_id: UUID,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        item = await self.content_repo.get(content_id)
        if item is None:
            raise ValueError(f"Content item {content_id} not found")
        if item.status != ApprovalStatus.APPROVED_TEXT:
            raise InvalidTransitionError(
                f"Image audit requires APPROVED_TEXT, current status={item.status.value}"
            )

        manual = await self.brand_repo.get_manual(item.brand_id)
        if manual is None:
            raise ValueError("Brand manual missing — cannot audit without visual rules")

        with self.tracer.trace(
            "audit-image-multimodal",
            input_data={
                "content_id": str(content_id),
                "actor_id": str(actor_id),
                "image_bytes": len(image_bytes),
                "mime_type": mime_type,
            },
        ) as t:

            # 1) Retrieve VISUAL section from RAG (section-filtered)
            t0 = time.time()
            query_embedding = await self.embedder.embed(
                "visual rules logo color background typography", task_type="retrieval_query"
            )
            visual_chunks = await self.brand_repo.search_chunks(
                brand_id=manual.id,
                query_embedding=query_embedding,
                top_k=3,
                min_similarity=0.0,
                section_filter=BrandSection.VISUAL,
            )
            visual_rules_text = (
                "\n\n".join(c.content for c, _ in visual_chunks) if visual_chunks else ""
            )
            retrieval_ms = int((time.time() - t0) * 1000)
            t.span(
                "rag-retrieval-visual",
                input_data={"section_filter": "VISUAL"},
                output_data={
                    "chunks_retrieved": len(visual_chunks),
                    "rules_chars": len(visual_rules_text),
                },
                latency_ms=retrieval_ms,
            )

            # 2) Multimodal audit
            t0 = time.time()
            audit = await self.gemini.audit_image(
                image_bytes=image_bytes,
                mime_type=mime_type,
                visual_rules=visual_rules_text,
                brand_name=manual.name,
            )
            audit_ms = int((time.time() - t0) * 1000)
            t.span(
                "gemini-multimodal-audit",
                input_data={
                    "model": self.gemini.settings.gemini_vision_model,
                    "image_kb": len(image_bytes) // 1024,
                    "mime_type": mime_type,
                },
                output_data={
                    "compliant": audit.get("compliant"),
                    "checks": audit.get("checks"),
                    "summary": audit.get("summary"),
                },
                latency_ms=audit_ms,
                metadata={"model": self.gemini.settings.gemini_vision_model},
            )

            # 3) Drive state machine
            ApprovalStateMachine.finalize_image_audit(item, actor_id, audit)
            await self.content_repo.update(item)

            output = {
                "content_id": str(item.id),
                "status": item.status.value,
                "audit_result": item.audit_result,
                "rejection_reason": item.rejection_reason,
            }
            t.set_output(output)
            return output
