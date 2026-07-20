# Machine-Readable Output

`inkwell fetch` and `inkwell transcribe` support script-friendly output modes for automation. These modes preserve the default human-facing Rich output unless you opt in with `--json` or `--plain`.

---

## Stdout And Stderr Contract

In machine-readable modes:

| Stream | Contents |
|--------|----------|
| stdout | The primary result: JSON envelope, transcript text, output directory path, or transcript file path |
| stderr | Progress, warnings, hints, status messages, and errors |

This lets shell scripts parse stdout safely:

```bash
inkwell transcribe "$URL" --json > transcript.json 2> progress.log
inkwell fetch "$URL" --plain > output-dir.txt 2> progress.log
```

`--json` and `--plain` are mutually exclusive. `inkwell fetch --extract` is its own transcript-only mode and does not currently combine with `--json`.

---

## JSON Envelope Version

JSON responses include:

```json
{
  "schema_version": 1,
  "command": "fetch",
  "status": "success"
}
```

Treat `schema_version` as the compatibility guard for scripts. New optional fields may be added over time, but incompatible shape changes should use a new schema version.

`input.kind` identifies the routed source shape. Common values include `saved_feed`, `youtube`, `direct_media`, `article`, `pdf`, `local_file`, `stdin`, and `unknown_url`.

---

## `inkwell transcribe --json`

Use this when you want one transcript and structured metadata without note generation.

```bash
inkwell transcribe https://youtube.com/watch?v=abc --json
```

Example response:

```json
{
  "cache_hits": {
    "extractions": 0,
    "transcript": false
  },
  "command": "transcribe",
  "costs": {
    "total_usd": 0.0,
    "transcription_usd": 0.0
  },
  "error": null,
  "files": [],
  "input": {
    "kind": "youtube",
    "normalized": "https://youtube.com/watch?v=abc",
    "raw": "https://youtube.com/watch?v=abc"
  },
  "output": {
    "path": null
  },
  "output_directory": null,
  "schema_version": 1,
  "status": "success",
  "templates": [],
  "transcript": "Full transcript text...",
  "transcription": {
    "attempts": ["cache", "youtube"],
    "cost_usd": 0.0,
    "duration_seconds": 1.2,
    "from_cache": false,
    "language": "en",
    "media_duration_seconds": 3600.0,
    "source": "youtube",
    "word_count": 9500
  }
}
```

When `--output transcript.txt` is used, the `files` array and `output.path` include that file.

---

## `inkwell fetch --json`

Use this when you want the complete structured-note pipeline and a parseable summary of the run.

```bash
inkwell fetch syntax --latest --json
```

Example response:

```json
{
  "cache_hits": {
    "extractions": 2,
    "transcripts": 1
  },
  "command": "fetch",
  "errors": [],
  "files": [
    {
      "filename": "summary.md",
      "path": "/Users/me/inkwell-notes/syntax-episode/summary.md",
      "size_bytes": 2048,
      "template": "summary"
    }
  ],
  "input": {
    "kind": "saved_feed",
    "normalized": "syntax",
    "raw": "syntax",
    "selector": {
      "count": null,
      "episode": null,
      "latest": true
    }
  },
  "output_directory": "/Users/me/inkwell-notes",
  "results": [
    {
      "cache_hits": {
        "extractions": 2,
        "transcript": true
      },
      "costs": {
        "extraction_usd": 0.0032,
        "interview_usd": 0.0,
        "total_usd": 0.0032,
        "transcription_usd": 0.0
      },
      "episode": {
        "episode_title": "Modern CSS Features",
        "episode_url": "https://youtube.com/watch?v=abc",
        "podcast_name": "Syntax"
      },
      "extraction": {
        "cached": 2,
        "failed": 0,
        "successful": 3,
        "total": 3
      },
      "interview": {
        "completed": false,
        "cost_usd": 0.0
      },
      "output": {
        "directory": "/Users/me/inkwell-notes/syntax-episode",
        "files": []
      },
      "status": "success",
      "templates": [],
      "transcription": {
        "attempts": ["cache"],
        "cost_usd": 0.0,
        "duration_seconds": 0.1,
        "from_cache": true,
        "language": "en",
        "media_duration_seconds": 3600.0,
        "source": "cached",
        "word_count": 9500
      }
    }
  ],
  "schema_version": 1,
  "status": "success",
  "summary": {
    "failed": 0,
    "requested": 1,
    "succeeded": 1,
    "total_cost_usd": 0.0032
  },
  "templates": [],
  "warnings": []
}
```

For feed runs with `--count`, `results` contains one entry per processed episode.

Codex template entries add runtime and monetary provenance:

```json
{
  "provider": "codex",
  "model": "MODEL_ID",
  "from_cache": false,
  "cost_usd": 0.0,
  "cost_known": false,
  "billing": {
    "mode": "runtime_managed",
    "amount_usd": null
  },
  "runtime": {
    "kind": "codex-cli",
    "version": "0.144.6",
    "protocol_version": 1,
    "requested_model": "MODEL_ID",
    "effective_model": "MODEL_ID",
    "auth_class": "chatgpt",
    "billing_class": "runtime_managed",
    "usage": {
      "input_tokens": 0,
      "cached_input_tokens": 0,
      "output_tokens": 0,
      "reasoning_output_tokens": 0
    }
  }
}
```

The version and model above are illustrative values from one run. Scripts must
read the returned values. When `cost_known` is false, numeric `cost_usd` exists
only for schema-v1 compatibility and does not mean the operation was free.
`summary.total_cost_known` and `summary.unknown_cost_operations` prevent a
partial known sum from being mistaken for complete spend.

For generic article URLs, `input.kind` is `article` after local extraction
succeeds. Local PDFs use `pdf`, and local OCR images use `image`. These sources
skip media transcription; the transcription section reports text-style attempts
such as `article`, `pdf`, or `image`. Each fetch result may include a
`source_extraction` object with deterministic local provenance for images/PDFs.

---

## Plain Mode

Plain mode is intentionally terse.

```bash
# Transcript text only
inkwell transcribe "$URL" --plain

# Generated episode directory path(s)
inkwell fetch "$URL" --plain

# Transcript file path(s), when writing extract-only output
inkwell fetch syntax --latest --extract --output-dir ~/transcripts --plain
```

Plain mode is useful for command substitution and pipelines:

```bash
note_dir="$(inkwell fetch "$URL" --plain 2> progress.log)"
open "$note_dir"
```
