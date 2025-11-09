# Research: Obsidian Integration Patterns

**Date**: 2025-11-09
**Researcher**: Phase 5 Unit 1
**Status**: Complete
**Related**: [ADR-026](../adr/026-obsidian-integration-architecture.md)

## Overview

This research document explores Obsidian's core features and best practices for integration, focusing on wikilinks, tags, Dataview plugin capabilities, and Graph View requirements. The goal is to inform our Phase 5 implementation of deep Obsidian integration for Inkwell's podcast note generation.

---

## 1. Wikilinks - Internal Linking System

### How Wikilinks Work

Obsidian uses **wikilinks** (double square brackets) as the primary internal linking mechanism:

```markdown
[[Note Name]]                    # Basic link
[[Note Name|Display Text]]       # Custom display text
[[Note Name#Heading]]            # Link to heading
[[Note Name#^block-id]]          # Link to specific block
```

### Key Features

#### 1. Autocomplete & Suggestions
- Type `[[` and Obsidian suggests existing notes
- Type `[[Note#` to see headings in that note
- Type `[[Note#^` to see block references

#### 2. Bidirectional Links
- Links automatically appear in both source and target notes
- Backlinks panel shows all notes linking to current note
- Creates automatic knowledge graph connections

#### 3. Unlinked Mentions
- Obsidian detects mentions of note names without explicit links
- Shows potential connections for manual linking
- Reduces over-linking fatigue

### Best Practices for Programmatic Wikilink Generation

#### ✅ DO:
1. **Use wikilinks for entities with potential reuse**
   - People: `[[Cal Newport]]`
   - Books: `[[Deep Work]]`
   - Tools: `[[Obsidian]]`
   - Concepts that appear across episodes: `[[Zone of Genius]]`

2. **Provide custom display text when helpful**
   - `[[Deep Work|Cal Newport's book on focus]]`
   - `[[Tim Ferriss|Tim]]` for readability in context

3. **Link to specific sections when relevant**
   - `[[Episode 287#Key Takeaways]]`
   - Enables precise cross-episode references

4. **Use consistent naming conventions**
   - Books: `[[Book - Deep Work]]` or `[[Deep Work]]`
   - People: `[[Person - Cal Newport]]` or `[[Cal Newport]]`
   - Tools: `[[Tool - Notion]]` or `[[Notion]]`
   - Consistency enables better graph connections

#### ❌ DON'T:
1. **Over-link common words**
   - Avoid linking every mention of "work", "time", "productivity"
   - Reserve links for specific references

2. **Create orphan links without context**
   - Every wikilink should have purpose
   - Consider: will user click this link?

3. **Use markdown links when wikilinks are appropriate**
   - Wikilinks work better within Obsidian ecosystem
   - Markdown links break backlinks and graph

### Wikilinks vs. Markdown Links

| Feature | Wikilinks `[[]]` | Markdown Links `[]()` |
|---------|------------------|----------------------|
| Autocomplete | ✅ Yes | ❌ No |
| Backlinks | ✅ Yes | ❌ No |
| Graph View | ✅ Yes | ❌ No |
| Rename support | ✅ Yes | ❌ No |
| Plugin support | ✅ Excellent | ⚠️ Limited |
| Portability | ⚠️ Obsidian-specific | ✅ Universal |
| File paths | ✅ Automatic | ❌ Manual |

**Recommendation for Inkwell:** Use wikilinks exclusively for Obsidian integration. Users who need portability can use community plugins to convert wikilinks to markdown links.

---

## 2. Tag System - Organization & Categorization

### Tag Syntax

Obsidian supports three tag formats:

```markdown
#tag                             # Inline tag
#parent/child                    # Nested/hierarchical tag
#parent/child/grandchild         # Multi-level hierarchy

---
tags: [tag1, tag2, parent/child] # YAML frontmatter
---
```

### Hierarchical Tag Structure

Tags with forward slashes (`/`) create logical hierarchies:

```markdown
#podcast/deep-questions
#podcast/huberman-lab
#topic/ai
#topic/productivity
#topic/ai/machine-learning
#topic/ai/llm
#person/cal-newport
#person/andrew-huberman
```

### Tag Best Practices

#### ✅ Effective Tag Strategies:

1. **Use hierarchies for scalability**
   ```markdown
   #podcast/show-name              # Scales to many podcasts
   #topic/parent/child             # Enables filtering at any level
   #status/reviewed                # Action-based organization
   ```

2. **Balance specificity and utility**
   - Too broad: `#interesting` (meaningless)
   - Too narrow: `#episode-287-discussed-on-tuesday` (too specific)
   - Just right: `#topic/deep-work`, `#theme/focus-strategies`

3. **Use YAML frontmatter for metadata tags**
   ```yaml
   ---
   tags:
     - podcast/deep-questions
     - topic/productivity
     - person/cal-newport
     - status/reviewed
   ---
   ```
   Benefits: Cleaner markdown, easier to edit, Dataview-friendly

4. **Create tag naming conventions**
   - Lowercase only: `#ai` not `#AI`
   - Hyphens for multi-word: `#deep-work` not `#deep_work` or `#deepwork`
   - Namespace prefixes: `#podcast/`, `#topic/`, `#person/`

#### ❌ Tag Anti-Patterns:

1. **Over-tagging**
   - Don't tag every possible concept
   - More tags = more cognitive load
   - Focus on 3-7 meaningful tags per note

2. **Inconsistent naming**
   - `#AI`, `#ai`, `#artificial-intelligence` all different
   - Pick one convention and stick to it

3. **Meaningless tags**
   - `#important`, `#todo`, `#interesting` without context
   - Use more specific tags

### Tag Wrangler Plugin

**Key capabilities:**
- Visual tag hierarchy browser
- Rename tags across vault
- Merge duplicate tags
- Navigate tag relationships

**Recommendation:** Essential for managing large tag systems programmatically.

---

## 3. Dataview Plugin - Querying Metadata

### What is Dataview?

Dataview treats your Obsidian vault as a **queryable database**, enabling SQL-like queries over markdown files and their metadata.

**Repository:** https://github.com/blacksmithgu/obsidian-dataview
**Adoption:** One of the most popular Obsidian plugins (~1M downloads)

### Metadata Sources

Dataview can query:

1. **YAML Frontmatter** (explicit metadata)
   ```yaml
   ---
   type: podcast-note
   podcast: Deep Questions
   episode: 287
   date: 2025-11-09
   duration: 3600
   rating: 5
   actionable: true
   ---
   ```

2. **Inline Fields** (within content)
   ```markdown
   Rating:: 5
   Status:: reviewed
   ```

3. **Implicit Fields** (automatically available)
   - `file.name` - File name
   - `file.path` - File path
   - `file.link` - File as link
   - `file.size` - File size
   - `file.ctime` - Creation time
   - `file.mtime` - Modified time
   - `file.tags` - All tags
   - `file.inlinks` - Backlinks
   - `file.outlinks` - Outgoing links

### Query Language

#### LIST Query
```dataview
LIST
FROM #podcast
WHERE rating >= 4
SORT date DESC
```

#### TABLE Query
```dataview
TABLE podcast, episode, duration, rating
FROM #podcast
WHERE date >= date(2025-01-01)
SORT rating DESC, date DESC
```

#### TASK Query
```dataview
TASK
FROM #podcast
WHERE !completed
```

#### CALENDAR Query
```dataview
CALENDAR date
FROM #podcast
```

### Frontmatter Best Practices for Dataview

#### ✅ Dataview-Friendly Design:

1. **Use consistent field names**
   ```yaml
   # Good - consistent across all notes
   podcast: Deep Questions
   episode: 287
   date: 2025-11-09

   # Bad - inconsistent
   show: Deep Questions  # sometimes "podcast", sometimes "show"
   ep: 287              # sometimes "episode", sometimes "ep"
   ```

2. **Use appropriate data types**
   ```yaml
   # Dates
   date: 2025-11-09                    # YYYY-MM-DD format

   # Numbers
   duration: 3600                      # Integer (seconds)
   rating: 5                           # Integer (1-5)
   cost_total: 0.45                    # Float

   # Booleans
   actionable: true                    # Boolean
   interview_conducted: false          # Boolean

   # Lists
   topics: [ai, productivity, focus]   # List

   # Links
   guest: [[Cal Newport]]              # Wikilink in frontmatter
   ```

3. **Create queryable categories**
   ```yaml
   type: podcast-note                  # Enables: WHERE type = "podcast-note"
   status: reviewed                    # Enables: WHERE status = "reviewed"
   ```

4. **Add custom calculation fields**
   ```yaml
   word_count: 8543                    # For tracking note length
   action_items: 3                     # For tracking actionable insights
   cost_transcription: 0.003           # For cost breakdowns
   cost_extraction: 0.015
   cost_interview: 0.15
   cost_total: 0.168
   ```

### Example Dataview Queries for Inkwell

#### Most Expensive Episodes
```dataview
TABLE podcast, episode, cost_total
FROM #podcast
SORT cost_total DESC
LIMIT 10
```

#### Actionable Episodes Not Yet Reviewed
```dataview
LIST
FROM #podcast
WHERE actionable = true AND status != "reviewed"
```

#### Episodes by Podcast, Grouped
```dataview
TABLE episode, date, duration
FROM #podcast
GROUP BY podcast
SORT podcast ASC, date DESC
```

#### Interview Completion Rate
```dataview
TABLE
  length(rows) AS "Total Episodes",
  length(filter(rows, (r) => r.interview_conducted = true)) AS "Interviewed",
  round(length(filter(rows, (r) => r.interview_conducted = true)) / length(rows) * 100) + "%" AS "Rate"
FROM #podcast
GROUP BY podcast
```

#### Episodes with High Ratings
```dataview
TABLE file.link AS Episode, rating, date
FROM #podcast
WHERE rating >= 4
SORT date DESC
```

### Multi-Value Fields & Complex Queries

#### Nested Frontmatter
```yaml
---
speakers:
  - name: Cal Newport
    role: host
  - name: Jesse
    role: producer
---
```

Query nested fields:
```dataview
TABLE speakers.name
FROM #podcast
FLATTEN speakers AS speaker
WHERE speaker.role = "host"
```

#### List Containment
```yaml
---
topics: [ai, productivity, deep-work]
---
```

Query lists:
```dataview
LIST
FROM #podcast
WHERE contains(topics, "ai")
```

---

## 4. Graph View - Visual Knowledge Networks

### How Graph View Works

Obsidian's **Graph View** visualizes your vault as a network:
- **Nodes** = Notes
- **Edges** = Links (wikilinks only)
- Color coding by tags, folders, or custom rules
- Zoom, pan, filter capabilities

### Requirements for Good Graph Visualization

#### 1. Meaningful Links
- Links should represent genuine relationships
- Avoid linking every mention (creates noise)
- Focus on cross-references that add value

#### 2. Consistent Note Structure
- Similar notes (e.g., all podcast episodes) should link consistently
- Creates recognizable patterns in graph

#### 3. Hub Notes
- Central index notes that link to many related notes
- Example: `[[Podcast - Deep Questions - Index]]` links to all episodes
- Creates clear visual hierarchy

### Inkwell Graph View Strategy

#### Episode-to-Episode Linking
```markdown
## Related Episodes

This episode builds on ideas from:
- [[Episode 285 - On Deep Work]]
- [[Episode 280 - Managing Attention]]

See also discussions of similar themes in:
- [[Episode 250 - Zone of Genius]]
```

#### Topic-Based Clustering
```markdown
## Key Topics

This episode covered:
- [[Topic - Artificial Intelligence]]
- [[Topic - Productivity Systems]]
- [[Topic - Knowledge Management]]
```

#### Entity Linking
```markdown
## People Mentioned

- [[Cal Newport]] (host)
- [[Andrew Huberman]] (referenced)
- [[Tim Ferriss]] (mentioned book)

## Books Discussed

- [[Book - Deep Work]]
- [[Book - Slow Productivity]]
```

**Result:** Creates visual clusters in Graph View:
- All episodes cluster around their podcast
- Episodes discussing similar topics cluster together
- Entity nodes (people, books) connect episodes across podcasts

---

## 5. Popular Obsidian Plugins for Consideration

### Templater
**Purpose:** Advanced template system with JavaScript support
**Relevance:** Could inspire our own template system enhancements

### Dataview (covered above)
**Purpose:** Query engine for vault
**Relevance:** Primary reason for our frontmatter design

### Tag Wrangler
**Purpose:** Tag management and refactoring
**Relevance:** Users will need this for large tag systems

### Excalidraw
**Purpose:** Diagrams and sketches
**Relevance:** Not directly relevant, but popular for visual thinkers

### Tasks
**Purpose:** Task management with checkboxes
**Relevance:** Could enhance our action items from interviews

### Calendar
**Purpose:** Calendar view of daily notes
**Relevance:** Could visualize podcast listening timeline

---

## 6. Key Findings & Recommendations

### Findings

1. **Wikilinks are essential**
   - Core to Obsidian's value proposition
   - Enable backlinks, graph view, and navigation
   - Must use `[[]]` format, not markdown links

2. **Hierarchical tags scale better**
   - Flat tags become overwhelming at scale
   - Use namespace prefixes: `#podcast/`, `#topic/`, `#person/`
   - YAML frontmatter preferred over inline tags

3. **Dataview demands consistent frontmatter**
   - Field names must be consistent across notes
   - Data types matter (dates, booleans, numbers)
   - Lists and nested structures are supported

4. **Graph View requires intentional linking**
   - Too many links = noise
   - Too few links = isolation
   - Focus on meaningful cross-references

### Recommendations for Inkwell

#### Wikilinks
- ✅ Auto-generate wikilinks for: people, books, tools, concepts
- ✅ Use consistent naming: prefer simple `[[Name]]` over prefixes
- ✅ Link cross-episode references
- ✅ Provide custom display text when context demands

#### Tags
- ✅ Use hierarchical structure: `#podcast/show-name`
- ✅ Limit to 5-7 tags per note
- ✅ Store in YAML frontmatter, not inline
- ✅ Support custom tag rules per podcast feed

#### Dataview
- ✅ Design frontmatter schema for queryability
- ✅ Include: type, podcast, episode, date, duration, rating, status
- ✅ Add cost fields for tracking
- ✅ Use appropriate data types

#### Graph View
- ✅ Link episodes to topics, people, books
- ✅ Create episode-to-episode references
- ✅ Consider hub notes for each podcast

---

## 7. Implementation Priority

### High Priority (Must Have)
1. **Wikilink generation** for entities
2. **Hierarchical tags** in frontmatter
3. **Dataview-compatible frontmatter** with consistent fields

### Medium Priority (Should Have)
4. Cross-episode references
5. Custom display text for wikilinks
6. Topic and concept linking

### Low Priority (Nice to Have)
7. Hub note generation
8. Advanced graph view optimization
9. Plugin-specific enhancements

---

## 8. References

- [Obsidian Help - Internal Links](https://help.obsidian.md/links)
- [Obsidian Help - Tags](https://help.obsidian.md/tags)
- [Dataview Plugin Documentation](https://blacksmithgu.github.io/obsidian-dataview/)
- [Obsidian Forum - Nested Tags Discussion](https://forum.obsidian.md/t/nested-tags/169)
- [AWS Builders Library - Backoff with Jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)

---

## Next Steps

1. Design Obsidian integration architecture (see ADR-026)
2. Implement wikilink extraction system (Phase 5 Unit 3)
3. Implement tag generation system (Phase 5 Unit 4)
4. Implement Dataview frontmatter (Phase 5 Unit 5)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-09
**Status:** Complete
