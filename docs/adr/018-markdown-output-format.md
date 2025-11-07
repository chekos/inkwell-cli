# ADR-018: Markdown Output Format

**Date**: 2025-11-07
**Status**: Accepted
**Context**: Phase 3 Unit 6 - Markdown Output System

---

## Context

Extracted content needs to be formatted as readable markdown files that users can:
- Read in any markdown viewer
- Import into Obsidian/Notion/Roam
- Search and reference
- Link between notes

We need to decide:
1. Markdown structure and formatting
2. Frontmatter format (YAML/TOML/JSON)
3. Template-specific formatting
4. Obsidian compatibility

## Decision

**We will generate markdown files with YAML frontmatter and template-specific formatting.**

Structure:
```markdown
---
template: template-name
podcast: Podcast Name
episode: Episode Title
date: 2025-11-07
url: https://...
extracted_with: gemini
cost_usd: 0.01
tags:
  - podcast
  - inkwell
  - quotes
---

# Content Heading

Content formatted according to template type...
```

## Rationale

### Why YAML Frontmatter?

**Alternatives considered:**
1. TOML frontmatter
2. JSON frontmatter
3. No frontmatter (content only)
4. Custom format

**Decision: YAML frontmatter**

**Pros:**
- ✅ Standard in Obsidian, Jekyll, Hugo
- ✅ Human-readable
- ✅ Supports lists and nested data
- ✅ Most markdown tools support it
- ✅ Easy to parse with PyYAML

**Cons:**
- ❌ Whitespace-sensitive (minor)

**Verdict:** YAML is the de facto standard for markdown frontmatter.

### Frontmatter Fields

**Essential fields:**
- `template`: Template name (for filtering/organization)
- `podcast`: Podcast name (for grouping)
- `episode`: Episode title (for identification)
- `date`: Generation date (for sorting)

**Optional fields:**
- `url`: Episode URL (for reference)
- `extracted_with`: Provider used (cache/gemini/claude)
- `cost_usd`: Extraction cost (for tracking)
- `tags`: Obsidian-style tags (for categorization)

### Template-Specific Formatting

Different content types need different formatting:

**Quotes:**
```markdown
# Quotes

## Quote 1

> The actual quote text

**Speaker:** John Doe
**Timestamp:** 12:34
```

**Why blockquotes?** Standard markdown convention for quotes.

**Concepts:**
```markdown
# Key Concepts

## Concept Name

Explanation of the concept

**Context:** Where it was discussed
```

**Tools/Books:**
```markdown
# Tools & Technologies

| Tool | Category | Context |
|------|----------|---------|
| Python | language | Backend |
```

**Why tables?** Structured data is clearer in table format.

**Summary:**
```markdown
# Summary

Summary text in markdown format...

## Key Takeaways

- Point 1
- Point 2
```

### Obsidian Compatibility

**Tags format:**
- `tags: [podcast, inkwell, quotes]` - YAML array format
- Works in Obsidian tag pane
- Clickable tags in preview

**Wikilinks:**
- Could add: `[[Podcast Name]]` linking
- Decision: NOT implemented (user can add manually)
- Rationale: Don't want to assume user's vault structure

**Backlinks:**
- Episode files naturally backlink via filename
- Works automatically in Obsidian

## Implementation

### MarkdownGenerator Class

```python
class MarkdownGenerator:
    def generate(self, result: ExtractionResult, metadata: dict) -> str:
        """Generate markdown from extraction result."""
        parts = []

        # Frontmatter
        frontmatter = self._generate_frontmatter(result, metadata)
        parts.append(frontmatter)

        # Content
        content = self._format_content(result)
        parts.append(content)

        return "\n\n".join(parts)
```

### Format Dispatch

```python
def _format_content(self, result: ExtractionResult) -> str:
    content = result.content

    if content.format == "json":
        return self._format_json_content(result.template_name, content)
    elif content.format == "markdown":
        return content.data["text"]  # Pass-through
    elif content.format == "yaml":
        return self._format_yaml_content(content)
    else:  # text
        return content.data["text"]
```

### Template-Specific Formatters

Each known template type has a custom formatter:
- `_format_quotes()` - Blockquotes with metadata
- `_format_concepts()` - Headings with explanations
- `_format_tools()` - Markdown table
- `_format_books()` - List with details
- `_format_generic_json()` - JSON code block (fallback)

## Usage

### Basic Generation

```python
generator = MarkdownGenerator()

result = ExtractionResult(
    template_name="summary",
    content=ExtractedContent(...),
    cost_usd=0.01,
    provider="gemini"
)

markdown = generator.generate(result, episode_metadata)
```

### Without Frontmatter

```python
markdown = generator.generate(
    result,
    episode_metadata,
    include_frontmatter=False
)
```

Use case: Concatenating multiple outputs into single file.

## Examples

### Example 1: Quote Extraction

```markdown
---
template: quotes
podcast: The Test Podcast
episode: Episode 42
date: 2025-11-07
url: https://example.com/ep42
extracted_with: claude
cost_usd: 0.12
tags:
  - podcast
  - inkwell
  - quotes
---

# Quotes

## Quote 1

> Focus is the key to productivity

**Speaker:** Cal Newport
**Timestamp:** 15:30

## Quote 2

> Deep work matters in a distracted world

**Speaker:** Cal Newport
**Timestamp:** 22:15
```

### Example 2: Summary

```markdown
---
template: summary
podcast: Tech Talk
episode: AI in 2024
date: 2025-11-07
extracted_with: gemini
cost_usd: 0.003
tags:
  - podcast
  - inkwell
  - summary
---

# Summary

This episode explores the current state of AI technology in 2024,
focusing on large language models, their capabilities, and limitations.

## Key Takeaways

- LLMs are powerful but not AGI
- Focus on practical applications
- Ethics remain important
```

### Example 3: Tools Table

```markdown
---
template: tools-mentioned
podcast: Dev Podcast
episode: Modern Stack
date: 2025-11-07
extracted_with: gemini
cost_usd: 0.002
tags:
  - podcast
  - inkwell
  - tools
---

# Tools & Technologies Mentioned

| Tool | Category | Context |
|------|----------|---------|
| Python | language | Backend development |
| React | framework | Frontend UI |
| Docker | platform | Containerization |
```

## Design Decisions

### Decision 1: Template Name in Frontmatter

**Decision:** Include `template: name` field

**Rationale:**
- Users can filter by template type
- Useful for bulk operations
- Clear provenance

### Decision 2: Provider and Cost in Frontmatter

**Decision:** Include `extracted_with` and `cost_usd`

**Rationale:**
- Transparency about extraction source
- Cost tracking
- Debug information (was it cached?)

**Trade-off:** Exposes implementation details, but users appreciate transparency.

### Decision 3: Separate Files per Template

**Decision:** Each template → separate markdown file

**Rationale:**
- ✅ Easier to navigate
- ✅ Better for Obsidian (one note per concept)
- ✅ Can link between files
- ❌ More files to manage

**Alternative:** Single file with all extractions
- Harder to navigate
- Obsidian works better with atomic notes

**Verdict:** Separate files is better UX.

### Decision 4: Markdown Pass-Through for Summary

**Decision:** If template outputs markdown, use it as-is

**Rationale:**
- LLM already formatted it well
- Don't want to impose structure
- Respect LLM's judgment

### Decision 5: Generic JSON Fallback

**Decision:** Unknown templates → JSON code block

**Rationale:**
- Safe default
- Preserves all data
- Users can see raw structure
- Better than error

## Consequences

### Positive

✅ Human-readable output
✅ Obsidian-compatible out of the box
✅ Searchable and linkable
✅ Template-specific formatting improves UX
✅ Frontmatter enables filtering and organization
✅ Easy to customize (extend formatters)

### Negative

❌ YAML frontmatter slightly increases file size
❌ Template-specific formatters need maintenance
❌ Not all tools support frontmatter (rare)

### Neutral

- Separate file per template (design choice)
- Blockquotes for quotes (standard convention)
- Tables for structured data (good for some tools, not all)

## Future Enhancements

### 1. Custom Formatters

Allow users to define custom formatters:

```python
generator.register_formatter("custom-template", custom_formatter_fn)
```

### 2. Wikilink Generation

Automatically add Obsidian wikilinks:

```markdown
Discussed in [[Episode 42]] from [[The Test Podcast]]
```

**Trade-off:** Assumes vault structure.

### 3. Dataview Integration

Add Dataview-compatible frontmatter:

```yaml
dataview:
  speakers: [John, Jane]
  topics: [AI, ML]
```

### 4. Export Formats

Support other formats:
- HTML export
- PDF generation
- JSON export

### 5. Template Inheritance

Share formatting between similar templates:

```python
class QuotesFormatter(BaseFormatter):
    def format(self, data):
        # Shared quote formatting
```

## Testing Strategy

**Unit tests:**
- Frontmatter generation
- Template-specific formatters
- Edge cases (empty data, missing fields)
- Unicode handling
- Full generation pipeline

**Manual testing:**
- Open in Obsidian
- Verify tag navigation
- Check search functionality
- Test wikilinks (if added)

## Related

- [Unit 6 Devlog](../devlog/2025-11-07-phase-3-unit-6-markdown-output.md) - Implementation details
- [Unit 2: Output Models](../devlog/2025-11-07-phase-3-unit-2-data-models.md) - EpisodeMetadata, OutputFile

---

## Revision History

- 2025-11-07: Initial ADR (Phase 3 Unit 6)
