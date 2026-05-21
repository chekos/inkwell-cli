# Transcription Attempt Policy

**Date:** 2026-05-21
**Author:** Codex

## Focus

Implement Phase 7 of the summarize-inspired CLI evolution: replace ad hoc transcription fallback ordering with a small policy object that can produce ordered attempts and remain ready for future providers.

## Plan

- Add a transcription attempt policy model with explicit attempt kinds and provider names.
- Wire `TranscriptionManager` to consult the policy for cache, YouTube transcript, Gemini YouTube URL, Gemini audio, and local media attempts.
- Preserve the current provider set and user-visible fallback behavior.
- Keep token-aware routing, new providers, and plugin capability expansion out of scope.
- Add focused unit tests for policy ordering and manager integration.

## Notes

This phase is about making fallback order intentional and observable, not adding more transcription backends.

## Progress

- Started implementation on `codex/transcription-attempt-policy`.
- Added `TranscriptionAttemptPolicy` with explicit attempt kinds for cache, YouTube transcript, Gemini YouTube URL, Gemini audio, and Gemini local media.
- Wired `TranscriptionManager` to consult the policy while preserving current fallback behavior and provider names in attempt records.
- Added focused policy-ordering tests and a manager integration test for injected policy behavior.
- Tightened the manager loop so omitted attempts are not run implicitly after earlier failures.
- Verified focused tests, formatting, linting, mypy, and the full test suite locally.

## Links

- Related devlog: `./2026-05-21-local-file-stdin-ingestion.md`
- Related roadmap: `../../../2026-roadmap/03-universal-content-ingestion.md`
- PR: #94
- Issue: TBD
