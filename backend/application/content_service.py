"""ContentService — Module II (Creative Engine). RAG-grounded content generation."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional
from uuid import UUID

from ..domain.brand import BrandRepository, BrandSection, ForbiddenWords
from ..domain.content import (
    ApprovalStatus,
    ConflictItem,
    ContentItem,
    ContentRepository,
    ContentType,
    RetrievedChunkRef,
)
from ..infrastructure.embedding_service import EmbeddingService
from ..infrastructure.groq_client import GroqClient
from ..infrastructure.langfuse_client import Tracer

logger = logging.getLogger(__name__)


class ContentService:
    def __init__(
        self,
        brand_repo: BrandRepository,
        content_repo: ContentRepository,
        groq: GroqClient,
        embedder: EmbeddingService,
        tracer: Tracer,
    ) -> None:
        self.brand_repo = brand_repo
        self.content_repo = content_repo
        self.groq = groq
        self.embedder = embedder
        self.tracer = tracer

    async def generate(
        self,
        *,
        creator_id: UUID,
        brand_id: UUID,
        content_type: ContentType,
        request: str,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
    ) -> dict[str, Any]:
        from ..config import get_settings

        settings = get_settings()
        top_k = top_k or settings.rag_top_k
        # Lower the floor automatically when on the mock embedder, whose
        # hash-based vectors yield ~0.3-0.5 typical similarity (vs ~0.6+
        # from real Gemini embeddings). Real-mode keeps the strict default.
        if min_similarity is None:
            base = settings.rag_min_similarity
            if self.embedder.is_mocked and base >= 0.5:
                min_similarity = 0.2
            else:
                min_similarity = base

        with self.tracer.trace(
            "content-generation",
            input_data={
                "creator_id": str(creator_id),
                "brand_id": str(brand_id),
                "content_type": content_type.value,
                "request": request,
            },
        ) as t:

            # 1) Verify brand exists
            manual = await self.brand_repo.get_manual(brand_id)
            if manual is None:
                output = {
                    "content_id": None,
                    "content": None,
                    "conflicts": [
                        {
                            "rule": "BRAND_NOT_FOUND",
                            "violation": f"No brand manual exists for id {brand_id}.",
                            "suggestion": "Create the brand manual first via /api/v1/brand-dna.",
                        }
                    ],
                    "retrieved_chunks": [],
                    "status": "blocked",
                }
                t.set_output(output)
                return output

            # 2) Embed the user request
            t0 = time.time()
            query_embedding = await self.embedder.embed(request, task_type="retrieval_query")
            embed_ms = int((time.time() - t0) * 1000)

            # 3) RAG search
            t0 = time.time()
            scored = await self.brand_repo.search_chunks(
                brand_id=brand_id,
                query_embedding=query_embedding,
                top_k=top_k,
                min_similarity=min_similarity,
            )
            retrieval_ms = int((time.time() - t0) * 1000)

            t.span(
                "rag-retrieval",
                input_data={"query": request, "top_k": top_k, "min_similarity": min_similarity},
                output_data={
                    "chunks_retrieved": len(scored),
                    "top_similarity": round(scored[0][1], 4) if scored else 0.0,
                    "sections": [c.section.value for c, _ in scored],
                },
                latency_ms=embed_ms + retrieval_ms,
                metadata={
                    "embed_ms": embed_ms,
                    "search_ms": retrieval_ms,
                    "mocked_embedder": self.embedder.is_mocked,
                },
            )

            # 4) Block if no chunks above threshold
            if not scored:
                output = {
                    "content_id": None,
                    "content": None,
                    "conflicts": [
                        {
                            "rule": "NO_BRAND_CONTEXT",
                            "violation": (
                                f"No brand chunks above similarity threshold {min_similarity} "
                                "for this request. Generation refused — output would not be brand-grounded."
                            ),
                            "suggestion": (
                                "Try a request more closely aligned with the brand's tone, "
                                "audience, visual rules, or messaging. Or lower the threshold."
                            ),
                        }
                    ],
                    "retrieved_chunks": [],
                    "status": "blocked",
                }
                t.set_output(output)
                return output

            # 5) LLM generation with retrieved context
            forbidden = await self._extract_forbidden_words(scored, manual)
            t0 = time.time()
            gen = await self.groq.generate_content(
                brand_name=manual.name,
                content_type=content_type.value,
                request=request,
                retrieved_context=[(c.section.value, c.content) for c, _ in scored],
                forbidden_words=list(forbidden),
            )
            llm_ms = int((time.time() - t0) * 1000)
            t.span(
                "llm-generation",
                input_data={
                    "model": self.groq.settings.groq_model,
                    "temperature": self.groq.settings.llm_temperature,
                    "system_context_sections": [c.section.value for c, _ in scored],
                    "user_request": request,
                },
                output_data={
                    "content_present": gen.get("content") is not None,
                    "conflicts": gen.get("conflicts", []),
                },
                latency_ms=llm_ms,
                metadata={"mocked": self.groq.is_mocked},
            )

            # 6) Post-generation conflict scan (defense-in-depth)
            extra_conflicts = self._post_scan_for_forbidden(gen.get("content"), forbidden)
            all_conflicts = list(gen.get("conflicts") or []) + extra_conflicts

            retrieved_refs = [
                RetrievedChunkRef(chunk_id=c.id, section=c.section.value, similarity=sim)
                for c, sim in scored
            ]

            # 7) Conflict path - block, do not save
            if all_conflicts and gen.get("content") is None:
                output = {
                    "content_id": None,
                    "content": None,
                    "conflicts": all_conflicts,
                    "retrieved_chunks": [r.to_dict() for r in retrieved_refs],
                    "status": "blocked",
                }
                t.span(
                    "conflict-detection",
                    output_data={"conflicts_found": len(all_conflicts), "blocked": True},
                    latency_ms=0,
                )
                t.set_output(output)
                return output

            # 8) Persist as PENDING
            item = ContentItem(
                brand_id=brand_id,
                creator_id=creator_id,
                content_type=content_type,
                original_request=request,
                content=gen.get("content"),
                status=ApprovalStatus.PENDING,
                conflicts=[
                    ConflictItem(
                        rule=c.get("rule", ""),
                        violation=c.get("violation", ""),
                        suggestion=c.get("suggestion", ""),
                    )
                    for c in all_conflicts
                ],
                retrieved_chunks=retrieved_refs,
            )
            await self.content_repo.save(item)

            output = {
                "content_id": str(item.id),
                "content": item.content,
                "conflicts": [c.to_dict() for c in item.conflicts],
                "retrieved_chunks": [r.to_dict() for r in item.retrieved_chunks],
                "status": item.status.value,
            }
            t.span(
                "conflict-detection",
                output_data={"conflicts_found": len(item.conflicts), "blocked": False},
                latency_ms=0,
            )
            t.set_output(output)
            return output

    async def get(self, item_id: UUID) -> Optional[dict[str, Any]]:
        item = await self.content_repo.get(item_id)
        if item is None:
            return None
        return _item_to_dict(item)

    async def list_for_user(
        self,
        *,
        user_id: UUID,
        role: str,
        status: Optional[ApprovalStatus] = None,
        brand_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        creator_filter = user_id if role == "creator" else None
        items = await self.content_repo.list(
            creator_id=creator_filter,
            status=status,
            brand_id=brand_id,
            limit=limit,
            offset=offset,
        )
        return [_item_to_dict(i) for i in items]

    async def _extract_forbidden_words(self, scored, manual) -> list[str]:
        """Pull forbidden words out of the FORBIDDEN chunk text."""
        forbidden_chunks = await self.brand_repo.search_chunks(
            brand_id=manual.id,
            query_embedding=await self.embedder.embed(
                "forbidden words restricted prohibited", task_type="retrieval_query"
            ),
            top_k=1,
            min_similarity=0.0,
            section_filter=BrandSection.FORBIDDEN,
        )
        text = ""
        if forbidden_chunks:
            text = forbidden_chunks[0][0].content
        words = []
        for line in text.split("."):
            if ":" in line:
                tail = line.split(":", 1)[1]
                words.extend(w.strip(" ,.") for w in tail.split(","))
        cleaned = [w.lower() for w in words if w and len(w) > 1 and " " not in w]
        return list(dict.fromkeys(cleaned))[:25]

    def _post_scan_for_forbidden(
        self, content: Optional[str], forbidden: list[str]
    ) -> list[dict[str, str]]:
        if not content or not forbidden:
            return []
        fw = ForbiddenWords.from_iterable(forbidden)
        hits = fw.contains(content)
        if not hits:
            return []
        return [
            {
                "rule": "FORBIDDEN_POST_SCAN",
                "violation": f"Generated text contained prohibited words: {', '.join(hits)}.",
                "suggestion": "The model slipped - regenerate. Consider lowering temperature.",
            }
        ]


def _item_to_dict(item: ContentItem) -> dict[str, Any]:
    return {
        "content_id": str(item.id),
        "brand_id": str(item.brand_id),
        "creator_id": str(item.creator_id),
        "content_type": item.content_type.value,
        "original_request": item.original_request,
        "content": item.content,
        "status": item.status.value,
        "conflicts": [c.to_dict() for c in item.conflicts],
        "retrieved_chunks": [r.to_dict() for r in item.retrieved_chunks],
        "approver_a_notes": item.approver_a_notes,
        "audit_result": item.audit_result,
        "rejection_reason": item.rejection_reason,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
