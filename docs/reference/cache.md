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
inkwell cache clear --transcripts
inkwell cache clear --extractions
inkwell cache clear --media
inkwell cache clear --all
inkwell cache clear-expired
inkwell cache clear-expired --extractions
```

For backward compatibility, `inkwell cache clear` and `inkwell cache clear-expired` still default to transcript cache entries when no target flag is provided.

| Command | Behavior |
|---------|----------|
| `inkwell cache clear` | Clears cached transcripts |
| `inkwell cache clear --transcripts` | Clears cached transcripts |
| `inkwell cache clear --extractions` | Clears extraction cache entries |
| `inkwell cache clear --media` | Clears downloaded media/audio cache files |
| `inkwell cache clear --all` | Clears transcript, extraction, and media/audio caches |
| `inkwell cache clear-expired` | Removes expired cached transcripts |
| `inkwell cache clear-expired --extractions` | Removes expired extraction cache entries |
| `inkwell cache stats` | Reports transcript, extraction, and media/audio cache stats |

`clear` confirms by default. Use `--force` for non-interactive cleanup.

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

You can also enforce the media policy directly without downloading new media:

```bash
inkwell cache enforce-media-policy
inkwell cache enforce-media-policy --force
```

Use this when reclaiming disk space or after changing `cache.media.max_mb` or `cache.media.ttl_days`.

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
