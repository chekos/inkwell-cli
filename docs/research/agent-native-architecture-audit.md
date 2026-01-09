# Agent-Native Architecture Audit

**Date:** 2026-01-09
**Status:** Complete
**Overall Score:** 52%

## Overview

This document captures a comprehensive audit of the Inkwell CLI codebase against agent-native architecture principles. The audit evaluates 8 core principles that define whether an application enables agents to work effectively alongside users.

## Overall Score Summary

| Core Principle | Score | Percentage | Status |
|----------------|-------|------------|--------|
| Action Parity | 0/27 | 0% | ❌ |
| Tools as Primitives | 5/17 | 29% | ❌ |
| Context Injection | 2/7 | 28% | ❌ |
| Shared Workspace | 8/8 | 100% | ✅ |
| CRUD Completeness | 5/8 | 62% | ⚠️ |
| UI Integration | 17/20 | 85% | ✅ |
| Capability Discovery | 5/7 | 71% | ⚠️ |
| Prompt-Native Features | 4/10 | 40% | ❌ |

**Overall Agent-Native Score: 52%**

### Status Legend
- ✅ Excellent (80%+)
- ⚠️ Partial (50-79%)
- ❌ Needs Work (<50%)

---

## Top 10 Recommendations by Impact

| Priority | Action | Principle | Effort |
|----------|--------|-----------|--------|
| 1 | **Create MCP tool definitions** wrapping PipelineOrchestrator methods (process_episode, transcribe, etc.) | Action Parity | High |
| 2 | **Move interview system prompt to YAML template** instead of hardcoded Python | Prompt-Native | Low |
| 3 | **Extract LLM Client as primitive** - separate API calls from prompt building | Tools as Primitives | Medium |
| 4 | **Inject available resources** (feeds, templates, processed episodes) into agent prompts | Context Injection | Medium |
| 5 | **Add episode deletion command** (`inkwell delete <episode>`) | CRUD Completeness | Low |
| 6 | **Add `/help` command to interview mode** for capability discovery | Capability Discovery | Low |
| 7 | **Extract category detection keywords** from code to config YAML | Prompt-Native | Low |
| 8 | **Inject user preferences from config** into extraction and interview prompts | Context Injection | Medium |
| 9 | **Split ExtractionEngine** into primitives: API client + prompt builder + output parser | Tools as Primitives | High |
| 10 | **Add contextual hints after fetch completes** suggesting interview mode and cost tracking | Capability Discovery | Low |

---

## What's Working Excellently

1. **Shared Workspace (100%)** - Agent and user operate in the same data space with seamless bidirectional access. Interview agent reads extraction results directly, writes to same episode directory.

2. **UI Integration (85%)** - Excellent Rich library integration with progress bars, spinners, and real-time feedback. Progress callback architecture enables loose coupling.

3. **Extraction Templates** - Summary, quotes, and key-concepts fully prompt-native in YAML with Jinja2 templating.

4. **Atomic File Writes** - Files written to temp location then moved, with backup mechanism for safety.

5. **Cost Transparency** - All API costs tracked and displayed, with `--dry-run` for estimates.

---

## Critical Gaps

### Action Parity (0%)
The codebase has **zero agent tools defined**. All 27 user actions (add feed, transcribe, fetch, interview, etc.) are CLI-only. The excellent programmatic APIs (PipelineOrchestrator, TranscriptionManager, ConfigManager) exist but are **not exposed as MCP tools**.

**Impact:** An agent cannot programmatically process podcasts, manage feeds, or conduct interviews.

### Tools as Primitives (29%)
Architecture uses **service/orchestrator pattern** instead of composable primitives. ClaudeExtractor, GeminiExtractor, and ExtractionEngine bundle multiple concerns (API calls + prompt building + validation + cost tracking).

**Impact:** Cannot compose tools flexibly; business logic is embedded in services.

### Context Injection (28%)
Agent prompts receive minimal context:
- ❌ No list of available feeds or processed episodes
- ❌ No user preferences from config
- ❌ No available capabilities listing
- ❌ Only last 3 interview exchanges retained

**Impact:** Agent operates blindly without knowing workspace state or user preferences.

### Prompt-Native Features (40%)
Interview system prompt is **hardcoded in Python** despite ADR-023 designing a template-based system. Category detection uses hardcoded keyword lists. Provider selection heuristics embedded in code.

**Impact:** Behavior changes require code changes instead of prompt edits.

---

## Detailed Principle Reports

### 1. Action Parity: 0/27 (0%) ❌

**Definition:** "Whatever the user can do, the agent can do."

**User actions available (27 total):**
- Feed management: add, list, remove (3)
- Configuration: show, edit, set (3)
- Transcription: transcribe with options (3)
- Cache: stats, clear, clear-expired (3)
- Processing: fetch with 8+ options (9)
- Interview: start, resume, template, format, max-questions (5)
- Cost tracking: view, filter, clear (4)

**Agent tools: 0**

No MCP tools, no agent SDK tool definitions. The interview mode uses direct AsyncAnthropic API, not agent tools.

#### Missing Agent Tools

| Category | Tools Needed |
|----------|--------------|
| Feed Management | `add_podcast_feed`, `list_podcast_feeds`, `remove_podcast_feed`, `get_feed` |
| Configuration | `get_config`, `set_config_value`, `reset_config` |
| Transcription | `transcribe_url`, `get_cache_stats`, `clear_transcript_cache` |
| Processing | `process_episode`, `estimate_processing_cost` |
| Interview | `conduct_interview`, `resume_interview` |
| Extraction | `extract_content`, `select_templates_for_category` |
| Analytics | `get_cost_summary`, `get_recent_operations`, `clear_cost_history` |

#### Recommendation

Create MCP tool definitions in `src/inkwell/agent/tools.py` that wrap the existing programmatic APIs:
- `PipelineOrchestrator.process_episode()`
- `TranscriptionManager.transcribe()`
- `ConfigManager` methods
- `SimpleInterviewer.conduct_interview()`

---

### 2. Tools as Primitives: 5/17 (29%) ❌

**Definition:** "Tools provide capability, not behavior."

#### Component Analysis

| Component | Type | Reasoning |
|-----------|------|-----------|
| AudioDownloader | ✅ PRIMITIVE | Pure capability: downloads audio, reports progress |
| RSSParser | ✅ PRIMITIVE | Pure I/O: fetches feed, parses XML |
| TemplateLoader | ✅ PRIMITIVE | Loads YAML files, returns objects |
| ExtractionCache | ✅ PRIMITIVE | Simple get/set storage |
| TranscriptCache | ✅ PRIMITIVE | Simple caching without business logic |
| CostTracker | ✅ PRIMITIVE | Pure telemetry |
| YouTubeTranscriber | ❌ WORKFLOW | Combines URL checking, API calls, language selection |
| GeminiTranscriber | ❌ WORKFLOW | Chains audio analysis, transcription, cost tracking |
| ClaudeExtractor | ❌ WORKFLOW | Bundles prompt building, API calls, validation |
| GeminiExtractor | ❌ WORKFLOW | Same as ClaudeExtractor |
| BaseExtractor | ❌ WORKFLOW | Includes Jinja2 templating logic |
| ExtractionEngine | ❌ WORKFLOW | Complex orchestration hub |
| TranscriptionManager | ❌ WORKFLOW | Multi-tier strategy selection |
| SimpleInterviewer | ❌ WORKFLOW | Interview flow + question generation + formatting |
| PipelineOrchestrator | ❌ WORKFLOW | Top-level coordination |
| OutputManager | ❌ WORKFLOW | File I/O with business logic |
| MarkdownGenerator | ❌ WORKFLOW | Presentation logic |

#### Missing Primitives

```
SHOULD EXIST:
- LLMClient: Just makes API calls, nothing else
- PromptTemplate: Renders a template with variables
- JSONValidator: Validates output against schema
- FileWriter: Atomic file writes
- ProgressReporter: Reports progress without logic
```

#### Recommendation

Extract LLM Client as a primitive:
```python
# Layer 1: LLMClient (primitive)
async def call(model, system, messages) -> Response

# Layer 2: ExtractionWorkflow (orchestration)
# Builds prompt → calls LLMClient → parses output
```

---

### 3. Context Injection: 2/7 (28%) ❌

**Definition:** "System prompt includes dynamic context about app state."

#### Context Types Analysis

| Context Type | Injected? | Location | Notes |
|--------------|-----------|----------|-------|
| Available resources | ❌ No | N/A | No feed list, transcript list, or available templates injected |
| User preferences | ❌ No | N/A | Config exists but NOT passed to LLMs |
| Recent activity | ❌ No | N/A | No recent episodes or processing history |
| Available capabilities | ❌ No | N/A | Agent never told what it can do |
| Session history | ⚠️ Minimal | `simple_interviewer.py:258-263` | Only last 3 Q&A exchanges |
| Workspace state | ❌ No | N/A | Output directories never passed to LLMs |
| Current episode context | ⚠️ Partial | `extractors/base.py:109-113` | Only 4 of 14 metadata fields passed |

#### What Should Be Injected

```python
context = {
    "transcript": transcript,
    "metadata": metadata,
    "available_templates": ["summary", "quotes", "key-concepts", "books-mentioned"],
    "recent_episodes": [{"title": "...", "date": "..."}],
    "configured_feeds": ["podcast1", "podcast2"],
    "user_preferences": {
        "interview_style": config.interview.default_template,
        "preferred_provider": config.extraction.default_provider
    }
}
```

---

### 4. Shared Workspace: 8/8 (100%) ✅

**Definition:** "Agent and user work in the same data space."

#### Data Store Analysis

| Data Store | Location | User Access | Agent Access | Shared? |
|------------|----------|-------------|--------------|---------|
| Episode Output | `~/podcasts/podcast-name-YYYY-MM-DD-title/` | Read/Write | Reads for interview context | ✅ YES |
| Metadata File | `.metadata.yaml` in episode directory | Read/Write | Reads + modifies after interview | ✅ YES |
| Extraction Results | `summary.md`, `quotes.md`, etc. | Read/Write | Reads directly | ✅ YES |
| Interview Notes | `my-notes.md` | Read/Write | Writes directly | ✅ YES |
| Config Files | `~/.config/inkwell/` | Read/Write | Reads settings | ✅ YES |
| Feeds Config | `~/.config/inkwell/feeds.yaml` | Read/Write | Reads feed info | ✅ YES |
| Transcription Cache | `~/.cache/inkwell/transcripts/` | System | Reads cached | ✅ YES |
| Extraction Cache | `~/.cache/inkwell/extractions/` | System | Reads cached | ✅ YES |

**Exemplary implementation** - no sandbox isolation anti-pattern. Interview agent reads extraction results directly and writes to the same episode directory users access.

---

### 5. CRUD Completeness: 5/8 (62%) ⚠️

**Definition:** "Every entity has full CRUD (Create, Read, Update, Delete)."

#### Entity CRUD Analysis

| Entity | Create | Read | Update | Delete | Score |
|--------|--------|------|--------|--------|-------|
| Podcast Feeds | ✓ | ✓ | ✓ | ✓ | 4/4 |
| Configuration | ✓ | ✓ | ✓ | - | 3/4 |
| Episodes | ✓ | ✓ | ✓ | - | 3/4 |
| Transcripts | ✓ | ✓ | - | ✓ | 3/4 |
| Extraction Cache | ✓ | ✓ | - | ✓ | 3/4 |
| Output Files | ✓ | ✓ | - | - | 2/4 |
| Interview Notes | ✓ | ✓ | - | - | 2/4 |
| Cost History | ✓ | ✓ | - | ✓ | 3/4 |

#### Missing Operations

- **Episode Deletion:** No `inkwell delete <episode-dir>`
- **Config Reset:** No `inkwell config reset`
- **Output File Editing:** No CLI for editing generated markdown
- **Interview Resume:** Session management was simplified out

---

### 6. UI Integration: 17/20 (85%) ✅

**Definition:** "Agent actions immediately reflected in UI."

#### Strengths

- **Rich Console Integration:** Progress bars, spinners, tables, colored output
- **Progress Callback Architecture:** Loose coupling between orchestrator and CLI
- **Atomic File Writes:** Temp location → move, with backup mechanism
- **Cost Transparency:** `--dry-run` for estimates, summary at completion

#### Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| Interview exchanges not persisted until completion | Medium | Interrupt = data loss |
| No per-template extraction streaming | Low | Aggregate results only |
| Audio download progress not wired to CLI | Low | Infrastructure exists |

---

### 7. Capability Discovery: 5/7 (71%) ⚠️

**Definition:** "Users can discover what the agent can do."

#### Discovery Mechanism Analysis

| Mechanism | Exists? | Quality |
|-----------|---------|---------|
| Onboarding flow | ⚠️ Partial | No first-run wizard |
| Help documentation | ✅ Yes | Good `--help` on all commands |
| Capability hints in output | ⚠️ Limited | Only empty state |
| Agent self-describes | ✅ Yes | Interview mode explains role |
| Suggested prompts | ⚠️ Minimal | Examples in docs only |
| Empty state guidance | ✅ Yes | Shows next step |
| Slash commands | ❌ No | No `/help` in interview |

#### Missing

- No `inkwell capabilities` command
- No `/help` in interview mode
- No contextual hints after operations complete

---

### 8. Prompt-Native Features: 4/10 (40%) ❌

**Definition:** "Features are prompts defining outcomes, not code."

#### Feature Definition Analysis

| Feature | Type | Location |
|---------|------|----------|
| Summary extraction | ✅ PROMPT | `templates/default/summary.yaml` |
| Quote extraction | ✅ PROMPT | `templates/default/quotes.yaml` |
| Key concepts extraction | ✅ PROMPT | `templates/default/key-concepts.yaml` |
| Books/Tools/People extraction | ✅ PROMPT | `templates/default/*.yaml` |
| Interview question generation | ❌ CODE | `simple_interviewer.py:241-253` |
| Category detection | ❌ CODE | `template_selector.py:146-192` |
| Template selection | ❌ CODE | `template_selector.py:43-124` |
| Provider selection | ❌ CODE | `engine.py:659-692` |
| Batch extraction prompt | ❌ CODE | `engine.py:758-847` |
| Cost estimation | ❌ CODE | `claude.py:33-34`, `gemini.py:37-40` |

#### Code-Defined Features (Anti-Patterns)

**Interview System Prompt (Critical):**
```python
# simple_interviewer.py:241-253
system_prompt = """You are conducting a thoughtful interview..."""
```
Should be: `interview_templates/reflective.yaml`

**Category Detection Keywords:**
```python
# template_selector.py:146-192
tech_keywords = ["software", "programming", "code", ...]
interview_keywords = ["guest", "author", "book", ...]
min_threshold = 3
```
Should be: `config/category_detection.yaml`

#### Design/Implementation Mismatch

ADR-023 designed a template-based interview system with three styles (reflective, analytical, creative), but the implementation has a single hardcoded Python prompt.

---

## Implementation Roadmap

### Phase 1: Quick Wins (Low Effort, High Impact)

1. Move interview system prompt to YAML template
2. Add `/help` command to interview mode
3. Add episode deletion command
4. Extract category keywords to config

### Phase 2: Medium Effort

5. Create MCP tool definitions for core operations
6. Inject user preferences into prompts
7. Inject available resources into agent context
8. Add contextual hints after operations

### Phase 3: Architectural (High Effort)

9. Extract LLM Client as primitive
10. Split ExtractionEngine into composable components
11. Implement full CRUD for all entities
12. Add interview session persistence

---

## Conclusion

Inkwell CLI is a **well-architected traditional CLI application** with excellent shared workspace patterns and UI integration. However, it is **not agent-native** - there are no exposed tools for agents to use, business logic is embedded in service classes rather than prompts, and minimal context is injected into LLM interactions.

**To become agent-native:**
1. Expose programmatic APIs as MCP tools (Action Parity)
2. Refactor services into composable primitives (Tools as Primitives)
3. Inject workspace state and preferences into prompts (Context Injection)
4. Move hardcoded behavior to YAML templates (Prompt-Native Features)

---

## References

- [Agent-Native Architecture Principles](https://github.com/anthropics/claude-code) - Claude Code SDK documentation
- [ADR-023: Interview Template System](../adr/023-interview-template-system.md) - Design for template-based interviews
- [ADR-014: Template Format](../adr/014-template-format.md) - YAML template specification
