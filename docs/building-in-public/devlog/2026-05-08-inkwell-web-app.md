# Inkwell Web App Foundation

**Date:** 2026-05-08
**Author:** Codex

## Focus

Plan and start the first real Inkwell web app: an account-based saved-note library deployed on Vercel, backed by Supabase Auth/Postgres, with the existing Python pipeline running behind a Modal worker.

## Progress

- Reverted the accidental demo/FastAPI direction from `main`.
- Found the Paperclip-derived web app spec at `/Users/chekos/Documents/Codex/2026-05-08/i-have-a-paperclip-company-running/inkwell-web-app-spec.md`.
- Chose a monorepo layout that keeps the existing Python package stable while adding `apps/web`, `workers/inkwell`, and `supabase/migrations`.
- Decided that Vercel owns the web app, Supabase owns auth/data/RLS, and Modal owns trusted Python processing jobs.
- Scaffolded the Next.js App Router app in `apps/web` with login, app shell, import creation, job status, library, note rendering, local search, and copy-markdown UI.
- Added the Supabase core migration for profiles, sources, import jobs, notes, indexes, triggers, grants, and owner-scoped RLS policies.
- Added the Modal worker endpoint and long-running job function. The worker now invokes the existing Python pipeline, collects generated markdown into one saved note, and updates Supabase job state.

## Observations

The main risk is not whether a web UI is possible. It is boundary drift: putting frontend code inside `src/inkwell`, rewriting the pipeline in TypeScript, or turning the worker into a public try-it demo. The implementation needs durable job records and a narrow worker contract from the start.

## Next

- Apply the Supabase migration to a real project and verify RLS with two users.
- Deploy the Modal worker with real secrets and copy the endpoint into Vercel.
- Create a Vercel project pointed at `apps/web` and run an end-to-end smoke import.
- Add retry/delete/rename actions after the first deployed vertical slice proves the job loop.

## Links

- Related ADR: `../adr/037-web-app-stack-and-repo-boundary.md`
- Plan: `../../plans/2026-05-08-001-inkwell-web-app-plan.md`
