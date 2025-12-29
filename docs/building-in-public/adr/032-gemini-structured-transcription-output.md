# ADR-032: Gemini Structured Transcription Output

**Date**: 2025-12-22
**Status**: Accepted
**Context**: Transcription Layer Improvement
**Extends**: [ADR-009](009-transcription-strategy.md)

---

## Context

When using Gemini for transcription, the original implementation requested plain text output with a prompt asking for timestamps. This led to inconsistent, hard-to-parse responses where:

1. Timestamps were formatted inconsistently (sometimes HH:MM:SS, sometimes MM:SS)
2. Speaker labels varied in format
3. The response was a large block of text that was difficult to segment
4. No structured summary was provided

Users reported transcripts appearing "short" (76 lines but 9476 words) because Gemini returned huge paragraphs rather than properly segmented speech.

---

## Decision

Use Gemini's **structured output** feature with a JSON schema to enforce consistent formatting:

```python
response_schema = types.Schema(
    type="object",
    properties={
        "summary": types.Schema(
            type="string",
            description="Brief summary of the entire audio content",
        ),
        "segments": types.Schema(
            type="array",
            items=types.Schema(
                type="object",
                properties={
                    "timestamp": types.Schema(type="string", description="Timestamp in MM:SS format"),
                    "speaker": types.Schema(type="string", description="Speaker identifier or name"),
                    "text": types.Schema(type="string", description="Verbatim transcription of speech"),
                },
                required=["timestamp", "speaker", "text"],
            ),
        ),
    },
    required=["summary", "segments"],
)
```

The response is requested via:
```python
config=types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=response_schema,
)
```

---

## Consequences

### Positive

1. **Consistent formatting**: Every response follows the same structure
2. **Parseable output**: JSON can be reliably parsed without regex heuristics
3. **Summary included**: Users get a brief overview at the top of transcripts
4. **Better UX**: `_transcript.md` now shows summary followed by full transcript
5. **Speaker separation**: Each segment has clear speaker attribution

### Negative

1. **LLM-generated timestamps**: Timestamps are estimates, not actual audio timecodes
2. **Potential token overhead**: JSON structure adds some token usage
3. **Model dependency**: Requires Gemini models that support structured output

### Timestamp Caveat

The timestamps in the structured output are **LLM-generated estimates**, not precise audio timecodes. Gemini doesn't have access to actual audio timing information when generating the transcript. Users should treat these as approximate markers rather than precise references.

---

## Alternatives Considered

### 1. Continue with plain text + regex parsing
- **Pro**: Simpler prompt
- **Con**: Inconsistent results, parsing failures
- **Verdict**: Rejected - too unreliable

### 2. Use external speech-to-text service with real timestamps
- **Pro**: Accurate timestamps from audio analysis
- **Con**: Additional cost, complexity, vendor dependency
- **Verdict**: Deferred - consider for future enhancement

---

## Implementation

Files modified:
- `src/inkwell/transcription/gemini.py` - Added structured output schema
- `src/inkwell/transcription/models.py` - Added `summary` field to Transcript
- `src/inkwell/output/manager.py` - Accept `transcript_summary` parameter
- `src/inkwell/pipeline/orchestrator.py` - Pass summary through pipeline

---

## References

- [Google AI Structured Output Docs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini Audio Transcription](https://ai.google.dev/gemini-api/docs/audio#speech-to-text)
