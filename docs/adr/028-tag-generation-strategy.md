# ADR-028: Tag Generation Strategy

**Status**: Accepted
**Date**: 2025-11-10
**Context**: Phase 5 Unit 4 - Smart Tag Generation
**Deciders**: Development Team
**Related**: [ADR-026](./026-obsidian-integration-architecture.md)

## Context

Obsidian supports tags for organizing and filtering notes. For podcast notes to be discoverable and well-organized, we need an automated tag generation system that creates relevant, consistent tags without overwhelming users.

**Requirements:**
1. Generate tags from multiple sources (metadata, entities, content analysis)
2. Support hierarchical tags (#podcast/name, #topic/ai)
3. Normalize tags to Obsidian-compatible format
4. Balance comprehensiveness with usability (limit quantity)
5. Use cost-effective LLM for content analysis
6. Allow user configuration (max tags, confidence thresholds)

**Constraints:**
- Gemini API costs $0.003/1K tokens (vs Claude $0.015/1K)
- Obsidian tag rules: lowercase, no spaces, alphanumeric + hyphens
- Too many tags overwhelm users; too few reduce discoverability
- Must work without LLM (degraded mode)

## Decision

We will implement a **three-source hybrid tag generation system** with Gemini-powered content analysis:

### 1. Tag Sources (Priority Order)

**Source 1: Metadata Tags (confidence = 1.0)**
- Always included: `#podcast`, `#inkwell`
- Podcast name: `#podcast/lex-fridman`
- Source: Always available, no cost

**Source 2: Entity Tags (confidence = entity.confidence)**
- Derived from WikilinkGenerator entities
- Map entity types to tag categories:
  - Person → `#person/cal-newport`
  - Book → `#book/deep-work`
  - Tool → `#tool/obsidian`
  - Concept → `#concept/flow-state`
- Filter: Only entities with confidence ≥ 0.8
- Source: Already extracted, no additional cost

**Source 3: LLM Content Analysis Tags (confidence = LLM-provided)**
- Use Gemini Flash for cost efficiency ($0.003/1K tokens)
- Analyze summary + key concepts + transcript excerpt
- Suggest 3-5 tags for:
  - Topics (e.g., `#topic/ai`, `#topic/productivity`)
  - Themes (e.g., `#theme/focus`, `#theme/leadership`)
  - Industry (e.g., `#industry/tech`, `#industry/healthcare`)
- Source: ~$0.001-0.002 per episode
- Fallback: Gracefully disable if API unavailable

### 2. Tag Normalization Rules

Convert all tags to Obsidian-compatible format:

**Rules:**
```python
# 1. Lowercase
"Deep Work" → "deep work"

# 2. Replace spaces with hyphens
"deep work" → "deep-work"

# 3. Remove special characters (except hyphens, underscores)
"AI & ML!" → "ai-ml"

# 4. Collapse multiple hyphens
"deep---work" → "deep-work"

# 5. Remove leading/trailing hyphens
"-deep-work-" → "deep-work"
```

**Result**: `"Deep Work"` → `"deep-work"`

### 3. Hierarchical Tag Structure

Support two styles (user-configurable):

**Hierarchical (default):**
```
#podcast/lex-fridman
#topic/ai
#person/cal-newport
#book/deep-work
#tool/obsidian
#theme/productivity
#industry/tech
```

**Flat (optional):**
```
#lex-fridman
#ai
#cal-newport
#deep-work
#obsidian
#productivity
#tech
```

**Benefits of hierarchical:**
- Better organization in large vaults
- Namespace isolation (avoid collisions)
- Queryable hierarchies in Dataview

### 4. Quality Control Pipeline

**Pipeline:**
```
Raw Tags → Normalize → Deduplicate → Filter → Limit → Sort
```

**Steps:**
1. **Normalize**: Apply tag normalization rules
2. **Deduplicate**: Remove case-insensitive duplicates
3. **Filter**: Remove tags below confidence threshold (default 0.6)
4. **Limit**: Keep top N by confidence (default 7)
5. **Sort**: Order by confidence (descending)

**Configuration:**
```yaml
obsidian:
  tags_enabled: true
  tag_style: hierarchical
  max_tags: 7
  min_tag_confidence: 0.6
  include_entity_tags: true
  include_llm_tags: true
```

### 5. LLM Prompt Design

**Prompt structure:**
```
Analyze this podcast episode and suggest relevant tags.

Context:
- Podcast: Lex Fridman Podcast
- Episode: Cal Newport on Deep Work
- Summary: [first 500 chars]
- Key Concepts: [top 5 concepts]
- Transcript: [first 1000 chars]

Suggest 3-5 tags that capture:
1. Main topics (e.g., ai, productivity)
2. Themes (e.g., focus, leadership)
3. Industry (e.g., tech, business)

Requirements:
- Lowercase, hyphens for spaces
- Be specific but not too narrow
- Avoid redundancy (don't suggest podcast name)

Respond with JSON:
{
  "tags": [
    {"name": "ai", "category": "topic", "confidence": 0.9},
    {"name": "productivity", "category": "theme", "confidence": 0.8}
  ]
}
```

**Parsing:**
- Extract JSON from response
- Map category strings to TagCategory enum
- Create Tag objects with confidence scores
- Gracefully handle malformed JSON

## Alternatives Considered

### Alternative 1: Claude for Content Analysis

**Approach:** Use Claude Sonnet for tag suggestions

**Pros:**
- Higher quality analysis
- Better reasoning about themes

**Cons:**
- 5x more expensive ($0.015 vs $0.003)
- Slower API response times
- Not cost-effective for tag generation

**Decision:** Rejected - Cost difference not justified for tag suggestions

### Alternative 2: Rule-Based Only (No LLM)

**Approach:** Generate tags only from metadata and entities

**Pros:**
- Zero additional API cost
- Deterministic, predictable
- Fast

**Cons:**
- Misses thematic tags (productivity, leadership, etc.)
- Less discovery of cross-cutting topics
- Requires extensive rule maintenance

**Decision:** Rejected as primary strategy, but supported as fallback

### Alternative 3: TF-IDF/Keyword Extraction

**Approach:** Use statistical methods to extract keywords

**Pros:**
- No API cost
- Fast

**Cons:**
- Misses semantic meaning
- Poor at identifying themes
- Requires extensive tuning

**Decision:** Rejected - LLM provides better semantic understanding

### Alternative 4: Global Tag Limit (Not Per-Source)

**Approach:** Limit total tags to 7, regardless of source

**Pros:**
- Simpler logic
- Strict quantity control

**Cons:**
- Metadata tags (podcast, inkwell) consume limit
- LLM tags might crowd out entity tags
- Less balanced representation

**Decision:** Rejected - Per-source limits provide better balance

**Chosen Approach:** Three-source hybrid with Gemini, per-source filtering

## Implementation Details

### Data Models

```python
# Tag representation
class Tag(BaseModel):
    name: str  # Normalized
    category: TagCategory | None
    confidence: float
    source: Literal["llm", "entity", "manual"]
    raw_name: str  # Original before normalization

# Tag categories
class TagCategory(Enum):
    PODCAST = "podcast"
    TOPIC = "topic"
    PERSON = "person"
    CONCEPT = "concept"
    TOOL = "tool"
    BOOK = "book"
    THEME = "theme"
    INDUSTRY = "industry"
    CUSTOM = "custom"

# Configuration
class TagConfig(BaseModel):
    enabled: bool = True
    style: TagStyle = TagStyle.HIERARCHICAL
    max_tags: int = 7
    min_confidence: float = 0.6
    include_entity_tags: bool = True
    include_llm_tags: bool = True
```

### TagGenerator API

```python
class TagGenerator:
    def generate_tags(
        self,
        entities: list[Entity],
        transcript: str,
        metadata: dict,
        extraction_results: dict | None = None,
    ) -> list[Tag]:
        """Generate tags from all sources."""

    def format_tags(self, tags: list[Tag]) -> list[str]:
        """Format as Obsidian tags: ['#topic/ai', '#person/cal-newport']"""

    def format_frontmatter_tags(self, tags: list[Tag]) -> list[str]:
        """Format for YAML: ['topic/ai', 'person/cal-newport']"""
```

## Consequences

### Positive

1. **Multi-Source Richness**: Combines deterministic (metadata, entities) with semantic (LLM) tags
2. **Cost-Effective**: Gemini keeps costs low (~$0.001-0.002 per episode)
3. **Graceful Degradation**: Works without LLM (entity + metadata tags only)
4. **User Control**: Configurable limits and thresholds
5. **Obsidian-Compatible**: Normalized format works everywhere
6. **Hierarchical Organization**: Scales to large vaults
7. **Quality Control**: Confidence filtering prevents noise

### Negative

1. **LLM Dependency**: Best experience requires Gemini API access
2. **API Latency**: LLM adds ~1-2 seconds to episode processing
3. **Prompt Maintenance**: LLM prompt may need tuning for quality
4. **Category Mapping**: LLM category strings must map to enum
5. **Normalization Edge Cases**: Complex names may lose clarity

### Neutral

1. **Default Limit (7 tags)**: May need adjustment based on user feedback
2. **Confidence Threshold (0.6)**: Conservative default, users may want higher
3. **Hierarchical Default**: Some users may prefer flat tags

## Validation

### Test Coverage

**Unit Tests (28 tests):**
- Tag normalization (6 tests)
- Tag formatting (4 tests)
- Entity tag generation (3 tests)
- LLM response parsing (3 tests)
- Quality control pipeline (5 tests)
- Integration (7 tests)

**Success Criteria:**
- ✅ All tests passing (28/28)
- ✅ Tag normalization handles edge cases
- ✅ LLM failures don't crash system
- ✅ Hierarchical and flat styles both work
- ✅ Confidence filtering removes low-quality tags

### Cost Analysis

**Per Episode:**
- Metadata tags: $0.000 (3 tags)
- Entity tags: $0.000 (reuse WikilinkGenerator)
- LLM tags: $0.001-0.002 (Gemini Flash)
- **Total: ~$0.002 per episode**

**100 Episodes:** ~$0.20 for tag generation

**Comparison:**
- Claude Sonnet: ~$1.00 for 100 episodes (5x more)
- Rule-based: $0.00 but lower quality

## Future Enhancements

### 1. Tag Learning from User Edits

**Concept:** Learn from user tag modifications
- Track which LLM-suggested tags users keep/remove
- Adjust confidence scoring based on feedback
- Build user-specific tag preferences

**Implementation:** Post-v1.0

### 2. Cross-Episode Tag Consistency

**Concept:** Maintain consistent tags across episodes
- Tag database with canonical forms
- Alias resolution ("Cal Newport" vs "Dr. Newport")
- Tag suggestion from previous episodes

**Implementation:** Post-v1.0

### 3. Custom Tag Categories

**Concept:** User-defined tag categories
```yaml
custom_tag_categories:
  - name: "guest"
    pattern: "#guest/{name}"
  - name: "series"
    pattern: "#series/{name}"
```

**Implementation:** Post-v1.0

### 4. Multi-Level Hierarchies

**Concept:** Deeper tag hierarchies
```
#podcast/lex-fridman/episode-123
#topic/ai/machine-learning/deep-learning
```

**Implementation:** Consider for v2.0

## References

- [Obsidian Tag Documentation](https://help.obsidian.md/Editing+and+formatting/Tags)
- [ADR-026: Obsidian Integration Architecture](./026-obsidian-integration-architecture.md)
- [Gemini API Pricing](https://ai.google.dev/pricing)
- Research: `docs/research/obsidian-integration-patterns.md`

## Revision History

- **2025-11-10**: Initial version - Three-source hybrid with Gemini
