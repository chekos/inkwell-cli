# Phase 5 Unit 1: Research & Architecture

**Date**: 2025-11-09
**Unit**: 1 of 10
**Duration**: 1 day
**Status**: Complete

## Overview

Unit 1 establishes the foundation for Phase 5 by conducting comprehensive research into Obsidian integration patterns and error handling best practices, then designing the architecture for both systems.

**Key Deliverables:**
- ✅ 2 research documents (Obsidian patterns, error handling)
- ✅ 2 ADRs (Obsidian architecture, retry strategy)
- ✅ This devlog

---

## What Was Accomplished

### 1. Obsidian Integration Research

**Document:** [research/obsidian-integration-patterns.md](../research/obsidian-integration-patterns.md)

#### Key Findings

**Wikilinks (`[[Name]]`)**
- Core to Obsidian's value proposition
- Enable bidirectional linking, backlinks, Graph View
- Must use wikilink format, not markdown links
- Support for headings (`[[Note#Heading]]`) and blocks (`[[Note#^block-id]]`)
- Custom display text with pipe: `[[Note|Display]]`

**Hierarchical Tags**
- Forward slash creates hierarchy: `#parent/child`
- Scales better than flat tags at large scale
- Best stored in YAML frontmatter, not inline
- Limit to 5-7 tags per note for cognitive load
- Use namespace prefixes: `#podcast/`, `#topic/`, `#person/`

**Dataview Plugin**
- Treats vault as queryable database
- Requires consistent field names across notes
- Supports YAML frontmatter, inline fields, implicit fields
- Data types matter: dates (YYYY-MM-DD), booleans, numbers, lists
- Query language: LIST, TABLE, TASK, CALENDAR

**Graph View**
- Visualizes notes as network (nodes = notes, edges = wikilinks)
- Requires intentional, meaningful links
- Too many links = noise, too few = isolation
- Hub notes create visual hierarchy

#### Recommendations

For Inkwell implementation:
1. **Wikilinks:** Auto-generate for people, books, tools, concepts
2. **Tags:** Hierarchical structure with 5-7 per note
3. **Frontmatter:** Design for Dataview queryability
4. **Linking:** Focus on cross-episode references and entities

### 2. Error Handling Research

**Document:** [research/error-handling-best-practices.md](../research/error-handling-best-practices.md)

#### Key Findings

**Exponential Backoff with Jitter (Industry Standard)**
- Prevents "thundering herd" problem
- Equal jitter balances spread with minimum wait
- Formula: `temp/2 + random(0, temp/2)` where `temp = min(cap, base * 2^attempt)`
- Recommended by AWS, Google, Microsoft

**Tenacity Library (Best for Python)**
- Most comprehensive and flexible
- Excellent async support (critical for Inkwell)
- Declarative decorator API
- Well-tested and maintained

**Error Classification**
- **Retry on:** 408, 429, 500, 502, 503, 504, network errors
- **Don't retry on:** 400, 401, 403, 404, 422
- Always set max retry limits (prevent infinite loops)
- Respect `Retry-After` headers

**Best Practices**
1. Log retry attempts for debugging
2. Show retry progress to users
3. Provide helpful error messages with suggestions
4. Use token bucket for local rate limiting
5. Implement circuit breaker for repeated failures

#### Recommendations

For Inkwell implementation:
1. **Library:** Use Tenacity
2. **Strategy:** Exponential backoff with equal jitter
3. **Limits:** Max 3 attempts, max 60s wait
4. **Apply to:** TranscriptionManager, ExtractionEngine, InterviewAgent, FeedParser
5. **UX:** Show retry progress with Rich, provide helpful errors

### 3. Obsidian Integration Architecture

**Document:** [adr/026-obsidian-integration-architecture.md](../adr/026-obsidian-integration-architecture.md)

#### Architecture Design

**Three-Module System:**

1. **Wikilink Generation** (`src/inkwell/obsidian/wikilinks.py`)
   ```
   Entity Extraction → Validation → Formatting → Integration
   ```
   - Extract entities: people, books, tools, concepts
   - Validate with pattern matching + optional LLM
   - Format as `[[Name]]` or `[[Name|Display]]`
   - Replace mentions in markdown

2. **Tag Generation** (`src/inkwell/obsidian/tags.py`)
   ```
   Content Analysis → LLM Suggestions → Normalization → Frontmatter
   ```
   - Use Gemini for cost-effective suggestions
   - Hierarchical structure: `#podcast/name`, `#topic/ai`
   - Normalize: lowercase, kebab-case
   - Store in YAML frontmatter

3. **Dataview Frontmatter** (`src/inkwell/obsidian/dataview.py`)
   ```
   Metadata Collection → Type Validation → Generation → Output
   ```
   - Consistent field names across all notes
   - Appropriate data types (dates, booleans, numbers)
   - Queryable fields for common use cases
   - Custom field support

#### Frontmatter Schema

```yaml
---
# Document classification
type: podcast-note
podcast: <show-name>
episode: <episode-title>

# Temporal
date: YYYY-MM-DD
duration: <seconds>

# Content
topics: [<list>]
people: [<list>]
books: [<list>]
tools: [<list>]

# Workflow
status: unreviewed
rating: <1-5>
actionable: <boolean>

# Inkwell
transcription_source: <source>
interview_conducted: <boolean>
cost_total: <float>

# Tags
tags:
  - podcast/<name>
  - topic/<topic>
  - person/<name>
---
```

#### Configuration

```yaml
# ~/.config/inkwell/config.yaml
obsidian:
  enabled: true
  wikilinks:
    enabled: true
    style: simple  # or prefixed
  tags:
    enabled: true
    max_tags: 7
  dataview:
    enabled: true
```

#### Cost Impact

- Wikilink generation (Gemini): ~$0.003/episode
- Tag generation (Gemini): ~$0.002/episode
- **Total Obsidian features: ~$0.005/episode**

Much cheaper than using Claude ($0.08/episode).

### 4. Retry and Error Handling Strategy

**Document:** [adr/027-retry-and-error-handling-strategy.md](../adr/027-retry-and-error-handling-strategy.md)

#### Retry Strategy

**Exponential Backoff with Equal Jitter:**
- Attempt 1: 0s (initial)
- Attempt 2: 1-2s
- Attempt 3: 2-4s
- Attempt 4: 4-8s (if max_attempts=4)

**Max attempts:** 3 (configurable)
**Max wait:** 60 seconds

**Configuration:**
```yaml
# ~/.config/inkwell/config.yaml
retry:
  enabled: true
  max_attempts: 3
  max_wait: 60
  show_progress: true
```

#### Retry Utility

**Location:** `src/inkwell/utils/retry.py`

```python
from inkwell.utils.retry import with_retry

@with_retry(
    max_attempts=3,
    retry_on=(ConnectionError, TimeoutError, RateLimitError)
)
async def api_call():
    # Your API logic
    pass
```

#### Enhanced Errors

**Location:** `src/inkwell/utils/errors.py` (enhanced)

```python
class APIKeyError(InkwellError):
    """Missing or invalid API key."""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Missing or invalid API key for {provider}",
            suggestion=f"Set your API key with: inkwell config set {provider.lower()}_api_key YOUR_KEY"
        )
```

**Error format:**
```
❌ Missing or invalid API key for Gemini

💡 Suggestion: Set your API key with: inkwell config set gemini_api_key YOUR_KEY

📖 Learn more: https://docs.inkwell.cli/setup/api-keys
```

#### Application Points

Will be applied in Unit 6 to:
- `TranscriptionManager` - Gemini API calls
- `ExtractionEngine` - Claude/Gemini API calls
- `InterviewAgent` - Claude Agent SDK calls
- `FeedParser` - RSS feed fetching

---

## Architectural Decisions Summary

### ADR-026: Obsidian Integration Architecture

**Decision:** Modular three-component system (wikilinks, tags, Dataview)

**Key choices:**
- Wikilink style: Simple `[[Name]]` format
- Tag hierarchy: Namespace prefixes (`#podcast/`, `#topic/`)
- LLM: Gemini for cost optimization ($0.005 vs $0.08 with Claude)
- Storage: YAML frontmatter for tags (not inline)
- Optional: Can be disabled for non-Obsidian users

**Trade-offs:**
- ✅ Cost-effective, scalable, deeply integrated
- ❌ Adds complexity, Obsidian-specific, LLM dependency

### ADR-027: Retry and Error Handling Strategy

**Decision:** Exponential backoff with equal jitter using Tenacity library

**Key choices:**
- Library: Tenacity (most flexible)
- Strategy: Equal jitter (balanced spread)
- Limits: 3 attempts, 60s max wait
- Classification: Retry transient (429, 5xx), fail permanent (4xx)
- UX: Show retry progress, helpful error messages

**Trade-offs:**
- ✅ Resilient, user-friendly, configurable
- ❌ Longer waits on failures, dependency, complexity

---

## Lessons Learned

### Research Process

1. **Web search is invaluable**
   - Found current best practices and community wisdom
   - Obsidian docs and forums provided real-world patterns
   - AWS Builders Library is gold standard for distributed systems

2. **Multiple sources confirm patterns**
   - Exponential backoff + jitter recommended everywhere
   - Tenacity clearly the best Python library
   - Hierarchical tags universally preferred in Obsidian

3. **Cost analysis is critical**
   - Claude ($0.08) vs Gemini ($0.005) = 16x difference
   - For optional features, must optimize cost
   - Users care about per-episode costs

### Architecture Design

1. **Modularity enables flexibility**
   - Each Obsidian feature can be enabled/disabled
   - Non-Obsidian users unaffected
   - Easy to test components independently

2. **Configuration is essential**
   - Users have different preferences
   - Some want all features, some want minimal
   - Per-podcast overrides add power-user control

3. **Error messages matter**
   - Helpful suggestions reduce support burden
   - "What to do" more important than "what happened"
   - Links to docs empower users

### Technical Insights

1. **Jitter solves thundering herd**
   - Without: All clients retry simultaneously
   - With: Requests spread out, service can recover
   - Equal jitter balances guaranteed wait with spread

2. **Dataview requires discipline**
   - Consistent field names across all notes
   - Appropriate data types (dates, booleans)
   - Worth the effort for queryability

3. **Wikilinks are not markdown links**
   - Different syntax, different capabilities
   - Obsidian built around wikilinks
   - Must use `[[]]` not `[]()`

---

## Next Steps

### Unit 2: CLI Interview Integration (Day 2)
- Add `--interview` flag to `fetch` command
- Connect InterviewManager to main pipeline
- Test end-to-end flow

### Unit 3: Wikilink System (Days 3-4)
- Implement entity extraction
- Implement wikilink formatting
- Integrate with markdown generation

### Unit 4: Tag Generation (Day 5)
- Implement LLM-based tag suggestions
- Implement tag normalization
- Integrate with frontmatter

### Unit 5: Dataview Enhancement (Day 6)
- Implement enhanced frontmatter schema
- Create example Dataview queries
- Test in real Obsidian vault

### Unit 6: Error Handling (Day 7)
- Implement retry utility module
- Apply to all API calls
- Test error scenarios

---

## Documentation Created

| Type | File | Status |
|------|------|--------|
| Research | `research/obsidian-integration-patterns.md` | ✅ Complete |
| Research | `research/error-handling-best-practices.md` | ✅ Complete |
| ADR | `adr/026-obsidian-integration-architecture.md` | ✅ Complete |
| ADR | `adr/027-retry-and-error-handling-strategy.md` | ✅ Complete |
| Devlog | `devlog/2025-11-09-phase-5-unit-1-research.md` | ✅ Complete |

**Total:** 5 documents, ~15,000 words

---

## Metrics

**Time Spent:**
- Obsidian research: 4 hours
- Error handling research: 2 hours
- Architecture design: 2 hours
- Documentation: 2 hours
- **Total: ~10 hours** (1 working day)

**Research Sources:**
- 5 web searches conducted
- 20+ articles and docs reviewed
- 2 comprehensive research docs created
- 2 architectural decision records

**Lines of Documentation:**
- Research docs: ~2,000 lines
- ADRs: ~1,500 lines
- Devlog: ~500 lines
- **Total: ~4,000 lines**

---

## Conclusion

Unit 1 successfully established the research and architectural foundation for Phase 5. We now have:

1. **Clear understanding** of Obsidian integration requirements
2. **Proven patterns** for error handling and retries
3. **Documented architecture** for three major systems
4. **Cost-optimized approach** using Gemini where appropriate
5. **User-first design** with configuration and helpful errors

The research phase revealed that:
- Obsidian integration is well-documented and has community consensus
- Error handling best practices are consistent across industry leaders
- Both systems can be implemented without reinventing wheels

**Ready to proceed with Unit 2: CLI Interview Integration** 🚀

---

**Status:** ✅ Unit 1 Complete
**Next:** Unit 2 - CLI Interview Integration
**Phase 5 Progress:** 1/10 units complete (10%)
