# ADR-025: Interview Transcript Output Format

**Status**: Accepted
**Date**: 2025-11-08
**Deciders**: Development Team
**Related**: [ADR-020 Interview Framework Selection](./020-interview-framework-selection.md), [Unit 7 Devlog](../devlog/2025-11-08-phase-4-unit-7-transcript-formatting.md)

## Context

Interview mode creates conversational transcripts from user responses to questions. These transcripts need to be:

1. **Readable** - Easy to scan and understand
2. **Referenceable** - Quick to find specific exchanges
3. **Actionable** - Extract insights and next steps
4. **Flexible** - Support different user preferences
5. **Obsidian-compatible** - Work with users' existing note systems

We need to decide on the output format, structure, and what additional content to extract beyond the raw transcript.

## Decision

We will provide **three transcript styles with automatic insight/action extraction**.

**Core Approach**:
1. Three format styles: structured, narrative, Q&A
2. Extract key insights using pattern matching
3. Extract action items from responses
4. Identify recurring themes
5. Save as markdown with frontmatter metadata
6. Include session statistics

**Format Styles**:

**Structured** (default):
- Clear section headers (## Conversation, ## Session Statistics)
- Numbered questions with bold formatting
- Separate Q&A blocks
- Metadata section with episode info
- Professional, scannable

**Narrative**:
- Flowing prose format
- Questions in italics
- Responses as paragraphs
- Introduction and closing
- Conversational feel

**Q&A**:
- Simple question/answer pairs
- Minimal formatting
- Maximum density
- Easy copy-paste

**Automatic Extraction**:

**Insights** - Pattern-based detection:
- "I realize...", "I've realized...", "I learned..."
- "This made me think...", "I hadn't considered..."
- "What struck me...", "The connection is..."

**Action Items** - Pattern-based detection:
- "I should...", "I'll...", "I want to..."
- "I need to...", "I plan to...", "I'm going to..."
- Cleaned (capitalized, leading conjunctions removed)
- Presented as checkboxes `- [ ]`

**Themes** - Repetition detection:
- 2-3 word phrases appearing 2+ times
- Filter out stop words
- Capitalized for display

**Output Structure**:
```markdown
# Interview Notes: {episode_title}

---
**Podcast**: {podcast_name}
**Episode**: {episode_title}
**Interview Date**: {date}
**Template**: {template_name}
**Questions**: {count}
**Duration**: {minutes}
---

## Conversation

### Question 1
**Q**: {question_text}
**A**: {response_text}

...

## Session Statistics
- Questions asked: {count}
- Substantive responses: {count}
- Total time: {minutes}
- Tokens used: {tokens}
- Cost: ${cost}

## Key Insights
- {insight_1}
- {insight_2}

## Action Items
- [ ] {action_1}
- [ ] {action_2}

## Recurring Themes
- {theme_1}
- {theme_2}
```

## Alternatives Considered

### 1. Single Fixed Format

**Approach**: Provide only one transcript format (e.g., structured).

**Pros**:
- Simpler implementation
- No format selection needed
- Consistent output
- Easier to maintain

**Cons**:
- **Doesn't suit all use cases** - Some want narrative, others want minimal
- **Rigid** - Can't adapt to user preference
- **Limits adoption** - Some users won't use it
- **No experimentation** - Can't learn what users prefer

**Why Rejected**: User preferences vary significantly. Some users want scannable structure, others want flowing narrative. Providing choice increases adoption.

### 2. LLM-Based Extraction

**Approach**: Use Claude to extract insights, actions, themes by analyzing the full transcript.

**Example**:
```python
async def extract_insights(transcript: str) -> list[str]:
    prompt = f"Extract key insights from this interview:\n\n{transcript}"
    response = await claude.messages.create(...)
    return parse_insights(response.text)
```

**Pros**:
- Higher quality extraction
- Better understanding of context
- Can identify subtle insights
- More flexible than patterns

**Cons**:
- **Additional API cost** - 3 more API calls per interview
- **Slower** - Each extraction adds latency
- **Less reliable** - LLM might miss or hallucinate
- **Not deterministic** - Different results each time
- **Overkill** - Pattern matching works well enough

**Why Rejected**: Pattern-based extraction is fast, free, and reliable. The quality difference doesn't justify the cost/latency trade-off. Users can always re-analyze transcripts later with LLMs if needed.

### 3. No Automatic Extraction

**Approach**: Just format the transcript, let users extract insights manually.

**Pros**:
- Simpler implementation
- No pattern matching complexity
- Users have full control
- Zero false positives

**Cons**:
- **Less value-add** - Just a formatter
- **More work for users** - Have to manually scan
- **Insights lost** - Easy to forget to extract
- **Reduced adoption** - Less compelling feature

**Why Rejected**: Automatic extraction provides significant value with minimal risk. Even imperfect extraction helps users by highlighting potential insights they can then refine.

### 4. Structured Data Format (JSON/YAML)

**Approach**: Save transcripts as JSON or YAML instead of markdown.

**Example**:
```json
{
  "episode_title": "...",
  "exchanges": [
    {"question": "...", "response": "..."}
  ],
  "insights": [...],
  "actions": [...]
}
```

**Pros**:
- Machine-readable
- Easy to query
- Structured schema
- Can build tools on top

**Cons**:
- **Not human-readable** - Can't scan in editor
- **Breaks Obsidian flow** - Most users use markdown
- **Extra conversion step** - Need to render to read
- **Niche use case** - Most users want readable notes

**Why Rejected**: The primary use case is note-taking, not data processing. Markdown is the lingua franca of personal knowledge management. Users can export to JSON later if needed (we already save session JSON).

### 5. AI-Generated Summaries

**Approach**: Have Claude write a summary paragraph for each interview.

**Pros**:
- Quick overview
- Professional prose
- Captures essence
- Good for sharing

**Cons**:
- **Additional API cost**
- **Loses specifics** - Summaries are lossy
- **Not what users said** - Paraphrasing can change meaning
- **Takes control from user** - They lose their voice

**Why Rejected**: We want to preserve the user's actual words and thoughts. Summaries can be generated later if needed, but we can't reconstruct original responses from a summary.

## Consequences

### Positive

**User Flexibility**:
- Users can choose format that fits their workflow
- Structured for scanning, narrative for reading, Q&A for brevity
- Supports diverse note-taking styles

**Automatic Value-Add**:
- Insights surfaced without extra work
- Action items extracted and formatted as checkboxes
- Themes help identify patterns
- Users can ignore extractions if not useful

**Obsidian Integration**:
- Markdown format works natively
- Can be imported into vaults
- Compatible with existing workflows
- Links can be added by users

**Low Cost**:
- No additional API calls
- Pattern matching is instant
- No quality degradation from LLM extraction
- Deterministic results

**Extensibility**:
- Easy to add more format styles
- Can add more extraction patterns
- Can add LLM-based extraction as optional later
- Format is malleable

### Negative

**Pattern Matching Limitations**:
- May miss insights that don't follow patterns
- Can have false positives (phrases that aren't insights)
- Language-dependent (English only currently)
- Requires maintenance as patterns evolve

**Format Choice Complexity**:
- Users have to choose format (but reasonable default)
- Three implementations to maintain
- More testing surface area
- Documentation overhead

**No Deep Analysis**:
- Doesn't synthesize across exchanges
- Doesn't identify contradictions
- Doesn't provide meta-insights
- Surface-level extraction only

### Mitigation Strategies

**For Pattern Limitations**:
- Provide clear examples of what gets extracted
- Allow users to manually add/remove items
- Keep patterns simple and obvious
- Consider adding LLM extraction as opt-in premium feature

**For Format Complexity**:
- Make structured the clear default
- Show examples of each format
- Allow format switching post-interview
- Document when to use each style

**For Deep Analysis**:
- Document that this is intentional
- Explain that users can use LLMs on transcripts later
- Consider separate analysis command in future
- Focus on preserving user's raw thoughts

## Implementation Notes

**Extraction Patterns**:
- Use `re.compile()` for performance
- Case-insensitive matching
- Sentence-level extraction (split on `.!?`)
- Minimum length check (20 chars for insights, 15 for actions)

**Deduplication**:
- Lowercase comparison
- Keep first occurrence
- Simple set-based approach
- No fuzzy matching (too complex)

**Themes**:
- Count 2-3 word phrases
- Require 2+ occurrences
- Filter stop words
- Title case for display
- Top 8 max

**File Naming**:
- Default: `my-notes.md`
- Customizable via parameter
- Saved in episode output directory
- Alongside other extracted content

## Related Decisions

**ADR-020**: Chose Claude Agent SDK for interview framework
**ADR-021**: Session persistence strategy enables transcript generation
**ADR-022**: Rich library provides terminal UI for conducting interviews
**ADR-024**: Question generation strategy provides content to format

## References

- [Unit 7 Devlog](../devlog/2025-11-08-phase-4-unit-7-transcript-formatting.md) - Implementation details
- [formatter.py](../../src/inkwell/interview/formatter.py) - Implementation
- [test_formatter.py](../../tests/unit/interview/test_formatter.py) - Tests demonstrating behavior

## Future Considerations

**LLM-Based Extraction (Optional)**:
- Add `--ai-extract` flag for premium extraction
- Higher quality but slower and costs tokens
- Opt-in for users who want it

**Custom Extraction Patterns**:
- User-defined regex patterns
- Per-user vocabulary (e.g., domain-specific terms)
- Configuration file support

**Multi-Format Export**:
- Export to PDF
- Export to HTML
- Export to Notion/Roam format
- Maintain markdown as canonical

**Theme Evolution**:
- Track themes across multiple interviews
- Show how themes develop over time
- Meta-analysis of interview patterns

**Insight Refinement**:
- Let users mark false positives
- Learn from corrections
- Improve patterns over time
- Optional LLM refinement
