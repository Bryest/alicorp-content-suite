"""
Dependency wiring.

Lazily constructed singletons for repos, infra clients, services, and
the Langfuse tracer. FastAPI routes pull them via Depends().
"""


from functools import lru_cache

from ..application.audit_service import AuditService
from ..application.brand_service import BrandService
from ..application.content_service import ContentService
from ..infrastructure.embedding_service import EmbeddingService
from ..infrastructure.gemini_client import GeminiClient
from ..infrastructure.groq_client import GroqClient
from ..infrastructure.langfuse_client import Tracer, get_tracer
from ..infrastructure.supabase_client import (
    SupabaseBrandRepository,
    SupabaseContentRepository,
)


@lru_cache
def _brand_repo() -> SupabaseBrandRepository:
    return SupabaseBrandRepository()


@lru_cache
def _content_repo() -> SupabaseContentRepository:
    return SupabaseContentRepository()


@lru_cache
def _embedder() -> EmbeddingService:
    return EmbeddingService()


@lru_cache
def _groq() -> GroqClient:
    return GroqClient()


@lru_cache
def _gemini() -> GeminiClient:
    return GeminiClient()


@lru_cache
def _tracer() -> Tracer:
    return get_tracer()


def get_brand_service() -> BrandService:
    return BrandService(repo=_brand_repo(), groq=_groq(), embedder=_embedder(), tracer=_tracer())


def get_content_service() -> ContentService:
    return ContentService(
        brand_repo=_brand_repo(),
        content_repo=_content_repo(),
        groq=_groq(),
        embedder=_embedder(),
        tracer=_tracer(),
    )


def get_audit_service() -> AuditService:
    return AuditService(
        content_repo=_content_repo(),
        brand_repo=_brand_repo(),
        gemini=_gemini(),
        embedder=_embedder(),
        tracer=_tracer(),
    )
