# Local Codex extraction backend

**Date:** 2026-07-20
**Author:** Codex

## Focus

Implement the accepted local Codex extraction path without turning Inkwell into
an authentication broker or weakening the existing provider defaults.

## Progress

The implementation added a typed agent-runtime package, a bounded argv-only
subprocess runner, Codex readiness/capability probing, and a built-in extraction
plugin. The plugin is configured through the existing plugin system and
selected only through `--extractor codex` or `INKWELL_EXTRACTOR=codex`.

Extraction results now carry immutable per-call provider/runtime/model/usage
metadata. Cache entries preserve that origin and include the exact runtime
compatibility identity. Cost output distinguishes direct metered work from an
unknown runtime-managed subscription amount.

Deterministic fake executables cover install/auth/version/capability matrices,
stdin/argv separation, environment scrubbing, private cwd, protocol/schema
validation, limits, timeout, cancellation, and cleanup. The release rail also
uses an opt-in authenticated local smoke; CI never needs a personal login.

## Observations

`--ephemeral` prevents session-file persistence but does not promise that Codex
will never write its own state. Inkwell therefore reports an unwritable-state
failure and never tries to repair or copy that state.

The Codex JSONL completion event reports usage but not a separate guaranteed
effective-model field. The v1 contract requires an explicit model and disables
fallback configuration, making that selected identity the only unambiguous
effective model. Unexpected future protocol ambiguity fails closed.

## Verification

Repository verification passed with 1,414 Python tests, 11 web tests, Ruff,
mypy, strict MkDocs, and a production Next.js build. Wheel inspection confirmed
the runtime and extractor modules plus the `codex` extraction entry point are
present, while no Codex executable or SDK dependency is bundled.

The authenticated smoke used installed Codex CLI 0.144.6 and the exact
`gpt-5.6-sol` slug reported by that CLI's bundled model catalog. A generic
`gpt-5.6` request was rejected by the runtime and was not silently substituted.
The successful backend smoke recorded matching requested/effective provenance,
a completed JSONL lifecycle, and runtime-managed billing.

The full `inkwell fetch` smoke processed a local prompt-injection fixture through
all three default extraction templates with zero failures and three explicit
unknown-cost operations. Git status and the binary diff hash were identical
before and after both the failed and successful hostile-source runs.

## Links

- ADR: `../adr/041-local-agent-runtime-boundary.md`
- Epic: #119
- Runtime contract: #120
- Extraction integration: #121
- Release proof: #122
