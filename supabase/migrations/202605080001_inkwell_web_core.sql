create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  display_name text,
  created_at timestamptz not null default now()
);

create table if not exists public.sources (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  url text not null,
  normalized_url text not null,
  source_type text,
  title text,
  created_at timestamptz not null default now()
);

create table if not exists public.import_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_id uuid not null references public.sources(id) on delete cascade,
  status text not null default 'queued'
    check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  stage text default 'queued'
    check (stage is null or stage in (
      'queued',
      'fetching_source',
      'extracting_transcript',
      'generating_notes',
      'saving_result',
      'done'
    )),
  worker_run_id text,
  error_code text,
  error_message text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create table if not exists public.notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_id uuid not null references public.sources(id) on delete cascade,
  import_job_id uuid not null references public.import_jobs(id) on delete cascade,
  title text not null,
  body_markdown text not null,
  summary text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists sources_user_created_at_idx
  on public.sources (user_id, created_at desc);

create index if not exists sources_user_normalized_url_idx
  on public.sources (user_id, normalized_url);

create index if not exists import_jobs_user_created_at_idx
  on public.import_jobs (user_id, created_at desc);

create index if not exists import_jobs_user_status_idx
  on public.import_jobs (user_id, status);

create unique index if not exists notes_import_job_id_idx
  on public.notes (import_job_id);

create index if not exists notes_user_created_at_idx
  on public.notes (user_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name)
  values (
    new.id,
    coalesce(new.email, ''),
    coalesce(new.raw_user_meta_data->>'name', new.raw_user_meta_data->>'full_name')
  )
  on conflict (id) do update
    set email = excluded.email;

  return new;
end;
$$;

drop trigger if exists set_notes_updated_at on public.notes;
create trigger set_notes_updated_at
before update on public.notes
for each row
execute function public.set_updated_at();

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.sources enable row level security;
alter table public.import_jobs enable row level security;
alter table public.notes enable row level security;

drop policy if exists "profiles are owner-readable" on public.profiles;
create policy "profiles are owner-readable"
on public.profiles
for select
to authenticated
using ((select auth.uid()) = id);

drop policy if exists "profiles are owner-updatable" on public.profiles;
create policy "profiles are owner-updatable"
on public.profiles
for update
to authenticated
using ((select auth.uid()) = id)
with check ((select auth.uid()) = id);

drop policy if exists "sources are owner-selectable" on public.sources;
create policy "sources are owner-selectable"
on public.sources
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "sources are owner-insertable" on public.sources;
create policy "sources are owner-insertable"
on public.sources
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "sources are owner-updatable" on public.sources;
create policy "sources are owner-updatable"
on public.sources
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "sources are owner-deletable" on public.sources;
create policy "sources are owner-deletable"
on public.sources
for delete
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "jobs are owner-selectable" on public.import_jobs;
create policy "jobs are owner-selectable"
on public.import_jobs
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "jobs are owner-insertable" on public.import_jobs;
create policy "jobs are owner-insertable"
on public.import_jobs
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "jobs are owner-updatable" on public.import_jobs;
create policy "jobs are owner-updatable"
on public.import_jobs
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "notes are owner-selectable" on public.notes;
create policy "notes are owner-selectable"
on public.notes
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "notes are owner-insertable" on public.notes;
create policy "notes are owner-insertable"
on public.notes
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "notes are owner-updatable" on public.notes;
create policy "notes are owner-updatable"
on public.notes
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "notes are owner-deletable" on public.notes;
create policy "notes are owner-deletable"
on public.notes
for delete
to authenticated
using ((select auth.uid()) = user_id);

grant usage on schema public to anon, authenticated, service_role;
grant select, insert, update, delete on
  public.profiles,
  public.sources,
  public.import_jobs,
  public.notes
to authenticated;
grant all on
  public.profiles,
  public.sources,
  public.import_jobs,
  public.notes
to service_role;
