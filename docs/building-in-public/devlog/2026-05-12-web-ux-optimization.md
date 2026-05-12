# Web UX Optimization

**Date:** 2026-05-12
**Author:** Codex

## Focus

Optimize the Inkwell web app UX around the full import-to-note journey: dashboard command center, new import flow, job status confidence, library search, and note reading/export.

## Progress

- Started from `main` on `codex/inkwell-web-ux-optimization`.
- Reviewed the current Next.js app routes and the existing web MVP plan.
- Used Mobbin references for adjacent production patterns: Fireflies import/transcript detail, Manus library, ElevenLabs empty states, and GitBook navigation discipline.
- Generated a high-fidelity concept board for the target product direction at `/Users/chekos/.codex/generated_images/019e1d63-eb36-7b90-9337-6ab589506a55/ig_043e6496bb1e7ef6016a03726cd7748191b6c588e2e7b1643e.png`.

## Observations

The current app already has the correct MVP route shape. The highest-leverage UX work is making the async worker path feel trustworthy and giving the saved note page a stronger payoff, not adding a marketing-style surface.

## Next

- Build shared UI primitives for panels, page headers, import command, job timeline, and note actions.
- Add focused Vitest coverage for the new reusable UX surfaces.
- Run web lint/build/tests plus rendered browser QA before opening a PR.

## Links

- Related plan: `../../plans/2026-05-08-001-inkwell-web-app-plan.md`
- PR: TBD
