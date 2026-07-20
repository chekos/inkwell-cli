# Local Agent Runtime Reference

The `inkwell.agent_runtime` package provides a provider-neutral contract for
bounded local runtime delegation. Version 1 ships `codex-cli` and
`claude-code-cli` backends.

## Runtime Contract

`RuntimeRequest` contains the rendered prompt, JSON Schema, explicit requested
model, timeout and byte limits, task metadata, and an optional application
validator. `RuntimeResponse` contains the validated final value, lifecycle
event types, attempts, token usage, requested/effective model, runtime
kind/version/protocol, authentication and billing class, monetary state, and
duration.

Stable runtime errors include:

- `runtime_missing_executable`
- `runtime_unsupported_version`
- `runtime_unsupported_capability`
- `runtime_not_authenticated`
- `runtime_state_unwritable`
- `runtime_model_required`
- `runtime_model_mismatch`
- `runtime_input_too_large`
- `runtime_output_too_large`
- `runtime_timeout`
- `runtime_cancelled`
- `runtime_nonzero_exit`
- `runtime_malformed_protocol`
- `runtime_missing_terminal_state`
- `runtime_turn_failed`
- `runtime_schema_invalid`
- `runtime_application_invalid`
- `runtime_permission_denied`

Durable errors are sanitized and bounded. They do not include the prompt,
transcript, environment values, or provider response bodies.

## Codex Invocation Profile

The backend constructs argv directly and uses Codex's noninteractive `exec`
surface with JSONL events and a final JSON Schema. It uses:

- ephemeral execution;
- ignored user config and rules with strict config parsing;
- an empty mode-0700 temporary cwd;
- mode-0600 schema/result files;
- a read-only sandbox;
- approval policy `never`;
- explicit model selection;
- disabled stable `apps`, `browser_use`, `computer_use`, `goals`, `hooks`,
  `in_app_browser`, `multi_agent`, `plugins`, `shell_tool`, and `unified_exec`
  feature gates;
- disabled web search and no inherited shell environment;
- a minimal child environment retaining only executable discovery, locale,
  temporary directory, certificates, supported proxy values, and
  `HOME`/`CODEX_HOME` for Codex's own supported local authentication.

The prompt is written to stdin. It is never included in argv. On timeout or
cancellation, Inkwell sends TERM to the isolated process group, waits a bounded
grace period, sends KILL if needed, awaits the group leader and output drains,
and removes the temporary workspace.

Success requires exit code 0, a `turn.completed` JSONL event, a parseable final
document, JSON Schema validation, and application validation. `turn.failed`,
`error`, malformed/truncated output, oversized output, or missing terminal state
fails the request and is never cached.

## Readiness JSON

```bash
inkwell plugins validate codex --json
```

The stdout object uses schema version 1 and includes:

```json
{
  "schema_version": 1,
  "plugin": "codex",
  "runtime": "codex-cli",
  "ready": true,
  "installed": true,
  "authenticated": true,
  "supported": true,
  "executable": "/path/to/codex",
  "version": "0.144.6",
  "auth_class": "chatgpt",
  "configured_model": "MODEL_ID",
  "model_policy": "explicit_required",
  "reason": null,
  "recovery_command": null
}
```

Version values are examples of observed output, not compiled requirements.
Compatibility is checked against the runtime profile in the installed Inkwell
version.

## Claude Code Invocation Profile

The `claude-code` extraction plugin uses documented noninteractive `claude -p`
with stdin, a private mode-0700 temporary cwd, an explicit model, JSON Schema,
and single-result JSON. It enables safe mode, supplies an empty built-in tool
list, denies MCP tools, supplies a strict empty MCP configuration, selects
`dontAsk`, disables skills/slash commands, disables session persistence, and
loads no user/project/local setting sources.

The backend deliberately does not use `--bare`: that mode skips saved
OAuth/keychain authentication. Its minimal child environment retains `HOME` for
the CLI's saved login but removes Anthropic keys/tokens, setup tokens,
cloud-provider selectors/credentials, and other provider secrets. Readiness
accepts only `authMethod: claude.ai` with `apiProvider: firstParty`; no account
or organization fields survive parsing.

Success requires exit code 0, a `result` object with `subtype: success`,
`is_error != true`, one reported effective model, present structured output,
JSON Schema validation, and application validation. Multiple model-usage keys
are treated as ambiguous fallback and rejected. Usage, requested/effective
model, attempts, runtime version, duration, sanitized auth class, and
subscription-limit billing class are preserved.

```bash
inkwell plugins validate claude-code --json
```

Local Claude extraction remains explicit-only and local-only. The direct
Anthropic API plugin is still named `claude` and is unchanged.
