# fix: Transcript Truncation on Long Videos (2+ hours)

**Issue:** #29

## Problem

Gemini transcription uses default output token limit (~8K), truncating transcripts for long videos (2+ hours).

## Solution

1. Add `max_output_tokens=65536` to Gemini API call
2. Check `finish_reason` and warn if truncation still occurs

## File to Change

`src/inkwell/transcription/gemini.py` - the `_transcribe_sync` method

## Implementation

```python
# Add config with max_output_tokens
response = self._client.models.generate_content(
    model=self._model,
    contents=[audio_file, prompt],
    config=types.GenerateContentConfig(
        response_mime_type="text/plain",
        max_output_tokens=65536,
    ),
)

# After getting response, check for truncation
if response.candidates and response.candidates[0].finish_reason.name == "MAX_TOKENS":
    logger.warning("Transcript may be incomplete - output hit token limit")
```

## Done When

- [ ] Issue #29 test video (1h50m) produces complete transcript
- [ ] No truncation warning appears for test video
- [ ] Existing tests pass

## Test

```bash
inkwell fetch "https://youtu.be/TqC1qOfiVcQ" --templates step-by-step-plan
# Verify _transcript.md is complete
```

## References

- Issue: #29
- File: `src/inkwell/transcription/gemini.py`
- Previous fix: ADR-034 (JSON truncation)
