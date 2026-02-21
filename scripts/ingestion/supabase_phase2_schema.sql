-- Phase 2 Supabase schema for document ingestion and retrieval
-- Run in Supabase SQL Editor.

create extension if not exists vector;

create table if not exists public.embeddings (
  id text primary key,
  user_id uuid,
  source text not null,
  chunk_id text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

-- Incremental migration safety for existing tables:
-- 1) ensure user_id exists,
-- 2) backfill from metadata.user_id when available,
-- 3) remove legacy null-user rows,
-- 4) enforce NOT NULL.
alter table if exists public.embeddings
  add column if not exists user_id uuid;

update public.embeddings
set user_id = (metadata->>'user_id')::uuid
where user_id is null
  and metadata ? 'user_id'
  and metadata->>'user_id' ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$';

delete from public.embeddings
where user_id is null;

alter table if exists public.embeddings
  alter column user_id set not null;

drop index if exists embeddings_source_chunk_id_idx;
create unique index if not exists embeddings_user_source_chunk_id_idx
  on public.embeddings (user_id, source, chunk_id);

create index if not exists embeddings_user_id_idx
  on public.embeddings (user_id);

create index if not exists embeddings_metadata_gin_idx
  on public.embeddings using gin (metadata);

-- Optional vector index for future semantic search queries.
create index if not exists embeddings_embedding_ivfflat_idx
  on public.embeddings
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

alter table public.embeddings enable row level security;

-- Service-role jobs can bypass RLS. For user-facing reads, only return own rows.
drop policy if exists "embeddings_select_own" on public.embeddings;
create policy "embeddings_select_own"
  on public.embeddings
  for select
  to authenticated
  using (
    auth.uid() is not null
    and user_id = auth.uid()
  );

drop policy if exists "embeddings_insert_own" on public.embeddings;
create policy "embeddings_insert_own"
  on public.embeddings
  for insert
  to authenticated
  with check (
    auth.uid() is not null
    and user_id = auth.uid()
  );

drop policy if exists "embeddings_update_own" on public.embeddings;
create policy "embeddings_update_own"
  on public.embeddings
  for update
  to authenticated
  using (
    auth.uid() is not null
    and user_id = auth.uid()
  )
  with check (
    auth.uid() is not null
    and user_id = auth.uid()
  );

drop policy if exists "embeddings_delete_own" on public.embeddings;
create policy "embeddings_delete_own"
  on public.embeddings
  for delete
  to authenticated
  using (
    auth.uid() is not null
    and user_id = auth.uid()
  );

-- Keep updated_at current on updates.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists set_embeddings_updated_at on public.embeddings;
create trigger set_embeddings_updated_at
before update on public.embeddings
for each row
execute function public.set_updated_at();

-- RPC helper for user-scoped upsert from authenticated clients.
create or replace function public.upsert_embedding_chunk(
  p_id text,
  p_user_id uuid,
  p_source text,
  p_chunk_id text,
  p_content text,
  p_metadata jsonb,
  p_embedding text
)
returns void
language plpgsql
security invoker
as $$
begin
  insert into public.embeddings (
    id,
    user_id,
    source,
    chunk_id,
    content,
    metadata,
    embedding
  ) values (
    p_id,
    p_user_id,
    p_source,
    p_chunk_id,
    p_content,
    coalesce(p_metadata, '{}'::jsonb),
    p_embedding::vector
  )
  on conflict (id)
  do update set
    source = excluded.source,
    chunk_id = excluded.chunk_id,
    content = excluded.content,
    metadata = excluded.metadata,
    embedding = excluded.embedding;
end;
$$;

-- RPC helper for vector similarity search behind PostgREST.
create or replace function public.match_embeddings(
  query_embedding text,
  match_count int default 5,
  match_threshold float default 0.1
)
returns table (
  id text,
  source text,
  chunk_id text,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
security invoker
as $$
  select
    e.id,
    e.source,
    e.chunk_id,
    e.content,
    e.metadata,
    1 - (e.embedding <=> query_embedding::vector) as similarity
  from public.embeddings as e
  where 1 - (e.embedding <=> query_embedding::vector) > match_threshold
  order by (e.embedding <=> query_embedding::vector) asc
  limit match_count;
$$;
