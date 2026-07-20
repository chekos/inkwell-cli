---
title: ADR 042 - Local Claude subscription boundary
adr:
  author: Codex
  created: 20-Jul-2026
  status: accepted
  extends: [041-local-agent-runtime-boundary]
---

# ADR 042: Local Claude subscription boundary

**Date:** 2026-07-20
**Status:** Accepted

## Context

ADR 041 deferred a Claude Code backend while Anthropic's rules for same-user
third-party subscription use were ambiguous. Anthropic now explicitly documents
Claude Agent SDK, `claude -p`, and third-party app use as drawing from current
subscription limits. Its June 15 update paused the proposed separate Agent SDK
credit. The legal boundary still forbids offering Claude login or routing plan
credentials on a user's behalf.

## Decision

Add an explicit local extraction plugin named `claude-code`, distinct from the
direct Anthropic API provider `claude`. It invokes the user's separately
installed Claude CLI as a same-user subprocess and inherits only the CLI's saved
first-party subscription login.

Reuse ADR 041's provider-neutral runner, schemas, typed errors, cancellation,
provenance, cache, and cost-state contract. Probe only version and sanitized auth
status. Scrub API keys, setup tokens, cloud-provider selectors/credentials, and
provider secrets. Disable tools, MCP, customization, and session persistence;
require schema JSON and explicit model selection; reject multiple effective
models. Do not use `--bare`, offer login, inspect credentials, bundle Claude, or
enable this backend in hosted workers.

## Consequences

- Local users may explicitly use current Claude subscription limits for
  extraction without giving Inkwell a credential.
- Direct Anthropic API extraction is unchanged and remains the only Claude path
  for hosted imports.
- Monetary cost is `runtime_managed` and unknown even when token or
  API-equivalent cost metadata exists; Inkwell does not claim the call is free.
- The feature depends on a version-gated external CLI contract and fails closed
  when that contract or authentication class drifts.
- The same-user subprocess is not a separate OS security boundary.

## Alternatives Considered

1. Use `--bare` with an API key.
   - Rejected: it bypasses saved subscription OAuth and duplicates the direct
     Anthropic provider.
2. Accept setup-token or cloud-provider authentication.
   - Rejected: it changes the approved auth/billing boundary.
3. Automatically choose Local Claude.
   - Rejected: it would silently cross provider and billing domains.
4. Run Local Claude in Modal/Vercel.
   - Rejected: hosted execution is outside the same-user local permission.

## References

- Local runtime boundary: ADR 041
- Policy and implementation spec: #124
- Parent research: #119
- Anthropic Help Center: `https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan`
