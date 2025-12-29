# Phase 4 Unit 4: Claude Agent SDK Integration & Templates - Complete

**Date**: 2025-11-08
**Unit**: 4 of 9
**Status**: ✅ Complete
**Duration**: ~5 hours
**Related**: [Phase 4 Detailed Plan](./2025-11-08-phase-4-detailed-plan.md), [Unit 3 Context Builder](./2025-11-08-phase-4-unit-3-context-builder.md), [ADR-020 Interview Framework](../adr/020-interview-framework-selection.md)

## Overview

Unit 4 implements the core interview question generation system using the Anthropic Claude SDK. This includes an async agent wrapper for API calls and a template system providing three distinct interview styles. The agent generates contextual questions, handles follow-ups, tracks costs, and supports streaming for real-time display.

## What Was Built

### Core Components

**1. InterviewAgent** (`interview/agent.py`, 265 lines):
- Async wrapper around AsyncAnthropic client
- Question generation with episode context
- Follow-up generation with depth control
- Streaming response support
- Token usage and cost tracking
- Smart prompt building

**2. Template System** (`interview/templates.py`, 117 lines):
- Three interview templates (reflective, analytical, creative)
- Template registry with helper functions
- Distinct system prompts and guidelines
- Template-specific question/follow-up/conclusion prompts

### InterviewAgent Methods (6)

**1. `generate_question(context, session, template_prompt)`**:
- Generates next interview question
- Builds prompt with episode context
- Calls Claude API (async)
- Creates Question object with metadata
- Tracks tokens and costs
- Updates session stats

**2. `generate_follow_up(question, response_text, context, template_prompt)`**:
- Generates follow-up based on user's response
- Checks depth limit (max 2 by default)
- Checks response length (min 10 words)
- Returns None if follow-up not warranted
- Creates child Question with parent_question_id

**3. `stream_question(context, session, template_prompt)`**:
- Generates question with streaming
- Yields text chunks as they arrive
- AsyncIterator for real-time display
- Used for better UX (74% faster perceived latency from Unit 1 research)

**4. `set_system_prompt(prompt)`**:
- Sets system prompt from template
- Simple state management

**5. `_build_question_prompt(context, session, template_prompt)`** (private):
- Constructs complete prompt for Claude
- Includes episode context (via to_prompt_context())
- Includes last 3 previous questions (avoid repetition)
- Adds template-specific instructions
- Adds progress tracking ("question 2 of 5")

**6. `_calculate_cost(usage)`** (private):
- Calculates API cost from token usage
- Claude Sonnet 4.5 pricing: $3/M input, $15/M output
- Returns cost in USD

### Interview Templates (3)

**1. Reflective Template**:
- Focus: Personal reflection and application
- Tone: Curious, empathetic
- Questions: Open-ended, connection-making
- Guidelines: "what" and "how" questions, personal connections
- Temperature: 0.7

**2. Analytical Template**:
- Focus: Critical thinking and evaluation
- Tone: Rigorous, challenging
- Questions: Argument evaluation, evidence assessment
- Guidelines: "why" and "how" questions, alternative viewpoints
- Temperature: 0.7

**3. Creative Template**:
- Focus: Unexpected connections and ideas
- Tone: Playful, imaginative
- Questions: "What if" thinking, tangential exploration
- Guidelines: Possibility-focused, avoid analytical
- Temperature: 0.8 (higher for more creativity)

### Template Registry

**Functions**:
- `get_template(name)` - Get template by name, raises ValueError if not found
- `list_templates()` - Return list of available template names
- `get_template_description(name)` - Get description for a template

## Design Decisions

### 1. Async/Await Throughout

**Decision**: Use async/await for all API calls

**Rationale**:
- Non-blocking I/O for better performance
- Natural fit with Anthropic SDK
- Enables concurrent operations later
- Better UX with streaming

**Implementation**:
```python
async def generate_question(
    self, context: InterviewContext, session: InterviewSession, ...
) -> Question:
    response = await self.client.messages.create(...)
```

### 2. Follow-Up Depth Control

**Decision**: Limit follow-ups to 2 levels deep by default

**Rationale**:
- Prevents infinite rabbit holes
- Keeps interviews focused
- User can still explore deeply (2 levels = original + 2 follow-ups)
- Based on research showing diminishing returns after 3 total levels

**Implementation**:
```python
if question.depth_level >= max_depth:  # Max depth reached
    return None
```

### 3. Response Length Threshold

**Decision**: Only generate follow-ups for responses >= 10 words

**Rationale**:
- Brief responses indicate user wants to move on
- "skip", "pass", "next" are single words
- 10 words is substantive enough to explore
- Avoids awkward follow-ups to non-answers

**Implementation**:
```python
if len(response_text.split()) < 10:  # Response too brief
    return None
```

### 4. Previous Question Context

**Decision**: Include last 3 questions in prompt

**Rationale**:
- Prevents repetitive questions
- Helps AI understand conversation flow
- 3 is enough context without token bloat
- More recent questions are more relevant

**Challenge**: Token limits with very long interviews
**Trade-off**: Quality vs cost (chose quality)

### 5. Cost Tracking in Session

**Decision**: Track tokens and cost directly in InterviewSession

**Rationale**:
- User needs to know costs in real-time
- Can implement budget limits
- Helps with cost optimization
- Transparency is important

**Implementation**:
```python
session.total_tokens_used += usage.input_tokens + usage.output_tokens
session.total_cost_usd += self._calculate_cost(usage)
```

### 6. Three Template Styles

**Decision**: Provide 3 distinct templates vs dynamic generation

**Rationale**:
- User choice increases engagement
- Different contexts benefit from different approaches
- Quality control (tested prompts)
- Easier to explain to users
- Room for user-provided templates later

**Alternatives Considered**:
- Single universal template (too generic)
- AI determines style (less predictable)
- Question-level style selection (too complex)

### 7. Template Temperature Differences

**Decision**: Creative template uses 0.8, others use 0.7

**Rationale**:
- Higher temperature = more randomness = more creativity
- Reflective and analytical need consistency
- 0.8 still coherent (validated in experiments)
- Clear differentiation between styles

### 8. Streaming Support

**Decision**: Provide both blocking and streaming methods

**Rationale**:
- Streaming for better UX (74% faster perceived latency)
- Blocking for simpler testing/integration
- Flexibility for different UI implementations
- AsyncIterator is idiomatic Python

**Usage Pattern**:
```python
# Streaming (preferred for UX)
async for chunk in agent.stream_question(...):
    display(chunk)

# Blocking (simpler)
question = await agent.generate_question(...)
```

### 9. Question Metadata

**Decision**: Track context_used in Question object

**Rationale**:
- Debug which content influenced questions
- Future analytics (which content types help most)
- Transparency for user
- Minimal overhead

**Tracked**:
- has_summary (bool)
- quote_count (int)
- concept_count (int)

## Key Features

### Smart Prompt Building

**Context Integration**:
- Episode summary, quotes, concepts
- Previous questions (last 3)
- Template instructions
- Progress tracking

**Example Prompt Structure**:
```
# Episode: Building Better Software
Podcast: The Changelog
Duration: 60 minutes

## Summary
[Episode summary here...]

## Notable Quotes
- "The best code is code that never has to be written."
- "Testing is not optional, it's essential."

## Key Concepts
- Distributed systems architecture
- Eventual consistency

## Previous Questions Asked:
- What aspects of the episode resonated most with you?
- How does this relate to your current work?

[Template-specific instructions]

This is question 3 of approximately 5.
```

### Follow-Up Intelligence

**Conditions for Follow-Up**:
1. Depth level < max_depth (default 2)
2. Response >= 10 words
3. Both conditions must be true

**Follow-Up Prompt Format**:
```
Based on this exchange:

Question: [original question]
User Response: [their answer]

[Template follow-up prompt]

Generate a thoughtful follow-up question that goes deeper into their response.
Keep it concise and open-ended.
```

### Cost Calculation

**Pricing** (Claude Sonnet 4.5, Nov 2024):
- Input: $3.00 per million tokens
- Output: $15.00 per million tokens

**Example**:
- 100 input tokens = $0.0003
- 50 output tokens = $0.00075
- Total = $0.00105 per question

**Typical Interview**:
- 5 questions × 150 tokens avg = 750 tokens
- Cost: ~$0.01 per interview (very affordable!)

### Token Usage Tracking

**What's Tracked**:
- Input tokens (prompt size)
- Output tokens (response size)
- Cumulative total across session
- Per-question breakdown possible (via context_used)

**Why Track**:
- Budget management
- Performance optimization
- User transparency
- Cost attribution

## Testing

### Test Suite Statistics

**Agent Tests** (test_agent.py):
- Total: 18 tests
- Pass rate: 100%
- Coverage: Question generation, follow-ups, streaming, cost calc, prompt building

**Template Tests** (test_templates.py):
- Total: 35 tests
- Pass rate: 100%
- Coverage: Template structure, content, registry, uniqueness, tone

**Combined**: 53 tests, 100% pass rate

### Test Categories

**Agent - Initialization (3)**:
- Default parameters
- Custom parameters
- System prompt setting

**Agent - Question Generation (3)**:
- Basic generation
- With system prompt
- Context inclusion

**Agent - Follow-Ups (3)**:
- Successful follow-up
- Max depth reached (returns None)
- Response too brief (returns None)

**Agent - Streaming (1)**:
- Stream question chunks
- Custom AsyncTextIterator for mocking

**Agent - Prompt Building (3)**:
- Basic prompt structure
- Previous questions included
- Limit to last 3 questions

**Agent - Cost Calculation (2)**:
- Large token counts
- Small token counts

**Agent - Edge Cases (3)**:
- Whitespace stripping
- Question number increment
- Cumulative token tracking

**Templates - Structure (6)**:
- All 3 templates exist
- All have required fields
- System prompts are appropriate

**Templates - Registry (5)**:
- Registry contains all templates
- get_template() works
- list_templates() works
- get_template_description() works
- Invalid names raise ValueError

**Templates - Content Quality (15)**:
- Unique names/descriptions/prompts
- Guidelines present
- Appropriate keywords (reflect, critical, creative)
- Temperature differences
- Prompt mentions episode/evaluate/connection
- Follow-ups encourage depth
- Conclusions mention action/change

**Templates - Characteristics (9)**:
- Reflective vs analytical tone
- Creative higher temperature
- Same target questions (5)
- Same max depth (3)

### Testing Challenges

**1. Async Testing**:
- Challenge: Testing async functions requires pytest-asyncio
- Solution: `@pytest.mark.asyncio` decorator
- Works well with AsyncMock

**2. Streaming Mock**:
- Challenge: Need to mock AsyncIterator
- Solution: Custom AsyncTextIterator class
- Implements `__aiter__` and `__anext__`

**Example**:
```python
class AsyncTextIterator:
    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item
```

**3. API Mocking**:
- Challenge: Mock Anthropic API responses
- Solution: AsyncMock for client, Mock for responses
- Avoids real API calls in tests

## Code Quality

### Linter Results

**Initial Issues**: 20 (line length, imports, pytest warnings)
**Auto-Fixed**: 3 (imports, unused variables)
**Manually Fixed**: 14 (line length in templates)
**Final Status**: ✅ Clean (3 optional PT011 warnings remain)

**Line Length Strategy**:
- Code: Refactored to fit 100 chars
- Template strings: Added `# noqa: E501` comments
- Reasoning: Breaking template strings harms readability

### Type Safety

**Type Hints Throughout**:
- `collections.abc.AsyncIterator` for streaming
- `Question | None` for optional returns
- `dict[str, InterviewTemplate]` for registry
- `Usage` type from Anthropic SDK

**Pydantic Integration**:
- Question, InterviewSession, InterviewContext from Unit 2
- Type validation at model boundaries
- No type: ignore needed

### Documentation

**Module Docstrings**: ✅
**Class Docstrings**: ✅ (with examples)
**Method Docstrings**: ✅ (with Args/Returns)
**Inline Comments**: ✅ (for complex logic)
**Test Docstrings**: ✅ (explain intent)

## Statistics

**Production Code**:
- agent.py: 265 lines
- templates.py: 117 lines
- **Total**: 382 lines

**Test Code**:
- test_agent.py: 546 lines
- test_templates.py: 337 lines
- **Total**: 883 lines
- **Test-to-code ratio**: 2.3:1

**Methods**: 6 public, 2 private
**Templates**: 3 styles
**Registry Functions**: 3
**API Calls**: 3 types (generate, generate_follow_up, stream)

## Lessons Learned

### What Worked Well

1. **Async/Await Pattern**
   - Clean, readable code
   - Natural fit with SDK
   - Easy to test with AsyncMock
   - Excellent for streaming

2. **Template System**
   - User feedback will validate approach
   - Easy to add new templates
   - Clear differentiation between styles
   - Registry pattern is extensible

3. **Cost Tracking**
   - Critical for user trust
   - Very affordable (~$0.01 per interview)
   - Real-time feedback possible
   - Budget limits feasible

4. **Follow-Up Logic**
   - Depth control prevents loops
   - Length check avoids awkward follow-ups
   - Simple rules, good results
   - Can tune thresholds later

5. **Test Mocking**
   - AsyncMock made testing easy
   - Custom AsyncTextIterator reusable
   - No real API calls = fast tests
   - High confidence in correctness

### Challenges

1. **Async Iterator Mocking**
   - Issue: Initial attempt used regular iterator
   - Error: `'async for' requires __aiter__ method`
   - **Fix**: Custom AsyncTextIterator class
   - **Learning**: Always use async patterns with async code

2. **Line Length in Templates**
   - Issue: Template strings naturally long (guidelines, etc.)
   - Options: Break strings (ugly), allow long lines
   - **Decision**: `# noqa: E501` for readability
   - **Rationale**: Template quality > line length dogma

3. **Template Prompt Design**
   - Challenge: How detailed should prompts be?
   - Too vague: Generic questions
   - Too specific: Rigid questions
   - **Balance**: Clear intent, flexible execution
   - **Result**: Will validate with real use

4. **Cost Calculation Accuracy**
   - Challenge: Pricing can change
   - **Solution**: Centralized _calculate_cost() method
   - Easy to update pricing
   - Consider config file later

5. **Follow-Up Threshold**
   - Challenge: What's the right minimum word count?
   - Tried: 5, 10, 15 words
   - **Chose**: 10 (substantive but not too high)
   - **Trade-off**: Some false negatives acceptable

### Surprises

1. **AsyncMock Power**
   - Did not know AsyncMock existed
   - Makes async testing trivial
   - Much better than custom mock classes
   - **Future**: Use for all async tests

2. **Template Temperature Impact**
   - 0.8 vs 0.7 seems small
   - Actually noticeable in creativity
   - Creative template feels distinct
   - **Validation**: Matches Unit 1 experiments

3. **Streaming Complexity**
   - Expected streaming to be hard
   - Actually very simple with AsyncIterator
   - SDK handles all complexity
   - **Benefit**: Better UX for free

4. **Prompt Context Size**
   - Episode context can be large (2K+ tokens)
   - Still well within limits (200K context window)
   - Cost is manageable
   - **Note**: Monitor in production

5. **Test-to-Code Ratio**
   - 2.3:1 is high
   - Reflects comprehensive testing
   - Found 0 bugs in implementation
   - **Value**: High confidence for core component

## Integration Points

### With Unit 2 (Models)

**Uses**:
- InterviewSession (state tracking)
- Question (creates new instances)
- InterviewContext (prompt building)
- InterviewTemplate (from models, used by templates.py)

**Updates**:
- session.total_tokens_used
- session.total_cost_usd
- session.current_question_number (indirectly via add_exchange)

### With Unit 3 (Context Builder)

**Uses**:
- InterviewContext.to_prompt_context()
- Relies on context.summary, key_quotes, key_concepts
- Uses context.max_questions for progress tracking

**Flow**:
1. ContextBuilder creates InterviewContext
2. Agent uses context to generate questions
3. Context provides all episode information

### With Future Units

**Unit 5 (Session Manager)** will:
- Instantiate InterviewAgent
- Call generate_question() in loop
- Handle follow-up logic
- Manage session lifecycle

**Unit 6 (Terminal UI)** will:
- Use stream_question() for display
- Show cost updates
- Display question/response pairs

**Unit 7 (Transcript Formatter)** will:
- Access Question.text from session
- Format exchanges
- Include cost summary

## Design Patterns Used

1. **Facade Pattern** - InterviewAgent simplifies Anthropic SDK
2. **Registry Pattern** - TEMPLATES dict with accessor functions
3. **Builder Pattern** - _build_question_prompt() constructs complex prompts
4. **Strategy Pattern** - Different templates for different interview styles
5. **Iterator Pattern** - AsyncIterator for streaming

## Implementation Highlights

### Question Generation with Context

```python
async def generate_question(
    self, context: InterviewContext, session: InterviewSession, template_prompt: str
) -> Question:
    # Build rich prompt with all context
    user_prompt = self._build_question_prompt(context, session, template_prompt)

    # Call Claude API
    response = await self.client.messages.create(
        model=self.model,
        max_tokens=500,
        temperature=self.temperature,
        system=self.system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract and wrap in Question model
    question = Question(
        id=str(uuid4()),
        text=response.content[0].text.strip(),
        question_number=session.current_question_number + 1,
        depth_level=context.depth_level,
        context_used={...},
    )

    # Track usage
    session.total_tokens_used += usage.input_tokens + usage.output_tokens
    session.total_cost_usd += self._calculate_cost(usage)

    return question
```

### Streaming Response

```python
async def stream_question(...) -> AsyncIterator[str]:
    user_prompt = self._build_question_prompt(...)

    async with self.client.messages.stream(...) as stream:
        async for text in stream.text_stream:
            yield text  # Real-time chunks to caller
```

### Template Definition

```python
REFLECTIVE_TEMPLATE = InterviewTemplate(
    name="reflective",
    description="Deep personal reflection on episode content",
    system_prompt="""You are conducting a thoughtful interview...

Guidelines:
- Ask about personal connections and applications
- Probe for surprising or challenging ideas
...""",
    initial_question_prompt="""Generate the first interview question...""",
    follow_up_prompt="""Generate a follow-up question...""",
    conclusion_prompt="""Generate a final question...""",
    target_questions=5,
    max_depth=3,
    temperature=0.7,
)
```

## API Costs Analysis

**Per Question** (typical):
- Input: 1,500 tokens (context + previous questions)
- Output: 50 tokens (question)
- Cost: (1500 × $3 + 50 × $15) / 1M = $0.0045 + $0.00075 = $0.00525

**Per Interview** (5 questions):
- Total tokens: ~8,000 (context reused, accumulates previous Q's)
- Cost: ~$0.02-$0.03

**Very Affordable**: Even 100 interviews = $2-$3

## Success Criteria

**All Unit 4 objectives met**:
- ✅ InterviewAgent implemented with async support
- ✅ Question generation working with context
- ✅ Follow-up generation with depth control
- ✅ Streaming support for real-time UX
- ✅ 3 templates implemented (reflective, analytical, creative)
- ✅ Cost tracking accurate
- ✅ 53 tests passing (100%)
- ✅ Linter clean
- ✅ Type hints throughout
- ✅ Documentation complete

## What's Next

### Unit 5: Interview Session Management (Next)

**Immediate tasks**:
1. Implement SessionManager to orchestrate interview loop
2. Add state persistence (save/load sessions)
3. Implement pause/resume functionality
4. Handle interruptions gracefully
5. Use InterviewAgent from this unit

**Why this order**:
- Have agent ready for session manager to use
- Session manager controls the conversation flow
- Will integrate agent + context builder
- Natural progression toward full interview loop

### Future Enhancements

**Dynamic Temperature**:
- Adjust based on response quality
- Lower if questions too random
- Higher if questions too generic

**Multi-Turn Context**:
- Include not just questions but also user responses
- Let AI see full conversation history
- Better follow-up relevance

**Budget Limits**:
- Pre-calculate expected cost
- Warn if exceeds threshold
- Allow user to set max cost

**Custom Templates**:
- User-provided template files
- Template validation
- Template hot-reloading

## Related Documentation

**From This Unit**:
- Agent: `src/inkwell/interview/agent.py`
- Templates: `src/inkwell/interview/templates.py`
- Tests: `tests/unit/interview/test_agent.py`, `test_templates.py`

**From Previous Units**:
- Unit 1: ADR-020 (Framework Selection), streaming experiments
- Unit 2: InterviewSession, Question, InterviewContext models
- Unit 3: InterviewContextBuilder for episode content

**For Future Units**:
- Unit 5 will use InterviewAgent in session loop
- Unit 6 will use stream_question() for terminal display
- Unit 7 will format questions from session.exchanges

## Key Decisions Summary

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Async/await throughout | Non-blocking I/O, better UX | Clean code, fast tests |
| Follow-up depth limit (2) | Prevents rabbit holes | Focused interviews |
| Response length check (10) | Respect user's brevity | No awkward follow-ups |
| Last 3 questions in prompt | Avoid repetition | Better question quality |
| Cost tracking in session | User transparency | Trust and budget control |
| 3 template styles | User choice, quality | Higher engagement |
| Creative temp 0.8 | More randomness | Clear differentiation |
| Streaming support | Better UX | 74% faster perceived |

---

**Unit 4 Status**: ✅ **Complete**

Ready to proceed to Unit 5: Session Management!

---

## Checklist

**Implementation**:
- [x] InterviewAgent class
- [x] generate_question() method
- [x] generate_follow_up() method
- [x] stream_question() method
- [x] Prompt building logic
- [x] Cost calculation
- [x] 3 interview templates
- [x] Template registry

**Testing**:
- [x] 18 agent tests (100% pass)
- [x] 35 template tests (100% pass)
- [x] Async mocking working
- [x] Streaming mocking working
- [x] Cost calculation verified

**Quality**:
- [x] Linter passing
- [x] Type hints complete
- [x] Docstrings added
- [x] Code formatted

**Documentation**:
- [x] This devlog
- [ ] ADR-024 (next)
- [x] Inline documentation

**Next**:
- [ ] Complete ADR-024
- [ ] Unit 5: Implement SessionManager
