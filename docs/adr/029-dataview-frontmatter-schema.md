# ADR-029: Dataview-Compatible Frontmatter Schema

**Status**: Accepted
**Date**: 2025-11-10
**Context**: Phase 5 Unit 5 - Dataview Integration
**Deciders**: Development Team
**Related**: [ADR-026](./026-obsidian-integration-architecture.md), [ADR-028](./028-tag-generation-strategy.md)

## Context

Obsidian's Dataview plugin enables powerful queries over note collections. To make podcast notes discoverable and analyzable, we need rich, queryable frontmatter that follows Dataview best practices and supports common use cases.

**Requirements:**
1. Support common queries (by podcast, by date, by topic, by rating)
2. Enable aggregation (total listening time, cost analysis, topic trends)
3. Follow Dataview field naming conventions
4. Support task management workflows (inbox/reading/completed)
5. Allow user customization and extensibility
6. Maintain backward compatibility with simple frontmatter

**User Scenarios:**
- "Show all episodes from Lex Fridman Podcast sorted by date"
- "Find high-rated episodes about AI"
- "Calculate total listening time by podcast"
- "Show unprocessed episodes in my inbox"
- "Find episodes featuring specific guests"

**Constraints:**
- YAML frontmatter size impacts file performance
- Too many fields overwhelm users
- Field names must be Dataview-compatible (no special chars)
- Date fields must use ISO format for sorting

## Decision

We will implement a **comprehensive, hierarchical frontmatter schema** with 20+ queryable fields organized into logical categories:

### 1. Field Categories

```yaml
---
# Core identification
template: summary
podcast: Lex Fridman Podcast
episode: Cal Newport on Deep Work
episode_number: 261

# Dates (ISO format for sorting)
created_date: 2025-11-10
episode_date: 2023-05-15
last_modified: 2025-11-10

# URLs
url: https://example.com/episode
podcast_url: https://example.com
audio_url: https://example.com/audio.mp3

# Media info
duration_minutes: 180
word_count: 25000

# People
host: Lex Fridman
guest: Cal Newport
people:
  - Cal Newport
  - Andrew Huberman

# Content categorization
tags:
  - podcast/lex-fridman
  - topic/ai
  - theme/productivity
topics:
  - ai
  - productivity

# Ratings & status
rating: 5  # 1-5 scale
status: inbox  # inbox | reading | completed | archived
priority: high  # low | medium | high

# Metadata
extracted_with: gemini
cost_usd: 0.0045

# Obsidian integration
has_wikilinks: true
has_interview: true
---
```

### 2. Field Specifications

#### Core Identification
- **template** (string): Template used for extraction (summary, quotes, concepts)
- **podcast** (string): Podcast name (normalized)
- **episode** (string): Episode title
- **episode_number** (int, optional): Episode number if available

**Rationale:** Essential for identification and grouping

#### Dates
- **created_date** (string, YYYY-MM-DD): When note was created
- **episode_date** (string, YYYY-MM-DD, optional): When episode was published
- **last_modified** (string, YYYY-MM-DD): Last modification date

**Rationale:** ISO format enables proper chronological sorting in Dataview

#### URLs
- **url** (string, optional): Episode URL
- **podcast_url** (string, optional): Podcast homepage
- **audio_url** (string, optional): Direct audio file URL

**Rationale:** Clickable links for reference

#### Media Info
- **duration_minutes** (int, optional): Episode duration in minutes
- **word_count** (int, optional): Transcript word count

**Rationale:** Enables time investment analysis

#### People
- **host** (string, optional): Podcast host name
- **guest** (string, optional): Guest name if applicable
- **people** (list[string]): All people mentioned (extracted from entities)

**Rationale:** Enables guest-based discovery and relationship tracking

#### Content Categorization
- **tags** (list[string]): Generated tags for categorization
- **topics** (list[string]): Extracted from tags (topic/ai → ai)

**Rationale:** Multi-level categorization for flexible queries

#### Ratings & Status
- **rating** (int, 1-5, optional): User rating (null = not yet rated)
- **status** (enum): Processing status
  - `inbox`: Just downloaded, not reviewed
  - `reading`: Currently reviewing
  - `completed`: Finished reviewing
  - `archived`: Reference only
- **priority** (enum): Priority level (low, medium, high)

**Rationale:** Supports task management workflows

#### Metadata
- **extracted_with** (string): Provider (gemini, claude, cache)
- **cost_usd** (float): Extraction cost in USD

**Rationale:** Transparency and cost tracking

#### Obsidian Integration
- **has_wikilinks** (bool): Contains wikilinks
- **has_interview** (bool): Interview mode used

**Rationale:** Indicates which Inkwell features were applied

### 3. Configuration

```python
class DataviewConfig(BaseModel):
    enabled: bool = True
    include_episode_number: bool = True
    include_duration: bool = True
    include_word_count: bool = True
    include_ratings: bool = True
    include_status: bool = True
    default_status: Literal["inbox", "reading", "completed", "archived"] = "inbox"
    default_priority: Literal["low", "medium", "high"] = "medium"
```

**User configuration:**
```yaml
# ~/.config/inkwell/config.yaml
obsidian:
  dataview_enabled: true
  include_episode_number: true
  include_duration: true
  include_word_count: true
  include_ratings: true
  include_status: true
  default_status: inbox
  default_priority: medium
```

### 4. Implementation

**Frontmatter Generation:**
```python
from inkwell.obsidian import create_frontmatter_dict, format_frontmatter_yaml

# Create frontmatter
frontmatter = create_frontmatter_dict(
    template_name="summary",
    episode_metadata=metadata,
    extraction_result=result,
    tags=generated_tags,
    entities=extracted_entities,
    interview_conducted=interview_used,
    config=dataview_config,
)

# Format as YAML
yaml_str = format_frontmatter_yaml(frontmatter)
```

**Markdown file:**
```markdown
---
template: summary
podcast: Lex Fridman Podcast
episode: Cal Newport on Deep Work
created_date: 2025-11-10
status: inbox
rating: null
---

# Summary

...
```

## Alternatives Considered

### Alternative 1: Minimal Frontmatter

**Approach:** Only include essential fields (template, podcast, episode)

**Pros:**
- Simpler
- Smaller file size
- Easier to understand

**Cons:**
- Limited query capabilities
- Can't track status or ratings
- No time investment analysis
- No people-based discovery

**Decision:** Rejected - Too limiting for power users

### Alternative 2: Flat Namespace

**Approach:** No field categories, all fields at root level

**Example:**
```yaml
template_name: summary  # vs template
podcast_name: Test      # vs podcast
episode_title: Test     # vs episode
```

**Pros:**
- No ambiguity about field names

**Cons:**
- Verbose field names
- Harder to read
- More typing in queries

**Decision:** Rejected - Readability matters

### Alternative 3: Custom Objects

**Approach:** Nest related fields in objects

**Example:**
```yaml
metadata:
  template: summary
  created_date: 2025-11-10
media:
  duration_minutes: 180
  word_count: 25000
```

**Pros:**
- Logical grouping
- Namespace isolation

**Cons:**
- Harder to query: `WHERE metadata.template = "summary"`
- Not Dataview convention
- More complex access paths

**Decision:** Rejected - Flat structure is Dataview best practice

### Alternative 4: All Fields Optional

**Approach:** Make every field optional, include only when available

**Pros:**
- Flexible
- Smaller frontmatter when data missing

**Cons:**
- Inconsistent frontmatter structure
- Harder to write reliable queries
- Users can't rely on field presence

**Decision:** Partially adopted - Optional fields clearly documented

### Alternative 5: User-Defined Schema

**Approach:** Let users define their own frontmatter schema

**Pros:**
- Maximum flexibility
- Users get exactly what they want

**Cons:**
- No standard queries
- Community fragmentation
- Higher complexity

**Decision:** Rejected for v1.0, but supported via `custom` field

## Implementation Details

### Field Name Conventions

**Rules:**
1. **Lowercase with underscores**: `episode_date` (not `episodeDate` or `episode-date`)
2. **Descriptive but concise**: `duration_minutes` (not `dur` or `episode_duration_in_minutes`)
3. **No special characters**: Compatible with Dataview access patterns
4. **Consistent naming**: `created_date`, `episode_date`, `last_modified` (all use same suffix)

**Rationale:**
- Dataview supports both `obj.field_name` and `obj["field_name"]`
- Underscores more readable than camelCase
- Consistency aids muscle memory

### Date Format

**Format:** ISO 8601 (YYYY-MM-DD)

**Example:**
```yaml
created_date: 2025-11-10
episode_date: 2023-05-15
```

**Rationale:**
- Sortable lexicographically
- Dataview date functions work natively
- International standard

**Queries:**
```dataview
WHERE date(episode_date) >= date(today) - dur(30 days)
```

### List Fields

**Format:** YAML lists

**Example:**
```yaml
tags:
  - podcast/lex-fridman
  - topic/ai
people:
  - Cal Newport
  - Andrew Huberman
```

**Queries:**
```dataview
WHERE contains(tags, "topic/ai")
WHERE contains(people, "Cal Newport")
```

### Enum Fields

**Status:**
- `inbox`: New, unprocessed
- `reading`: Currently reviewing
- `completed`: Finished
- `archived`: Reference only

**Priority:**
- `low`: Can wait
- `medium`: Normal priority
- `high`: Important

**Rationale:**
- Standardized values enable reliable filtering
- Limited choices reduce decision fatigue
- Clear semantic meaning

### Extensibility

**Custom fields:**
```yaml
custom:
  project: "AI Research"
  shared_with: ["Alice", "Bob"]
  action_items: 3
```

**Query:**
```dataview
WHERE custom.project = "AI Research"
```

**Rationale:**
- Supports power user workflows
- No schema changes needed
- Future-proof

## Consequences

### Positive

1. **Rich Queries**: 20+ fields enable complex discovery patterns
2. **Task Management**: Status/priority fields support GTD workflows
3. **Time Analysis**: Duration tracking enables listening time calculations
4. **Guest Discovery**: People fields enable relationship tracking
5. **Cost Transparency**: Cost tracking helps budget management
6. **Standardized**: All Inkwell users share same schema
7. **Well-Documented**: 27 example queries provided
8. **Configurable**: Users can disable optional fields

### Negative

1. **Frontmatter Size**: ~30 lines per file (manageable)
2. **Learning Curve**: Users need to understand available fields
3. **Maintenance**: Schema changes require migration
4. **Null Values**: Some fields often null (rating, guest)

### Neutral

1. **Opinionated**: Prescribes specific workflow (inbox/reading/completed)
2. **Field Count**: 20+ fields may feel overwhelming initially
3. **Vendor Lock-in**: Somewhat tied to Dataview

## Validation

### Test Coverage

**Unit Tests (23 tests):**
- DataviewFrontmatter model (5 tests)
- DataviewConfig (2 tests)
- create_frontmatter_dict (12 tests)
- format_frontmatter_yaml (4 tests)

**Success Criteria:**
- ✅ All tests passing (23/23)
- ✅ Rating validation (1-5 constraint)
- ✅ Status enum validation
- ✅ Priority enum validation
- ✅ People extraction from entities
- ✅ Topics extraction from tags
- ✅ YAML formatting preserves order
- ✅ Unicode support

### Example Queries

**Provided 27 example queries:**
1. List all episodes
2. Episodes by podcast
3. Recent episodes (last 30 days)
4. Episodes with ratings
5. Find by guest
6. Find by topic
7. Long episodes (>2 hours)
8. Episodes with specific tag
9. Episodes mentioning person
10. Episodes with interview notes
11. Episodes with wikilinks
12. Most expensive extractions
13. Episodes by provider
14. Total extraction cost
15. Word count statistics
16. Inbox: unprocessed
17. Currently reading
18. Completed episodes
19. High priority episodes
20. Unrated episodes
21. Episodes by podcast with stats
22. Topics matrix
23. Guest appearances
24. Listening time by podcast
25. Timeline over time
26. Personal dashboard
27. Topic explorer dashboard

### User Benefits

**Discovery:**
- Find episodes by topic, guest, podcast, date
- Filter by rating, status, priority
- Search across all metadata

**Analysis:**
- Total listening time per podcast
- Cost analysis (total, average, by provider)
- Topic trends over time
- Guest appearance frequency
- Word count statistics

**Workflow:**
- Inbox management (GTD-style)
- Priority-based filtering
- Progress tracking (reading → completed)
- Rating for future reference

## Future Enhancements

### 1. Automatic Status Transitions

**Concept:** Auto-advance status based on user actions
- Open note → `reading`
- Add rating → `completed`
- Tag archived → `archived`

**Implementation:** Post-v1.0 (requires Obsidian plugin)

### 2. Smart Defaults from History

**Concept:** Learn user patterns
- If user always rates 5, default to 5
- If user always marks completed, skip inbox

**Implementation:** Post-v1.0

### 3. Relationship Graph

**Concept:** Track relationships between episodes
```yaml
related_episodes:
  - "[[Episode 123 - Same Topic]]"
  - "[[Episode 456 - Same Guest]]"
```

**Implementation:** v2.0

### 4. Custom Field Templates

**Concept:** User-defined field sets
```yaml
# User template: "research"
custom_template: research
research:
  hypothesis: "..."
  findings: "..."
  citations: [...]
```

**Implementation:** v2.0

## References

- [Dataview Documentation](https://blacksmithgu.github.io/obsidian-dataview/)
- [Dataview Field Naming Best Practices](https://blacksmithgu.github.io/obsidian-dataview/annotation/add-metadata/)
- [ADR-026: Obsidian Integration Architecture](./026-obsidian-integration-architecture.md)
- Query Examples: `docs/dataview-queries.md`

## Revision History

- **2025-11-10**: Initial version - Comprehensive frontmatter schema
