# Content Suite

> Brand-aware content generation with RAG, multimodal audit, and full Langfuse observability.
> Built for the **Alicorp IAGen Pleno** technical challenge.

A FastAPI + Next.js platform that solves brand inconsistency at scale: brand managers define the brand DNA once, every piece of content is generated against that DNA via RAG, and every image passes a multimodal audit before approval. Every LLM call is traced.

## Architecture

- **Backend** — FastAPI (hexagonal / DDD). Domain layer has zero external dependencies; adapters in `infrastructure/` implement the ports.
- **Frontend** — Next.js 14 App Router with role-based pages (Creator, Approver A, Approver B).
- **Database** — Supabase Postgres + pgvector (768-dim embeddings, IVFFlat index, RLS policies on every table).
- **LLMs** — Groq Llama 3.3 70B (text), Gemini 1.5 Flash (multimodal audit), Google text-embedding-004 (RAG).
- **Observability** — Langfuse traces every retrieval, prompt, response, and latency.

```
backend/
├── domain/          # entities, value objects, state machine, repository ports
├── application/     # BrandService, ContentService, AuditService
├── infrastructure/  # supabase, groq, gemini, langfuse, embedding adapters
└── api/             # FastAPI routes + JWT auth + RBAC middleware
frontend/
└── src/app/         # creator, approver-a, approver-b pages
db/
└── schema.sql       # Supabase schema + RLS + match_brand_chunks RPC
```

## Modules

| # | Module | Endpoint | Role |
|---|--------|----------|------|
| I | Brand DNA Architect | `POST /api/v1/brand-dna` | Creator |
| II | Creative Engine (RAG) | `POST /api/v1/generate` | Creator |
| III-A | Text approval | `PATCH /api/v1/audit/text/{id}` | Approver A |
| III-B | Multimodal image audit | `POST /api/v1/audit/image/{id}` | Approver B |
| IV | Observability | every LLM call traced | — |

## Run locally

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
cd ..
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

The system runs end-to-end **without any API keys** — each adapter detects missing credentials and switches to a deterministic mock. Add real keys to `backend/.env` to flip individual services to production providers.

## Test credentials

| Role | Email | Password |
|---|---|---|
| Creator | creator@test.com | Test1234! |
| Approver A | approver.a@test.com | Test1234! |
| Approver B | approver.b@test.com | Test1234! |

## Validation

End-to-end smoke test (no HTTP server required):

```bash
python -m backend.tests.smoke_e2e_no_fastapi
```

Covers: brand creation → RAG-grounded generation → forbidden-word block → Approver A text decision → Approver B multimodal audit → final state.

## Deployment

- **Backend**: `render.yaml` ready for Render
- **Frontend**: `frontend/vercel.json` ready for Vercel
- **Database**: paste `db/schema.sql` into Supabase SQL Editor

## Stack

FastAPI · Next.js 14 · Supabase pgvector · Groq Llama 3.3 · Gemini 1.5 · Langfuse · Tailwind

## Security & production notes

This deployment is hardened for a public demo:

- **JWT-protected endpoints** — every route except `/health`, `/auth/login`, and `/auth/demo-users` requires a Bearer token. Cross-role calls return 403.
- **Per-IP rate limits** (slowapi):
  - `/auth/login` — 5/min  · prevents credential stuffing
  - `/brand-dna`, `/generate`, `/audit/image` — 5/min each · caps LLM cost
  - `/audit/text` — 20/min  · DB-only, no LLM
  - everything else — 60/min
- **Demo credentials hidden in production** — `GET /auth/demo-users` returns 404 when `ENVIRONMENT=production` and Supabase is real.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection` set on every response.
- **Per-request access log** — `METHOD path status latency_ms ip` written to stdout, visible in Render logs.
- **Defense in depth (when Supabase is real)** — RLS policies enforce role-based access at the SQL layer, independent of the API.

**Caveat**: rate-limit state lives in process memory. Single Render free-tier instance is fine; multi-instance scale-out needs a Redis-backed limiter.

**Before production**, in your hosting provider's environment variables: rotate `MOCK_JWT_SECRET` to a fresh random string, set `ENVIRONMENT=production`, and (recommended) wire a real `SUPABASE_JWT_SECRET` so JWTs are issued by Supabase Auth instead of by the demo login endpoint.
