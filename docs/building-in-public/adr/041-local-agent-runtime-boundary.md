---
title: ADR 041 - Local agent runtime boundary
adr:
  author: Codex
  created: 20-Jul-2026
  status: accepted
---

# ADR 041: Local agent runtime boundary

**Date:** 2026-07-20
**Status:** Accepted

## Context

Local Inkwell users may already have a supported, authenticated agent runtime
but still need separate API keys for extraction. Reusing authentication by
reading tokens or treating a subscription credential as an API key would cross
a credential and billing boundary. Invoking a general coding agent without
strict controls would also expose repositories, tools, and inherited secrets.

## Decision

Add a provider-neutral local runtime contract below extraction and ship Codex
CLI as the first explicit-only backend. Codex owns installation, login, auth
storage, and updates. Inkwell only calls documented noninteractive commands,
passes prompts through stdin, validates JSONL plus final-schema output, and
records exact runtime/model provenance.

Use a private empty workspace, minimal environment, read-only sandbox, ignored
user config/rules, and a version-gated no-tool profile. Fail closed if required
controls are absent. Treat runtime output as untrusted. Bound input, output,
time, line length, termination grace, and process-group cleanup.

Direct Claude/Gemini APIs remain automatic defaults and the only hosted path.
Codex requires `--extractor codex` or `INKWELL_EXTRACTOR=codex`. There is no
automatic or cross-billing fallback. Claude Code subscription execution and
interview backend work are outside this decision.

## Consequences

- Users can choose a supported local subscription runtime without giving
  Inkwell its credentials.
- Subscription calls may have known token usage but unknown per-call USD cost;
  results and aggregates must say `runtime_managed`, never imply `$0.00`.
- Cache identity expands to runtime version/protocol, requested/effective model,
  and non-secret auth/billing class.
- A same-user read-only subprocess is not complete host read isolation. The
  limitation is documented and cannot be repaired by prompt instructions.
- CI uses deterministic fake executables and never a personal login.

## Alternatives Considered

1. Read or copy Codex authentication.
   - Rejected: credentials remain exclusively owned by Codex.
2. Automatically prefer a detected local runtime.
   - Rejected: it silently changes billing, auth, and failure semantics.
3. Run Codex in the hosted worker.
   - Rejected: hosted workers cannot access the user's local installation/login.
4. Add Claude Code subscription execution simultaneously.
   - Rejected: the policy boundary remains unresolved and is tracked separately.

The policy boundary was subsequently cleared and accepted under the narrower
conditions in ADR 042. This historical decision remains the origin of the
provider-neutral runtime contract.

## References

- Research and decision epic: #119
- Secure runtime contract: #120
- Codex extraction integration: #121
- Release verification: #122
- Claude Code policy boundary: #124
