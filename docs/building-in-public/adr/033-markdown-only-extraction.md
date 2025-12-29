# ADR-033: Markdown-Only Extraction Output

**Date**: 2025-12-22
**Status**: Accepted
**Context**: Extraction Pipeline Simplification
**Supersedes**: Previous JSON-based extraction approach

---

## Context

The extraction pipeline was using JSON as an intermediate format:
1. Transcript (text) → LLM → JSON output → Parse JSON → Convert to Markdown → Save .md file

This caused problems:
- LLMs frequently produced malformed JSON, causing parse failures
- The batched extraction approach (multiple templates in one call) made JSON even more error-prone
- Complex output schemas added unnecessary constraints
- The JSON step was pointless since the final output is always markdown

Templates like `quotes`, `key-concepts`, and `tools-mentioned` used `expected_format: json` with strict schemas, leading to 1/4 success rates even with individual extraction.

---

## Decision

**Remove JSON from the extraction pipeline entirely.** All templates now output markdown directly:

1. Changed all templates to `expected_format: markdown`
2. Removed `output_schema` and `few_shot_examples` from templates
3. Updated prompts to describe the desired markdown format inline
4. Removed batched extraction - each template gets its own focused LLM call

The new flow is simply:
```
Transcript (text) → LLM → Markdown output → Save .md file
```

---

## Template Changes

All templates updated to v1.1 with markdown output:

- `quotes.yaml` - Blockquotes with speaker attribution
- `key-concepts.yaml` - Headers with definition/context sections
- `tools-mentioned.yaml` - Bullet lists with categories
- `books-mentioned.yaml` - Bullet lists with author/context

Example prompt format change:
```yaml
# Before (JSON)
user_prompt_template: |
  Return as JSON:
  { "quotes": [{ "text": "...", "speaker": "..." }] }

expected_format: json
output_schema:
  type: object
  ...

# After (Markdown)
user_prompt_template: |
  Format each quote as:
  > "The exact quote text here."
  > — **Speaker Name** (timestamp)

expected_format: markdown
```

---

## Extraction Engine Changes

Removed batching logic from `extract_all_batched()`:
- Previously tried to batch all templates into one API call
- Now calls `_extract_individually()` directly
- Each template gets a focused, single-purpose LLM call
- Templates still run in parallel via `asyncio.gather`

---

## Consequences

### Positive

1. **100% success rate** - All 4 templates now extract successfully (was 1/4)
2. **Simpler pipeline** - No JSON parsing, no schema validation
3. **Better output** - LLM can focus on content, not format compliance
4. **Easier debugging** - Markdown is human-readable, JSON parse errors are not
5. **Focused calls** - Each template gets full LLM attention

### Negative

1. **No structured data** - Can't programmatically query extracted content
2. **Format variability** - LLM may format slightly differently each time

### Acceptable Trade-offs

The extracted content is meant for human reading in Obsidian, not programmatic access. Markdown is the right format for this use case.

---

## References

- [ADR-014: Template Format](014-template-format.md)
- [ADR-018: Markdown Output Format](018-markdown-output-format.md)
