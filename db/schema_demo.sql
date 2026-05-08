-- ============================================================
-- Content Suite — Supabase / Postgres schema (DEMO version)
--
-- This version drops all foreign keys to auth.users so it works
-- with the app's MOCK auth (3 demo users with deterministic UUIDs
-- that don't exist in Supabase Auth). RLS is also disabled because
-- the service_role key bypasses it anyway, and the FastAPI layer
-- enforces RBAC via require_roles middleware.
--
-- Paste this entire file into Supabase Dashboard → SQL Editor → Run.
-- ============================================================

-- ─── Extensions ──────────────────────────────────────────────
create extension if not exists vector;
create extension if not exists "uuid-ossp";


-- ─── Enums ───────────────────────────────────────────────────
do $$ begin
  create type approval_status as enum ('pending', 'approved_text', 'approved', 'rejected');
exception when duplicate_object then null; end $$;

do $$ begin
  create type content_type_enum as enum (
    'product_description', 'video_script', 'image_prompt', 'social_post', 'tagline'
  );
exception when duplicate_object then null; end $$;


-- ─── Brand manuals ───────────────────────────────────────────
create table if not exists brand_manuals (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid,                        -- mock-auth UUID, no FK
  name            text not null,
  product_type    text,
  target_audience text,
  tone            text,
  raw_manual      text,
  version         integer default 1,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index if not exists brand_manuals_user_id_idx on brand_manuals(user_id);


-- ─── Brand chunks (RAG vectors) ──────────────────────────────
create table if not exists brand_chunks (
  id          uuid primary key default uuid_generate_v4(),
  brand_id    uuid references brand_manuals(id) on delete cascade,
  section     text not null,
  content     text not null,
  embedding   vector(768),
  version     integer default 1,
  created_at  timestamptz default now()
);

create index if not exists brand_chunks_embedding_idx
  on brand_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create index if not exists brand_chunks_brand_id_idx on brand_chunks(brand_id);
create index if not exists brand_chunks_section_idx  on brand_chunks(section);


-- ─── Semantic search RPC ─────────────────────────────────────
create or replace function match_brand_chunks(
  query_embedding  vector(768),
  p_brand_id       uuid,
  match_count      int     default 3,
  min_similarity   float   default 0.5
)
returns table (
  id          uuid,
  brand_id    uuid,
  section     text,
  content     text,
  similarity  float
)
language sql stable as $$
  select
    bc.id,
    bc.brand_id,
    bc.section,
    bc.content,
    1 - (bc.embedding <=> query_embedding) as similarity
  from brand_chunks bc
  where bc.brand_id = p_brand_id
    and 1 - (bc.embedding <=> query_embedding) > min_similarity
  order by bc.embedding <=> query_embedding
  limit match_count;
$$;


-- ─── Content items ───────────────────────────────────────────
create table if not exists content_items (
  id                uuid primary key default uuid_generate_v4(),
  brand_id          uuid references brand_manuals(id),
  creator_id        uuid,                                 -- mock-auth UUID, no FK
  content_type      content_type_enum not null,
  original_request  text,
  content           text,
  status            approval_status default 'pending',
  conflicts         jsonb default '[]',
  retrieved_chunks  jsonb default '[]',
  approver_a_id     uuid,                                 -- mock-auth UUID, no FK
  approver_a_notes  text,
  approver_a_at     timestamptz,
  approver_b_id     uuid,                                 -- mock-auth UUID, no FK
  audit_result      jsonb,
  rejection_reason  text,
  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);

create index if not exists content_items_brand_id_idx   on content_items(brand_id);
create index if not exists content_items_creator_id_idx on content_items(creator_id);
create index if not exists content_items_status_idx     on content_items(status);

create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists content_items_updated_at on content_items;
create trigger content_items_updated_at
  before update on content_items
  for each row execute function update_updated_at();


-- ─── RLS disabled for the demo ───────────────────────────────
-- The service_role key (used by the FastAPI backend) bypasses RLS
-- automatically. RBAC is enforced at the API layer via the
-- require_roles middleware, so RLS would only get in the way for
-- this mock-auth demo.
alter table brand_manuals  disable row level security;
alter table brand_chunks   disable row level security;
alter table content_items  disable row level security;


-- ─── Done ────────────────────────────────────────────────────
-- After running this, you have:
--   • brand_manuals + brand_chunks + content_items tables
--   • pgvector IVFFlat index for cosine similarity
--   • match_brand_chunks RPC for top-K retrieval
--   • content_items.updated_at auto-updating trigger
-- The backend talks to this via supabase-py + service_role key.
