# Research: steipete/summarize CLI Architecture

**Date:** 2026-05-20
**Updated:** 2026-07-07
**Author:** Codex
**Status:** Completed

## Purpose

Evaluate Peter Steinberger's open-source `summarize` CLI as a reference architecture for Inkwell's next CLI evolution. This informs the universal ingestion, multi-export, cache, and model-routing work already sketched in the 2026 roadmap.

This note is intentionally research, not an ADR. It records external patterns that shaped follow-up implementation, plus the current Inkwell status so the recommendations do not read as unstarted work.

## Scope

This review focused on:

- Public product/docs at <https://summarize.sh/>
- Open-source repository at <https://github.com/steipete/summarize>
- CLI pipeline shape, content extraction, media transcription, model routing, cache design, and output modes
- Fit with Inkwell's existing Python pipeline and product identity

This is not a code-porting recommendation. `summarize` is MIT-licensed, but the useful part for us is the architecture and product behavior, not copying TypeScript implementation.

## Key Findings

### 1. `summarize` Is Extraction-First

The headline pattern is "extract clean content first, summarize second." The CLI handles URLs, files, YouTube, podcasts, PDFs, audio/video, and stdin, then routes the extracted payload into an LLM only when needed.

Useful behaviors:

- `--extract` stops after cleaned extraction and performs no LLM call.
- `--format md|text` lets extraction become a composable Unix pipe.
- Website extraction uses Readability, optional `markitdown`, and Firecrawl fallback when local extraction is blocked or too thin.
- Media pages prefer transcript/captions before downloading and transcribing audio.

At the time of this research, Inkwell already had a strong transcript-first podcast pipeline, but it did not yet have a general source classification layer that could represent URLs, saved feeds, local files, or stdin uniformly. That gap led to the conservative `InputResolver` / `ContentSource` foundation now present in `src/inkwell/ingestion/`.

### 2. Input Classification Is a First-Class Stage

`summarize` resolves inputs into URL, local file, stdin, asset URL, website, direct media, YouTube, podcast platform, or generic media. The source kind changes downstream policy.

This maps cleanly to Inkwell's roadmap item to replace RSS-specific parsing with a `ContentSource` abstraction.

Recommended Inkwell equivalent:

```text
Raw input
  -> InputResolver
  -> ContentSource
  -> ExtractedSourcePayload
  -> Transcription / structured extraction / output
```

This keeps RSS feeds, direct URLs, local files, articles, and batch stdin from leaking special cases through `cli.py`.

### 3. Provider Policy Is Explicit and Centralized

`summarize` keeps provider entrypoints thin. The docs call this out directly for transcript providers: YouTube, podcast, and generic providers orchestrate only their domain, while shared helpers own capability checks, missing-provider messages, provider ordering, and result shaping.

At research time, Inkwell had a similar shape in `TranscriptionManager`, but policy was still mostly hardcoded as:

```text
cache -> YouTube transcript -> Gemini public YouTube URL -> download audio -> Gemini audio
```

The next improvement was not "add every provider." It was to create a transcription policy object so local Whisper, Groq, AssemblyAI, OpenAI, or future plugin providers can be added later without turning `TranscriptionManager` into a switchboard. The first version of that idea now exists as `TranscriptionAttemptPolicy`.

### 4. Cache Design Is More Deliberate

`summarize` uses a SQLite cache for extracted content, transcripts, summaries, chat, and slides, plus a separate bounded media file cache. Cache keys include format versions and only the meaningful inputs:

- transcript: URL + namespace + file mtime + format version
- extraction: URL + extraction settings + format version
- summary: content hash + prompt hash + model + length + language + format version
- media files: URL with TTL, size cap, and optional size/hash verification

At research time, Inkwell had file-based transcript and extraction caches, plus an audio cache keyed by URL. That served the early CLI well, but it lacked broader cache stats, bounded media retention, and some explicit cache-key inputs. The follow-up work added extraction key metadata, cache format versions, media cache controls, and cache stats for transcript, extraction, and media caches. Summary reuse when two URLs produce the same content remains a future concern because Inkwell is structured-extraction-first rather than single-summary-first.

The biggest optimization to steal was content-hash-based extraction/summary caching. The extraction side has now mostly landed in Inkwell. Extraction cache keys include:

- transcript/content hash
- template name and version
- provider/model
- extraction prompt or template prompt hash
- output schema/version

### 5. Model Selection Is Input-Aware

`summarize --model auto` selects attempts based on input kind, prompt token size, configured rules, available API keys, model context limits, and fallbacks. It can fall back from native providers to OpenRouter or local CLI tools.

Inkwell currently exposes provider choice (`claude`, `gemini`, plugin override), but not token-aware model routing. We should not clone the full matrix immediately. The first useful version is:

```yaml
models:
  transcription:
    default: gemini/gemini-3-flash-preview
  extraction:
    mode: auto
    rules:
      - when: ["short_transcript"]
        candidates: ["gemini/gemini-3-flash-preview"]
      - when: ["long_transcript"]
        candidates: ["claude/claude-sonnet-4-5", "gemini/gemini-3-flash-preview"]
```

Then make provider selection produce an ordered attempt list instead of one selected plugin.

### 6. Output Modes Are Operator-Friendly

`summarize` cleanly separates stdout and stderr:

- primary extracted text / summary / JSON goes to stdout
- progress, metrics, prompts, and warnings go to stderr
- `--json` disables streaming and emits a stable envelope
- `--plain` / `--no-color` support scripting
- detailed metrics include timing and cost estimates

Inkwell already routed some chatter to stderr and had good Rich progress, but `fetch` still mainly behaved as a file-writing command. A structured JSON envelope would make Inkwell more agent-native and easier to call from the web worker, scripts, and future MCP tools. That recommendation has since landed for `fetch` and `transcribe`.

### 7. Short-Content Bypass Is a Good Cost Guard

`summarize` returns extracted content as-is when it is shorter than the requested summary length, unless `--force-summary` is set. This avoids paying an LLM to compress content that is already within the desired shape.

For Inkwell, the analog is:

- Skip summary templates when transcript/content is below a configured threshold and write the cleaned content or transcript note directly.
- Keep other structured templates running only when they add real value.
- Expose `--force-extraction` for users who want LLM processing anyway.

### 8. Slides Are Worth Learning From, But Later

`summarize` has video slide extraction: scene-change keyframes, optional OCR, timeline rendering, and transcript-aligned descriptions. This overlaps directly with Inkwell's future "visual intelligence" roadmap.

The optimization to remember: slide descriptions do not need an LLM by default. They can be generated from nearby transcript segments and OCR text. That keeps the feature cheaper and more deterministic.

## Recommendations And Implementation Status

### Landed Follow-Up

| Recommendation | Status | Notes |
|----------------|--------|-------|
| Add a small `InputResolver` / `ContentSource` layer | Landed | `src/inkwell/ingestion/` classifies saved feeds, URLs, local files, stdin, direct media, YouTube, and unknown URLs. |
| Add `--json`, `--plain`, and stronger stdout/stderr discipline | Landed | `inkwell fetch` and `inkwell transcribe` now emit machine-readable output while progress and warnings stay on stderr. |
| Add extract-only mode | Landed narrowly | `inkwell fetch --extract` emits transcript text for media workflows. It is not a generic article/PDF extraction command. |
| Add bounded media cache controls | Landed | `cache.media.enabled`, `cache.media.max_mb`, and `cache.media.ttl_days` now govern downloaded media/audio retention. |
| Improve cache keys before expanding providers | Landed for extraction | Extraction cache keys now include transcript hash, template identity, provider/model, prompt hash, output schema identity, and cache format version. |
| Create a provider attempt policy | Landed for transcription | `TranscriptionAttemptPolicy` now centralizes cache, YouTube, Gemini URL, Gemini audio, and local-media attempt ordering. |
| Add local-file and stdin ingestion | Landed for supported source types | Local audio/video routes through transcription; `.txt`, `.md`, and stdin route directly to extraction templates. |

### Still Useful Next

1. Add token-aware extraction model selection.
   - Estimate transcript/source tokens.
   - Skip models that cannot fit the prompt.
   - Produce an ordered attempt list instead of a single selected extraction provider.

2. Add article/web extraction as a new source type.
   - Python candidates: Readability-style extraction (`readability-lxml` or `trafilatura`) plus optional hosted fallback.
   - Keep this source separate from podcast transcription.

3. Decide PDF/document extraction dependency.
   - Treat PDFs as a separate extraction-source decision, not as an incidental local-file feature.

4. Add video slides/OCR mode.
   - Start with opt-in `--slides`.
   - Reuse transcript timestamps before calling any model.

5. Expand provider capability metadata.
   - Future plugin providers should expose capabilities such as `can_transcribe_url`, `can_transcribe_file`, `supports_timestamps`, and `estimated_cost`.

### Later

1. Local browser or extension pairing.
   - Useful eventually, but less important than making the CLI and web worker share clean primitives.

2. Broad provider marketplace.
   - Powerful, but only worth it after the policy and cache foundations are stable.

## What Not To Copy

- Do not make Inkwell a generic summarizer first. Inkwell's differentiator is structured knowledge output plus reflection.
- Do not start with a browser extension. The web app and Modal worker are already the product surface.
- Do not add many transcription providers before provider policy is centralized.
- Do not introduce a TypeScript sidecar just to reuse implementation details.
- Do not over-index on single summary output. Use `summarize` patterns to strengthen Inkwell's template pipeline.

## Original Implementation Sequence

1. `InputResolver` and source-kind models
2. JSON envelope for `fetch` and `transcribe`
3. Cache key/version cleanup
4. Bounded media cache
5. Extract-only mode
6. Local file/stdin ingestion
7. Provider attempt policy
8. Web/article extraction
9. Token-aware model auto-selection
10. Slides/OCR

This order front-loaded architecture that reduced future special cases while keeping user-visible wins close. Items 1 through 7 have since landed in narrow Inkwell-specific forms. Items 8 through 10 remain the main follow-up work.

## References

- `summarize` site: <https://summarize.sh/>
- GitHub repository: <https://github.com/steipete/summarize>
- Command reference: <https://summarize.sh/docs/commands/summarize.html>
- Website extraction docs: <https://summarize.sh/docs/website.html>
- Media/podcast docs: <https://summarize.sh/docs/media.html>
- Transcript provider flow: <https://summarize.sh/docs/transcript-provider-flow.html>
- Cache design: <https://summarize.sh/docs/cache.html>
- Auto model selection: <https://summarize.sh/docs/model-auto.html>
- Config docs: <https://summarize.sh/docs/config.html>
- Inkwell universal ingestion roadmap: `2026-roadmap/03-universal-content-ingestion.md`
- Inkwell multi-export roadmap: `2026-roadmap/09-multi-export-system.md`
- Inkwell machine-readable output docs: [machine-readable-output.md](../../reference/machine-readable-output.md)
- Inkwell supported inputs docs: [supported-inputs.md](../../reference/supported-inputs.md)
- Follow-up devlog: [summarize-inspired-cli-foundation.md](../devlog/2026-05-21-summarize-inspired-cli-foundation.md)
- Follow-up devlog: [machine-readable-output.md](../devlog/2026-05-21-machine-readable-output.md)
- Follow-up devlog: [cache-key-observability.md](../devlog/2026-05-21-cache-key-observability.md)
- Follow-up devlog: [media-cache-controls.md](../devlog/2026-05-21-media-cache-controls.md)
- Follow-up devlog: [extract-only-mode.md](../devlog/2026-05-21-extract-only-mode.md)
- Follow-up devlog: [local-file-stdin-ingestion.md](../devlog/2026-05-21-local-file-stdin-ingestion.md)
- Follow-up devlog: [transcription-attempt-policy.md](../devlog/2026-05-21-transcription-attempt-policy.md)
