# ADR-034: Plain Text Transcription Output

**Date**: 2025-12-22
**Status**: Accepted
**Context**: Gemini Transcription Reliability
**Supersedes**: [ADR-032: Gemini Structured Transcription Output](032-gemini-structured-transcription-output.md)

---

## Context

ADR-032 introduced JSON structured output for Gemini transcription to enforce consistent formatting. However, this caused failures with long podcast episodes:

- JSON responses hit token limits and get truncated mid-string
- Truncated JSON causes parse failures: "Unterminated string starting at: line 1837 column 15 (char 249512)"
- ~250KB response size triggered the issue on a real episode

This mirrors the problems ADR-033 documented for extraction, where JSON mode had only a 1/4 success rate.

---

## Decision

**Remove JSON mode from Gemini transcription.** Use plain text output with a structured prompt instead:

1. Removed `response_mime_type="application/json"` and `response_schema` from API call
2. Updated prompt to request specific plain text format: `[MM:SS] Speaker: text`
3. Parse timestamps using regex with graceful fallback to single segment

The prompt asks for:
- `SUMMARY:` prefix line for summary extraction
- `[MM:SS] Speaker Name: text` format for each segment
- `[HH:MM:SS]` format for podcasts over 1 hour

---

## Implementation

```python
# Before: JSON mode (fails on long content)
response = self.client.models.generate_content(
    model=self.model_name,
    contents=[audio_file, prompt],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=response_schema,
    ),
)

# After: Plain text (robust)
response = self.client.models.generate_content(
    model=self.model_name,
    contents=[audio_file, prompt],
)
```

Parsing uses regex to extract timestamps and speakers:
```python
timestamp_pattern = r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:]+):\s*"
```

Falls back to single segment if no timestamps found.

---

## Consequences

### Positive

1. **No truncation failures** - Plain text handles any length
2. **Consistent with extraction** - Both pipelines now use plain text
3. **Graceful degradation** - Falls back to single segment if format varies
4. **Simpler API call** - No schema configuration needed

### Negative

1. **Less strict formatting** - LLM may vary timestamp format slightly
2. **Regex parsing** - Less robust than JSON schema validation

### Acceptable Trade-offs

The transcript content is ultimately saved as text. Format variations in timestamps are minor compared to complete failure from JSON truncation.

---

## References

- [ADR-032: Gemini Structured Transcription Output](032-gemini-structured-transcription-output.md) (superseded)
- [ADR-033: Markdown-Only Extraction](033-markdown-only-extraction.md) (same pattern)
