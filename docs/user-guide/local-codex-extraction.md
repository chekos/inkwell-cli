# Local Codex Extraction

Inkwell can delegate extraction to a Codex CLI installation that you already
use locally. This is an explicit local runtime backend, not an Inkwell login and
not an API-key bridge.

Direct Gemini and Claude APIs remain the defaults. Codex never enters automatic
routing, never silently falls back to or from a metered API, and is not
available to the hosted Vercel/Modal import path.

## Requirements

1. Install Codex CLI separately using its supported installation instructions.
2. Sign in through Codex's own supported `codex login` flow.
3. Choose a currently supported model explicitly. Use Codex's `/model` picker
   or the current [Codex models documentation](https://learn.chatgpt.com/docs/models)
   to obtain the exact model slug for your installed runtime and account:

```bash
inkwell plugins configure codex model MODEL_ID
inkwell plugins validate codex --json
```

Inkwell deliberately has no compiled Codex model default. The requested model
is passed explicitly and recorded with the effective model in every result and
cache entry.

Optional bounded runtime settings:

```bash
inkwell plugins configure codex timeout_seconds 180
inkwell plugins configure codex max_input_bytes 8000000
inkwell plugins configure codex max_stdout_bytes 8388608
inkwell plugins configure codex max_stderr_bytes 1048576
```

`plugins validate` checks executable discovery, version compatibility,
noninteractive security controls, and `codex login status`. It does not perform
inference, open authentication files or databases, launch a login flow, or print
credentials.

## Run An Extraction

Select Codex explicitly for one fetch:

```bash
inkwell fetch ./source.txt \
  --extractor codex \
  --force-extraction \
  --json
```

Or select it for the current process environment:

```bash
INKWELL_EXTRACTOR=codex inkwell fetch ./source.txt --json
```

Short summaries may use Inkwell's normal deterministic pass-through behavior.
Use `--force-extraction` when you specifically want the configured runtime to
process a small local fixture.

## Credential And Isolation Boundary

Inkwell:

- does not read, copy, export, refresh, or persist Codex authentication;
- does not accept a Codex token as an OpenAI API key;
- does not bundle, install, update, or automate login for Codex;
- passes the prompt over stdin, never argv;
- starts Codex without a shell or PTY in a private empty temporary directory;
- ignores user configuration and rules, disables the tested agent-tool feature
  gates, requests a read-only sandbox, and fails closed if those controls drift;
- removes provider, cloud, GitHub, Supabase, Vercel, Modal, Inkwell worker, and
  other secret-shaped environment variables from the child.

The read-only sandbox and disabled tools prevent delegated mutations through
the tested Codex profile. They are not a complete host read-isolation boundary:
the same-user Codex process may still be able to read host paths allowed by the
operating system. Use this backend only for content you are willing to provide
to your locally authenticated Codex runtime.

## Cost, Cache, And Provenance

Codex may report token usage, but ChatGPT subscription execution does not
provide a trustworthy per-call USD amount. Inkwell reports:

```json
{
  "cost_usd": 0.0,
  "cost_known": false,
  "billing": {
    "mode": "runtime_managed",
    "amount_usd": null
  }
}
```

The compatibility `cost_usd` field remains numeric, but `cost_known: false`
means it must not be interpreted as free work. Human output says
`unknown (runtime-managed)`, and aggregate JSON reports unknown operations.

Cache keys include the exact Codex CLI version, runtime protocol, requested and
effective model, non-secret authentication/billing class, transcript,
template/version, prompt, and output schema. Cache hits retain their originating
`provider`, model, and runtime provenance.

## Recovery

| Diagnostic | Recovery |
| --- | --- |
| Executable missing | Install Codex CLI, then run `codex login` |
| Logged out | Run `codex login`, then validate again |
| Unsupported version or controls | Update Codex CLI and rerun validation |
| Model missing | Configure `codex.model` explicitly |
| Runtime state unwritable | Repair the local Codex installation/state permissions outside Inkwell |
| Timeout or output limit | Increase the bounded plugin setting only if the source requires it |

Inkwell never repairs or copies Codex runtime state.
