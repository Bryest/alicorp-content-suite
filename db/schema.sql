-- ============================================================
-- Content Suite — Supabase / Postgres schema
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

do $$ begin
  create type user_role as enum ('creator', 'approver_a', 'approver_b');
exception when duplicate_object then null; end $$;


-- ─── User roles ──────────────────────────────────────────────
create table if not exists user_roles (
  id          uuid primary key default uuid_generate_v4(),
  user_id     uuid references auth.users(id) on delete cascade,
  role        user_role not null,
  created_at  timestamptz default now(),
  unique(user_id)
);


-- ─── Brand manuals ───────────────────────────────────────────
create table if not exists brand_manuals (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid references auth.users(id),
  name            text not null,
  product_type    text,
  target_audience text,
  tone            text,
  raw_manual      text,
  version         integer default 1,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);


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
  creator_id        uuid references auth.users(id),
  content_type      content_type_enum not null,
  original_request  text,
  content           text,
  status            approval_status default 'pending',
  conflicts         jsonb default '[]',
  retrieved_chunks  jsonb default '[]',
  approver_a_id     uuid references auth.users(id),
  approver_a_notes  text,
  approver_a_at     timestamptz,
  approver_b_id     uuid references auth.users(id),
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


-- ─── Row Level Security ──────────────────────────────────────
alter table brand_manuals  enable row level security;
alter table brand_chunks   enable row level security;
alter table content_items  enable row level security;
alter table user_roles     enable row level security;

-- Creators see only their own brand manuals
drop policy if exists creators_own_brands on brand_manuals;
create policy creators_own_brands on brand_manuals
  for all using (user_id = auth.uid());

-- Creators see and create their own content
drop policy if exists creators_own_content on content_items;
create policy creators_own_content on content_items
  for all using (creator_id = auth.uid());

-- Approvers (A or B) see all content
drop policy if exists approvers_see_all_content on content_items;
create policy approvers_see_all_content on content_items
  for select using (
    exists (
      select 1 from user_roles
      where user_id = auth.uid()
        and role in ('approver_a', 'approver_b')
    )
  );

-- Approvers can update content (the API enforces *which* fields)
drop policy if exists approvers_update_content on content_items;
create policy approvers_update_content on content_items
  for update using (
    exists (
      select 1 from user_roles
      where user_id = auth.uid()
        and role in ('approver_a', 'approver_b')
    )
  );

-- Brand chunks readable by the manual's owner
drop policy if exists brand_chunks_owner on brand_chunks;
create policy brand_chunks_owner on brand_chunks
  for all using (
    exists (
      select 1 from brand_manuals m
      where m.id = brand_chunks.brand_id
        and m.user_id = auth.uid()
    )
  );

-- user_roles: users can read their own row
drop policy if exists user_roles_self_read on user_roles;
create policy user_roles_self_read on user_roles
  for select using (user_id = auth.uid());


-- ─── Demo seed (optional) ────────────────────────────────────
-- After creating the 3 demo users via Supabase Auth, run:
--   insert into user_roles (user_id, role) values
--     ('<creator-uuid>', 'creator'),
--     ('<approver-a-uuid>', 'approver_a'),
--     ('<approver-b-uuid>', 'approver_b');
