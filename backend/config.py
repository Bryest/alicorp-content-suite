"""Centralized settings (stdlib only). Missing API keys flip adapters into mock mode."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _csv(value: str) -> List[str]:
    return [s.strip() for s in (value or "").split(",") if s.strip()]


@dataclass
class Settings:
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    google_api_key: str = ""
    gemini_vision_model: str = "gemini-1.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000"])
    mock_jwt_secret: str = "alicorp-content-suite-dev-secret-change-me"
    rag_top_k: int = 3
    rag_min_similarity: float = 0.5
    llm_temperature: float = 0.2

    @property
    def supabase_mocked(self) -> bool:
        return not (self.supabase_url and self.supabase_service_role_key)

    @property
    def groq_mocked(self) -> bool:
        return not self.groq_api_key

    @property
    def google_mocked(self) -> bool:
        return not self.google_api_key

    @property
    def langfuse_mocked(self) -> bool:
        return not (self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def jwt_secret(self) -> str:
        return self.supabase_jwt_secret or self.mock_jwt_secret

    def mock_mode_summary(self) -> dict:
        return {
            "supabase": self.supabase_mocked,
            "groq": self.groq_mocked,
            "google": self.google_mocked,
            "langfuse": self.langfuse_mocked,
        }


@lru_cache
def get_settings() -> Settings:
    for p in (Path(".env"), Path("backend/.env")):
        _load_dotenv(p)
    s = Settings(
        supabase_url=_env("SUPABASE_URL"),
        supabase_service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_anon_key=_env("SUPABASE_ANON_KEY"),
        supabase_jwt_secret=_env("SUPABASE_JWT_SECRET"),
        groq_api_key=_env("GROQ_API_KEY"),
        groq_model=_env("GROQ_MODEL") or Settings.groq_model,
        google_api_key=_env("GOOGLE_API_KEY"),
        gemini_vision_model=_env("GEMINI_VISION_MODEL") or Settings.gemini_vision_model,
        gemini_embedding_model=_env("GEMINI_EMBEDDING_MODEL") or Settings.gemini_embedding_model,
        langfuse_public_key=_env("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=_env("LANGFUSE_SECRET_KEY"),
        langfuse_host=_env("LANGFUSE_HOST") or Settings.langfuse_host,
        environment=_env("ENVIRONMENT") or Settings.environment,
        log_level=_env("LOG_LEVEL") or Settings.log_level,
        cors_origins=_csv(_env("CORS_ORIGINS")) or ["http://localhost:3000", "http://localhost:3001"],
        mock_jwt_secret=_env("MOCK_JWT_SECRET") or Settings.mock_jwt_secret,
    )
    try:
        s.rag_top_k = int(_env("RAG_TOP_K") or 3)
        s.rag_min_similarity = float(_env("RAG_MIN_SIMILARITY") or 0.5)
        s.llm_temperature = float(_env("LLM_TEMPERATURE") or 0.2)
    except Exception:
        pass
    return s
