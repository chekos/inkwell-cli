# ADR-026: Obsidian Integration Architecture

**Date**: 2025-11-09
**Status**: Accepted
**Context**: Phase 5 Unit 1 - Research & Architecture
**Related**: [Research: Obsidian Integration Patterns](../research/obsidian-integration-patterns.md)

## Context

Inkwell currently generates basic markdown files with YAML frontmatter. Phase 5 aims to add deep Obsidian integration including:
- Automatic wikilink generation for entities (people, books, tools)
- Smart hierarchical tag generation
- Dataview-compatible frontmatter
- Cross-episode linking

We need to design an architecture that seamlessly integrates with Obsidian while remaining optional for users who don't use Obsidian.

## Research Summary

See [Research: Obsidian Integration Patterns](../research/obsidian-integration-patterns.md) for detailed findings.

**Key findings:**
1. Wikilinks (`[[Name]]`) are essential for Obsidian's value proposition
2. Hierarchical tags (`#podcast/name`) scale better than flat tags
3. Dataview requires consistent, typed frontmatter fields
4. Graph View requires intentional, meaningful links

## Decision

We will implement Obsidian integration as a **modular system** with three components:

### 1. Wikilink Generation System

**Module:** `src/inkwell/obsidian/wikilinks.py`

**Architecture:**
```
Entity Extraction → Entity Validation → Wikilink Formatting → Markdown Integration
```

**Implementation:**
- **Entity Extractor:** Detect entities in transcript and extracted content
  - People (speakers, guests, references)
  - Books (titles and authors)
  - Tools/Software
  - Concepts (from key-concepts template)
- **Validation:** Use pattern matching + optional LLM validation (Gemini for cost)
- **Formatting:** Convert entities to wikilinks with consistent naming
- **Integration:** Replace mentions in markdown with wikilinks

**Wikilink Style Decision:**
- Use simple format: `[[Name]]` not `[[Type - Name]]`
- Rationale: Cleaner, matches community conventions
- Custom display text when context demands: `[[Deep Work|Cal's book on focus]]`

**Cross-Episode Linking:**
- Detect episode references in content
- Link to other episodes in same podcast
- Format: `[[Podcast Name - Episode Title]]` or `[[Episode NNN]]` if configured

### 2. Tag Generation System

**Module:** `src/inkwell/obsidian/tags.py`

**Architecture:**
```
Content Analysis → Tag Suggestions (LLM) → Tag Normalization → Frontmatter Integration
```

**Tag Hierarchy:**
```
#podcast/<show-name>          # Podcast identity
#topic/<category>              # Content topics
#topic/<category>/<subtopic>   # Nested topics
#person/<name>                 # People mentioned (key guests)
#status/<state>                # Workflow state
#type/<document-type>          # Document classification
```

**Implementation:**
- **LLM-based:** Use Gemini for cost-effective tag suggestions
- **Input:** Episode summary, key concepts, entities extracted
- **Normalization:** Lowercase, kebab-case, validate characters
- **Storage:** YAML frontmatter (not inline tags)
- **Limit:** 5-7 tags per note (configurable)

**Tag Template:**
```yaml
tags:
  - podcast/<show-name>
  - topic/<primary-topic>
  - topic/<secondary-topic>
  - person/<guest-name>        # if notable guest
  - status/unreviewed          # default, user can change
```

### 3. Dataview Frontmatter Enhancement

**Module:** `src/inkwell/obsidian/dataview.py`

**Architecture:**
```
Metadata Collection → Type Validation → Frontmatter Generation → Output
```

**Frontmatter Schema:**
```yaml
---
# Document classification
type: podcast-note
podcast: <show-name>
episode: <episode-number-or-title>

# Temporal metadata
date: YYYY-MM-DD                # Publication date
processed_date: YYYY-MM-DD      # When processed by Inkwell
duration: <seconds>             # Integer

# Content metadata
topics: [<topic1>, <topic2>]    # List of topics
people: [<person1>, <person2>]  # List of people as strings or wikilinks
books: [<book1>, <book2>]       # List of books
tools: [<tool1>, <tool2>]       # List of tools

# Workflow metadata
status: unreviewed              # unreviewed | reviewed | archived
rating: <1-5>                   # User rating (null initially)
actionable: <boolean>           # Has action items?
action_items: <count>           # Number of action items

# Inkwell metadata
transcription_source: <source>  # youtube | gemini
interview_conducted: <boolean>  # Was interview completed?
templates_applied: [<list>]     # Templates used

# Cost tracking
cost_transcription: <float>
cost_extraction: <float>
cost_interview: <float>
cost_wikilinks: <float>
cost_tags: <float>
cost_total: <float>

# Tags (hierarchical)
tags:
  - podcast/<show-name>
  - topic/<topic>
  - person/<name>
  - status/unreviewed
---
```

**Key Design Principles:**
1. **Consistent field names** across all notes
2. **Appropriate data types** (dates as YYYY-MM-DD, booleans as true/false, numbers as integers/floats)
3. **Lists for multi-value** fields
4. **Wikilinks in lists** where appropriate: `people: [[Cal Newport]]`
5. **Queryable fields** for common use cases

### 4. Integration Points

**With existing systems:**

```python
# src/inkwell/output/manager.py - OutputManager
# BEFORE Phase 5:
def write_episode(episode_metadata, extraction_results):
    # Generate markdown files
    # Write to disk
    pass

# AFTER Phase 5:
def write_episode(episode_metadata, extraction_results, enable_obsidian=True):
    markdown_files = self.markdown_generator.generate_all(extraction_results)

    if enable_obsidian:
        # Wikilink generation
        entities = wikilink_generator.extract_entities(
            transcript=transcript,
            extraction_results=extraction_results
        )
        wikilinks = wikilink_generator.format_wikilinks(entities)

        # Apply wikilinks to markdown
        markdown_files = wikilink_generator.apply_to_markdown(
            markdown_files,
            wikilinks
        )

        # Tag generation
        tags = tag_generator.generate_tags(
            episode=episode_metadata,
            summary=extraction_results['summary'],
            concepts=extraction_results['key-concepts']
        )

        # Enhanced frontmatter
        frontmatter = dataview_generator.generate_frontmatter(
            episode=episode_metadata,
            extraction_results=extraction_results,
            tags=tags,
            entities=entities
        )

        # Update metadata in files
        markdown_files = update_frontmatter(markdown_files, frontmatter)

    # Write to disk
    self.write_files(markdown_files)
```

## Implementation Plan

### Phase 5 Unit 3: Wikilink System (2 days)
1. Entity extraction (pattern-based + LLM validation)
2. Wikilink formatting with naming conventions
3. Markdown integration (replace mentions)
4. Cross-episode linking

### Phase 5 Unit 4: Tag Generation (1 day)
1. LLM-based tag suggestions (Gemini)
2. Tag normalization and validation
3. Hierarchical tag structure
4. Frontmatter integration

### Phase 5 Unit 5: Dataview Enhancement (1 day)
1. Enhanced frontmatter schema
2. Type validation
3. Example Dataview queries
4. Custom field support

## Configuration

**User configuration** (`~/.config/inkwell/config.yaml`):

```yaml
obsidian:
  enabled: true                        # Enable Obsidian features

  wikilinks:
    enabled: true
    style: simple                      # simple: [[Name]], prefixed: [[Type - Name]]
    cross_episode_linking: true

  tags:
    enabled: true
    max_tags: 7                        # Limit per note
    custom_hierarchies:
      tech-podcasts:
        - topic/ai
        - topic/programming
        - topic/startup

  dataview:
    enabled: true
    custom_fields: {}                  # User-defined frontmatter fields
```

**Per-podcast overrides** (`~/.config/inkwell/feeds.yaml`):

```yaml
deep-questions:
  url: https://...
  category: productivity
  obsidian:
    tag_prefix: dq                     # Custom tag prefix
    wikilink_style: prefixed           # Override global style
```

## Consequences

### Positive

1. **Deep Obsidian integration** - Wikilinks, tags, Dataview work seamlessly
2. **Modular design** - Can be disabled for non-Obsidian users
3. **Cost-effective** - Use Gemini for tag generation ($0.002/note)
4. **Scalable** - Hierarchical tags and consistent frontmatter enable large-scale use
5. **User control** - Extensive configuration options

### Negative

1. **Complexity** - Three new modules to implement and test
2. **Cost increase** - Adds ~$0.005/episode (wikilinks + tags)
3. **LLM dependency** - Tag quality depends on LLM performance
4. **Obsidian-specific** - Features only useful in Obsidian (but optional)

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM tag quality varies | Pattern-based fallback, user review |
| Cost concerns | Use Gemini, cache results, make optional |
| Obsidian version changes | Follow stable API, test with updates |
| Performance impact | Generate concurrently with extraction |
| Entity extraction accuracy | Combine patterns + LLM, confidence scores |

## Alternatives Considered

### Alternative 1: Pattern-Based Only (No LLM)
**Pros:** Free, fast, deterministic
**Cons:** Lower quality tags and entity extraction
**Decision:** Use hybrid approach (patterns + LLM validation)

### Alternative 2: Claude for All Obsidian Features
**Pros:** Highest quality
**Cons:** 40x more expensive ($0.08/episode vs $0.005)
**Decision:** Use Gemini for cost optimization

### Alternative 3: Post-Processing Script
**Pros:** Separates concerns, optional
**Cons:** Extra step for users, breaks atomic workflow
**Decision:** Integrate into main pipeline, make optional via config

### Alternative 4: Obsidian Plugin
**Pros:** Native Obsidian integration
**Cons:** Requires learning plugin development, different language (TypeScript)
**Decision:** CLI-first approach, potential future plugin

## Success Metrics

- ✅ Wikilinks generated for 90%+ of entities (people, books, tools)
- ✅ Tags relevant and useful (user survey)
- ✅ Dataview queries work out of the box (test with 5 common queries)
- ✅ Graph View shows meaningful connections
- ✅ Cost per episode <$0.01 for Obsidian features
- ✅ Processing time increase <2 seconds
- ✅ Can be disabled without breaking core functionality

## Implementation Checklist

- [ ] Create `src/inkwell/obsidian/` module
- [ ] Implement entity extraction (wikilinks.py)
- [ ] Implement tag generation (tags.py)
- [ ] Implement Dataview frontmatter (dataview.py)
- [ ] Integrate with OutputManager
- [ ] Add configuration options
- [ ] Write unit tests (>90% coverage)
- [ ] Test in real Obsidian vault
- [ ] Document in user guide
- [ ] Create example Dataview queries

## References

- [Research: Obsidian Integration Patterns](../research/obsidian-integration-patterns.md)
- [Obsidian Help - Internal Links](https://help.obsidian.md/links)
- [Dataview Plugin Documentation](https://blacksmithgu.github.io/obsidian-dataview/)
- [ADR-018: Markdown Output Format](./018-markdown-output-format.md) (existing frontmatter)

---

**Decision Made By:** Phase 5 Team
**Status:** Accepted
**Next Review:** After Phase 5 Unit 5 completion
