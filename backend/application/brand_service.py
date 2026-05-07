"""
BrandService — Module I (Brand DNA Architect).

Responsibilities:
  1. Generate the structured brand manual via the LLM
  2. Materialize 5 BrandChunks (one per canonical section)
  3. Embed each chunk and persist
  4. Trace the whole flow to Langfuse
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from ..domain.brand import (
    BrandChunk,
    BrandManual,
    BrandRepository,
    BrandSection,
    ForbiddenWords,
)
from ..infrastructure.embedding_service import EmbeddingService
from ..infrastructure.groq_client import GroqClient
from ..infrastructure.langfuse_client import Tracer

logger = logging.getLogger(__name__)


class BrandService:
    def __init__(
        self,
        repo: BrandRepository,
        groq: GroqClient,
        embedder: EmbeddingService,
        tracer: Tracer,
    ) -> None:
        self.repo = repo
        self.groq = groq
        self.embedder = embedder
        self.tracer = tracer

    async def create_brand_manual(
        self,
        *,
        user_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        End-to-end Module I flow.
        Returns: {brand_id, name, sections_embedded, sections, raw_manual}
        """
        with self.tracer.trace(
            "brand-dna-generation",
            input_data={
                "user_id": str(user_id),
                "name": payload.get("name"),
                "product_type": payload.get("product_type"),
            },
        ) as t:
            # 1) Generate the structured manual
            t0 = time.time()
            sections_text = await self.groq.generate_brand_manual(payload)
            llm_ms = int((time.time() - t0) * 1000)
            t.span(
                "llm-brand-manual-generation",
                input_data={"payload_keys": list(payload.keys())},
                output_data={"sections_returned": list(sections_text.keys())},
                latency_ms=llm_ms,
                metadata={"model": self.groq.settings.groq_model, "mocked": self.groq.is_mocked},
            )

            # 2) Build the aggregate
            sections_enum: dict[BrandSection, str] = {}
            for s in BrandSection.all():
                if s.value in sections_text:
                    sections_enum[s] = sections_text[s.value]

            # FORBIDDEN section: ensure it explicitly lists the user-provided words
            forbidden = ForbiddenWords.from_iterable(payload.get("forbidden_words"))
            if forbidden:
                listed = ", ".join(forbidden)
                existing = sections_enum.get(BrandSection.FORBIDDEN, "")
                if listed.lower() not in (existing or "").lower():
                    sections_enum[BrandSection.FORBIDDEN] = (
                        f"Never use: {listed}. " + (existing or "")
                    ).strip()

            raw_manual = "\n\n".join(
                f"## {s.value}\n{sections_enum[s]}" for s in BrandSection.all() if s in sections_enum
            )

            manual = BrandManual(
                user_id=user_id,
                name=payload["name"],
                product_type=payload.get("product_type", ""),
                tone=payload.get("tone", ""),
                audience=payload.get("audience", ""),
                raw_manual=raw_manual,
                sections=sections_enum,
            )

            # 3) Persist manual
            await self.repo.save_manual(manual)

            # 4) Embed + persist chunks
            t0 = time.time()
            chunks = manual.chunks()
            embeddings = await self.embedder.embed_batch(
                [c.content for c in chunks], task_type="retrieval_document"
            )
            for c, e in zip(chunks, embeddings):
                c.embedding = e
            saved = await self.repo.save_chunks(chunks)
            embed_ms = int((time.time() - t0) * 1000)
            t.span(
                "embed-and-store-chunks",
                input_data={"chunk_count": len(chunks)},
                output_data={
                    "saved": saved,
                    "sections": [c.section.value for c in chunks],
                    "dim": len(embeddings[0]) if embeddings else 0,
                },
                latency_ms=embed_ms,
                metadata={"mocked": self.embedder.is_mocked},
            )

            output = {
                "brand_id": str(manual.id),
                "name": manual.name,
                "sections_embedded": saved,
                "sections": {s.value: v for s, v in sections_enum.items()},
                "raw_manual": raw_manual,
                "message": "Brand manual created and indexed successfully",
            }
            t.set_output(output)
            return output

    async def list_brands(self, user_id: UUID) -> list[dict[str, Any]]:
        manuals = await self.repo.list_manuals(user_id)
        return [
            {
                "brand_id": str(m.id),
                "name": m.name,
                "product_type": m.product_type,
                "created_at": m.created_at.isoformat(),
            }
            for m in manuals
        ]
