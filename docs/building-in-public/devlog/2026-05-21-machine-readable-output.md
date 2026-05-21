# Machine-Readable Output Modes

**Date:** 2026-05-21
**Author:** Codex

## Focus

Implement Phase 2 of the summarize-inspired CLI evolution: add script-friendly output modes for `fetch` and `transcribe` while preserving Inkwell's existing human-facing workflow.

## Progress

- Started from the merged `InputResolver` / `ContentSource` foundation.
- Scoped this pass to `--json` and `--plain` output modes only.
- Keeping default Rich output unchanged for interactive users.
- Routing progress, warnings, hints, and metadata to stderr in machine-output modes so stdout stays parseable.
- Added focused CLI tests for JSON/plain stdout payloads and stderr progress behavior.
- Verified the focused CLI suite and the full test suite locally.

## Observations

`PipelineOrchestrator` and `TranscriptionManager` already return enough structured data for a useful envelope. The risky part is CLI presentation: `fetch` currently prints progress and summary directly while processing each episode, so machine-readable modes need to collect results and emit the primary payload only once at the end.

## Next

Open the Phase 2 PR and watch CI. If it stays green, merge it before starting Phase 3 cache-key/version cleanup.

## Links

- Related devlog: `./2026-05-21-summarize-inspired-cli-foundation.md`
- Related roadmap: `../../../2026-roadmap/09-multi-export-system.md`
- PR: #89
- Issue: TBD
