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

create unique index if not exists embeddings_source_chunk_id_idx
  on public.embeddings (source, chunk_id);

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
    user_id is null
    or user_id = auth.uid()
  );

drop policy if exists "embeddings_insert_own" on public.embeddings;
create policy "embeddings_insert_own"
  on public.embeddings
  for insert
  to authenticated
  with check (
    user_id is null
    or user_id = auth.uid()
  );

drop policy if exists "embeddings_update_own" on public.embeddings;
create policy "embeddings_update_own"
  on public.embeddings
  for update
  to authenticated
  using (
    user_id is null
    or user_id = auth.uid()
  )
  with check (
    user_id is null
    or user_id = auth.uid()
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
