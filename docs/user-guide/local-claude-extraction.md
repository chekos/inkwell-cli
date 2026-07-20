# Local Claude Extraction

Inkwell can use your local Claude CLI for extraction. This is an explicit,
local-only subprocess backend named `claude-code`; it is separate from the
existing `claude` provider, which calls the Anthropic API with an API key.

Inkwell does not sign you in to Claude, install or bundle Claude Code, read or
copy credentials, create setup tokens, or proxy requests. The Claude CLI must
already be installed and authenticated independently. Local Claude extraction
is never available to Modal, Vercel, or another hosted worker.

## Configure And Validate

Choose a model explicitly. Inkwell has no compiled Claude model default:

```bash
inkwell plugins configure claude-code model sonnet
inkwell plugins validate claude-code --json
```

The requested value may be a current Claude CLI alias or full model identifier.
The result and cache provenance record both that requested value and the single
effective model reported by Claude Code. Multiple reported models fail closed;
Inkwell does not enable `--fallback-model`.

Optional bounded settings mirror Local Codex extraction:

```bash
inkwell plugins configure claude-code timeout_seconds 180
inkwell plugins configure claude-code max_input_bytes 8000000
inkwell plugins configure claude-code max_stdout_bytes 8388608
inkwell plugins configure claude-code max_stderr_bytes 1048576
```

Validation calls only `claude --version` and `claude auth status --json`. It
records installed/authenticated/supported state and the sanitized auth class;
it discards account, organization, subscription-tier, and credential fields.
Validation does not perform inference or start an authentication flow.

## Use Your Local Claude CLI

Select the backend explicitly for a local fetch:

```bash
inkwell fetch ./source.txt \
  --extractor claude-code \
  --force-extraction \
  --json
```

Or explicitly select it for the current process:

```bash
INKWELL_EXTRACTOR=claude-code inkwell fetch ./source.txt --json
```

`claude-code` is excluded from templates, default-provider heuristics, automatic
routing, and cross-provider retry. Direct Claude/Gemini providers remain the
automatic defaults and the only hosted choices.

## Authentication And Isolation Boundary

The child process receives `HOME` only so the Claude CLI can use its own saved
first-party subscription login. Inkwell removes `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, Claude cloud-provider
selectors, cloud credentials, and other provider secrets from the child. It
accepts readiness only when Claude reports saved `claude.ai` authentication
against the first-party provider. API keys, setup tokens, Bedrock, Vertex, and
Foundry authentication fail closed.

Inkwell does not use `--bare`, because that mode skips saved OAuth/keychain
authentication. Instead it runs documented `claude -p` through stdin with:

- `--safe-mode` and no user/project/local setting sources;
- an empty built-in tool list and denied MCP tools;
- a strict empty MCP configuration;
- permission mode `dontAsk`;
- disabled skills and slash commands;
- no session persistence;
- explicit model selection and schema-constrained JSON output;
- bounded stdin/stdout/stderr, timeout, process-tree cancellation, and a private
  mode-0700 temporary working directory.

The prompt never appears in argv. Runtime errors are sanitized and do not carry
the prompt, provider response body, environment values, account identifiers, or
session identifiers.

This boundary prevents Claude tool use and customization in the tested profile.
It is still a same-user local process using the host's Claude installation, not
a separate OS-level sandbox. Use it only for content you are willing to send to
your local Claude CLI.

## Subscription Limits, Cost, And Cache

Current Anthropic guidance says Claude Agent SDK, `claude -p`, and third-party
app usage draw from the user's subscription usage limits. The proposed June 15
separate monthly Agent SDK credit was paused and is not available.

Because subscription execution has no attributable per-call charge, Inkwell
records token usage but reports an unknown monetary amount:

```json
{
  "cost_usd": 0.0,
  "cost_known": false,
  "billing": {"mode": "runtime_managed", "amount_usd": null}
}
```

The numeric zero is a compatibility field and does not mean the request was
free. Cache keys include the CLI version, runtime protocol, requested model,
sanitized auth/billing class, transcript, template, prompt, and schema. Cache
hits retain the originating effective model, usage, attempts, and provenance.

## Recovery

| Diagnostic | Recovery |
| --- | --- |
| Executable missing | Install Claude Code independently and retry validation |
| No saved subscription login | Authenticate Claude Code independently, then retry validation |
| API-key/setup-token/cloud auth | Remove that auth override from the local Claude CLI context and use its saved subscription login |
| Unsupported version | Update Claude Code and rerun validation |
| Model missing | Configure `claude-code.model` explicitly |
| Timeout or output limit | Increase the bounded plugin setting only if the source requires it |

Inkwell never repairs, copies, or creates Claude authentication state.

## Policy References

- [Use the Claude Agent SDK with your Claude plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)
- [Run Claude Code programmatically](https://code.claude.com/docs/en/headless)
- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)
- [Issue #124 policy recheck](https://github.com/chekos/inkwell-cli/issues/124#issuecomment-5027345316)
