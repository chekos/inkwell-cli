---
title: ADR 037 - Web app stack and repository boundary
adr:
  author: Codex
  created: 08-May-2026
  status: accepted
---

# ADR 037: Web app stack and repository boundary

**Date:** 2026-05-08
**Status:** Accepted

## Context

Inkwell is currently a Python CLI and reusable processing pipeline. A previous branch added a demo-shaped FastAPI/static page directly under `src/inkwell/demo`, but the intended product direction is different: a private, account-based web app where users paste media/feed URLs, run the existing pipeline, and save generated notes to a personal library.

The web app needs frontend hosting, authentication, durable job state, private note storage, and a Python-native execution environment for `yt-dlp`, `ffmpeg`, transcription, and LLM extraction. It should not rewrite the pipeline in TypeScript or introduce GCP/Cloud Run/Firestore infrastructure.

## Decision

Build the MVP in this repository as a small monorepo:

- `src/inkwell/` remains the Python package and CLI source of truth.
- `apps/web/` contains the Next.js App Router web app deployed by Vercel using the Vercel project root-directory setting.
- `supabase/migrations/` contains Postgres schema, indexes, and row-level security policies.
- `workers/inkwell/` contains the Modal worker adapter and a narrow interface to the existing Python pipeline.

Use:

- Vercel for the Next.js web app and route handlers.
- Supabase Auth and Supabase Postgres for accounts, job state, source records, and saved notes.
- Modal for the trusted Python worker because it is Python-native, supports custom images and apt packages such as `ffmpeg`, supports secrets, and scales worker functions down when idle.

The web app calls one worker contract: start a job with `jobId`, `userId`, and `url`; the worker updates job status/stage and writes the final note.

## Consequences

- The web product can ship without a separate repository or package publishing loop.
- Pipeline changes and web worker integration stay close enough to avoid drift.
- Vercel can deploy only `apps/web` from GitHub, while Python CI remains focused on the package.
- Modal becomes a new operational dependency, but it keeps Python processing out of Vercel request lifetimes.
- Supabase RLS becomes part of the correctness surface; migrations and server-side access patterns need careful review.

## Alternatives Considered

1. Separate `inkwell-web` repository.
   - Pros: clean deployment boundary, independent issue cadence.
   - Cons: immediate package/release friction for the Python pipeline, higher chance of contract drift, more setup before MVP learning.
2. Put FastAPI/static pages inside `src/inkwell`.
   - Pros: quick to run Python-only demo.
   - Cons: wrong product boundary, poor Vercel fit, mixes package assets with product UI, repeats the reverted demo direction.
3. Run the Python pipeline directly inside Vercel Functions.
   - Pros: fewer vendors.
   - Cons: request-duration limits, awkward system dependencies, poor fit for long media jobs.
4. Use Fly Machines or Fly Sprites for the worker.
   - Pros: Docker/control flexibility; Sprites provide strong sandbox isolation and snapshots.
   - Cons: more infrastructure ceremony for the MVP; Sprites are better for per-run untrusted sandboxing than a boring trusted pipeline worker.

## References

- Vercel monorepos: https://vercel.com/docs/monorepos
- Modal scaling: https://modal.com/docs/guide/scale
- Modal web endpoints: https://modal.com/docs/guide/webhooks
- Supabase RLS: https://supabase.com/docs/learn/auth-deep-dive/auth-row-level-security
- Paperclip spec snapshot: `/Users/chekos/Documents/Codex/2026-05-08/i-have-a-paperclip-company-running/inkwell-web-app-spec.md`
