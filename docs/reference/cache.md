# Cache Behavior

Inkwell uses three local caches with different purposes. They all live under the XDG cache directory, usually `~/.cache/inkwell/`, but they are managed differently.

---

## Cache Layers

| Cache | Directory | Purpose | Key inputs | Expiration/control |
|-------|-----------|---------|------------|--------------------|
| Transcript cache | `~/.cache/inkwell/transcripts/` | Avoid re-transcribing the same episode URL | Episode URL hash | Transcript TTL, currently 30 days |
| Extraction cache | `~/.cache/inkwell/extractions/` | Avoid re-running LLM templates for identical inputs | Transcript hash, template name/version, provider, model, prompt hash, output schema version, cache format version | Extraction TTL, currently 30 days |
| Media/audio cache | `~/.cache/inkwell/audio/` | Avoid re-downloading media files during transcription fallback | Episode/media URL hash | `cache.media.enabled`, `cache.media.max_mb`, `cache.media.ttl_days` |

---

## Inspecting Caches

```bash
inkwell cache stats
```

`stats` is observational only. It reports transcript, extraction, and media/audio cache sections, including cache directories, sizes, format versions, and basic grouping metadata.

---

## Clearing Caches

```bash
inkwell cache clear
inkwell cache clear-expired
```

Important: these commands currently operate on the transcript cache.

| Command | Current behavior |
|---------|------------------|
| `inkwell cache clear` | Clears cached transcripts |
| `inkwell cache clear-expired` | Removes expired cached transcripts |
| `inkwell cache stats` | Reports transcript, extraction, and media/audio cache stats |

Extraction cache and media/audio cache clearing are intentionally not folded into `clear` yet, because deleting those artifacts has different cost and disk-space tradeoffs. Media/audio retention is bounded by configuration.

---

## Media Cache Controls

Media/audio files are controlled by:

```yaml
cache:
  media:
    enabled: true
    max_mb: 2048
    ttl_days: 30
```

Set values with:

```bash
inkwell config set cache.media.enabled false
inkwell config set cache.media.max_mb 4096
inkwell config set cache.media.ttl_days 14
```

The media cache policy is applied when media downloads run. Expired files are removed first, then oldest files are evicted until the cache is below `max_mb`.

---

## Cache Format Versions

Cache format versions make cache migrations explicit:

| Constant | Meaning |
|----------|---------|
| `TRANSCRIPT_CACHE_FORMAT_VERSION` | Stored transcript cache payload format |
| `EXTRACTION_CACHE_FORMAT_VERSION` | Stored extraction cache payload and key format |
| `AUDIO_CACHE_FORMAT_VERSION` | Media/audio cache reporting format |

Older extraction cache entries are treated as misses when the new key metadata is unavailable. This preserves existing files without corrupting them and avoids returning stale content for a changed prompt, provider, model, or output schema.

---

## Cost Implications

- Transcript cache hits avoid transcription costs.
- Extraction cache hits avoid LLM extraction costs for individual templates.
- Media/audio cache hits avoid repeated downloads, but not transcription itself.
- `--force` on `inkwell transcribe` bypasses transcript cache.
- `--skip-cache` on `inkwell fetch` bypasses extraction cache.
