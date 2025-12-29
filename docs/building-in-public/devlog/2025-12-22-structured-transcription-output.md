# Transcription & Extraction Improvements

**Date:** 2025-12-22
**Author:** Claude

## Focus

Two major improvements to the pipeline:
1. Structured JSON output for Gemini transcription (summaries + segments)
2. Simplified markdown-only extraction (removed JSON intermediate format)

## Progress

### Problem Identified

After processing a podcast episode, the `_transcript.md` file appeared unusually short - only 76 lines but containing 9,476 words. Investigation revealed:

1. Gemini was returning huge paragraphs instead of segmented speech
2. Timestamps were inconsistent (HH:MM:SS vs MM:SS)
3. Some timestamps like `[08:30:08]` didn't match the actual podcast duration (90 minutes)
4. No summary was provided despite being useful for quick reference

### Root Cause

The timestamps are **LLM-generated estimates**, not actual audio timecodes. Gemini doesn't analyze the audio waveform for timing - it generates approximate timestamps based on content flow.

### Solution Implemented

1. **Structured output schema**: Added JSON schema using `types.GenerateContentConfig` with `response_mime_type="application/json"`

2. **Schema structure**:
   ```json
   {
     "summary": "Brief overview of content",
     "segments": [
       {"timestamp": "00:00", "speaker": "Host", "text": "..."}
     ]
   }
   ```

3. **Updated transcript model**: Added `summary` field to `Transcript` pydantic model

4. **Updated output**: `_transcript.md` now shows:
   ```markdown
   # Transcript

   ## Summary
   [AI-generated summary]

   ---

   ## Full Transcript
   [Segmented transcript with timestamps and speakers]
   ```

## Observations

- **Structured output works well**: Gemini reliably returns valid JSON matching the schema
- **Timestamps are approximate**: Don't expect audio-accurate timecodes from LLM transcription
- **Summary is valuable**: Having a quick overview at the top makes transcripts much more usable
- **MM:SS format is cleaner**: Standardizing on MM:SS avoids confusion with HH:MM:SS

---

### Extraction Pipeline Simplification

After fixing transcription, extraction was still failing (1/4 templates succeeded). Investigation revealed:

1. Templates used `expected_format: json` with strict `output_schema`
2. LLMs frequently produced malformed JSON
3. The batched extraction approach made this worse
4. JSON was pointless - final output is always markdown anyway

**Solution: Remove JSON entirely**

- Changed all templates to `expected_format: markdown`
- Removed `output_schema` and complex validation
- Updated prompts to describe markdown format inline
- Removed batching - each template gets focused LLM call

Result: 4/4 templates now succeed. Clean markdown output.

## Observations

- **Structured output for transcription = good**: Gemini reliably returns valid JSON with the schema
- **Structured output for extraction = unnecessary**: The LLM just needs to output markdown
- **Focused calls > batched calls**: One task per LLM call produces better results
- **Simpler is better**: Transcript in → Markdown out, no intermediate formats

## Next

- Monitor extraction quality across different podcasts
- Consider structured output only where programmatic access is needed

## Links

- Related ADRs:
  - [ADR-032: Structured Transcription](../adr/032-gemini-structured-transcription-output.md)
  - [ADR-033: Markdown-Only Extraction](../adr/033-markdown-only-extraction.md)
- Google Docs: https://ai.google.dev/gemini-api/docs/structured-output
