# Transcript Truncation Bug: Chunk Prompt Fix

**Date:** 2026-01-06
**Objective:** Investigate and fix why long podcast transcripts were being truncated, missing content from the latter portions of episodes

---

## Summary
Long audio files (>15 minutes) were being truncated during transcription. A 25-minute podcast about "Gemini 3 vs. Claude Opus 4.5 vs. GPT-5.1 Codex" was missing the entire GPT-5.1 Codex section. The root cause was a vague chunk transcription prompt that caused Gemini to return ~450 chars instead of ~9000 chars per 10-minute chunk.

## The Journey

### What Didn't Work
- **Initial hypothesis: Chunking not triggering** - Checked `needs_chunking()` function, but it correctly returned `True` for 25-min audio
- **Checking audio chunks** - Created chunks manually and verified they had proper audio content (similar volume levels across all 3 chunks)
- **Testing cache issues** - Cleared transcript cache multiple times, but fresh transcriptions still truncated
- **Environment/config issues** - Verified API keys were configured correctly in the pipeline

### What Worked
- **Comparing chunk vs single-pass transcription** - Transcribed the same audio chunk using both methods:
  - `_transcribe_chunk_sync` (chunk mode): 445 chars
  - `_transcribe_sync` (single-pass mode): 9346 chars
- This revealed the chunk prompt was causing Gemini to return truncated results

## The Solution

### Key Findings
1. **The chunk prompt was too vague** - "Transcribe this audio segment" was interpreted as "give me a brief excerpt"
2. **All 3 chunks were being processed** - The chunking logic was correct, but chunks 2 and 3 returned almost no content
3. **Gemini needs explicit instructions** - Without strong language about transcribing "ALL speech", it takes shortcuts

### Code Changes

**Before (gemini.py:474):**
```python
prompt = (
    f"Transcribe this audio segment in plain text format.\n\n"
    f"IMPORTANT: This is chunk {chunk_index + 1} starting at "
    f"{hours:02d}:{minutes:02d}:{seconds:02d} in the full recording.\n\n"
    ...
)
```

**After:**
```python
prompt = (
    f"Transcribe this ENTIRE audio file in plain text format.\n\n"
    f"CRITICAL: You MUST transcribe ALL speech in this audio from start to finish.\n"
    f"This audio is approximately {CHUNK_DURATION_SECONDS // 60} minutes long.\n"
    f"Do not stop early or summarize - transcribe every word spoken.\n\n"
    ...
)
```

**Also added logging to chunking.py:**
```python
def needs_chunking(audio_path, threshold):
    try:
        duration = get_audio_duration(audio_path)
        needs_it = duration > threshold
        logger.debug(f"Audio duration: {duration:.1f}s, needs_chunking: {needs_it}")
        return needs_it
    except RuntimeError as e:
        logger.warning(f"Failed to determine audio duration: {e}. Skipping chunking.")
        return False
```

### Results

| Metric | Before | After |
|--------|--------|-------|
| Text length | 9,100 chars | 13,737 chars |
| Last segment | 9.1 min | 21.4 min |
| GPT-5.1 content | Missing | Present |

### Key Insights
1. **LLM prompts for audio transcription need explicit length expectations** - Tell the model how long the audio is and that you want ALL of it
2. **"CRITICAL" and strong language helps** - Gemini responds to urgency in prompts
3. **Silent failures are dangerous** - The original `needs_chunking()` silently returned `False` on ffprobe errors, which could cause truncation
4. **Test each component in isolation** - Comparing chunk vs single-pass on the same audio instantly revealed the issue

## Lessons Learned

1. **When debugging LLM output issues, test the same input with different prompts** - The audio was fine, the prompt was the problem
2. **Add logging to conditional branches** - If `needs_chunking()` had logged its decision, this would have been easier to diagnose
3. **Explicit > Implicit for LLM instructions** - Don't assume the model knows what "transcribe" means; spell out exactly what you want
4. **Duration hints help** - Telling Gemini "this is 10 minutes long" sets expectations for output length

## Related Resources

- **Files modified:**
  - `src/inkwell/transcription/gemini.py` - Fixed chunk prompt
  - `src/inkwell/transcription/chunking.py` - Added logging
- **Release:** v0.17.2
- **Commit:** `84702c3`
- **Test episode:** "Gemini 3 vs. Claude Opus 4.5 vs. GPT-5.1 Codex: Which AI model is the best designer?" from how-i-ai podcast
