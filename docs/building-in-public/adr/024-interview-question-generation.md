# ADR-024: Interview Question Generation Strategy

**Status**: Accepted
**Date**: 2025-11-08
**Deciders**: Development Team
**Related**: [ADR-020 Interview Framework Selection](./020-interview-framework-selection.md), [Unit 4 Devlog](../devlog/2025-11-08-phase-4-unit-4-agent-integration.md)

## Context

The interview mode needs to generate thoughtful, contextual questions that help users reflect on podcast episodes. Questions must be:

1. **Relevant** - Based on actual episode content
2. **Personalized** - Adapt to user's responses
3. **Diverse** - Avoid repetition across questions
4. **Engaging** - Encourage deep reflection
5. **Controllable** - Predictable quality and style

We need to decide how to generate these questions: fully dynamic, scripted, template-based, or hybrid.

## Decision

We will use **template-based question generation with rich episode context**.

**Core Approach**:
1. Provide 3 interview templates (reflective, analytical, creative)
2. Each template has distinct system prompt and guidelines
3. Questions generated dynamically using Claude API
4. Episode context (summary, quotes, concepts) included in prompts
5. Previous questions tracked to avoid repetition
6. Follow-ups generated based on user responses

**Template Structure**:
```python
class InterviewTemplate:
    name: str  # "reflective", "analytical", "creative"
    description: str
    system_prompt: str  # Sets agent behavior
    initial_question_prompt: str  # First question instructions
    follow_up_prompt: str  # Deeper exploration instructions
    conclusion_prompt: str  # Wrap-up instructions
    target_questions: int = 5
    max_depth: int = 3
    temperature: float = 0.7
```

**Question Generation Flow**:
1. Load template by name
2. Set agent system prompt
3. Build context from episode (summary + quotes + concepts)
4. Include previous questions (last 3)
5. Call Claude API with template prompt
6. Return generated question

## Alternatives Considered

### 1. Fully Dynamic Generation

**Approach**: Let Claude generate questions without any templates, purely based on episode content.

**Pros**:
- Maximum flexibility
- Adapts to any episode type
- No template maintenance
- Could discover novel question styles

**Cons**:
- **Unpredictable quality** - No quality control
- **Inconsistent style** - Each interview different
- **Hard to improve** - Can't iterate on prompts
- **Poor user expectation** - Users don't know what to expect
- **Difficult debugging** - Can't isolate prompt issues

**Why Rejected**: Quality and consistency are more important than flexibility. Users need to understand what each interview style provides.

### 2. Scripted Questions

**Approach**: Pre-write all questions, insert episode-specific content into placeholders.

**Example**:
```
"What did you find most surprising about [TOPIC]?"
"How does [MAIN_IDEA] relate to your work in [USER_FIELD]?"
```

**Pros**:
- Perfectly predictable
- Very fast (no API calls)
- Zero cost
- Easy to test

**Cons**:
- **Not contextual** - Questions may not fit episode
- **Feels robotic** - Users notice canned questions
- **Limited variety** - Finite question bank
- **High maintenance** - Need many variations
- **No adaptability** - Can't respond to user answers naturally

**Why Rejected**: The whole point of interview mode is intelligent, contextual questions. Scripted questions defeat the purpose.

### 3. Hybrid (Templates + Scripts)

**Approach**: Use templates for most questions, fall back to scripts for common cases.

**Example**:
- First question always: "What resonated most with you?"
- Middle questions: Generated with template
- Last question: Always about action items

**Pros**:
- Predictable start/end
- Dynamic middle
- Lower cost
- Controlled key moments

**Cons**:
- **Inconsistent experience** - Mixing styles confusing
- **Still limited** - Scripts lack context
- **Complex logic** - When to use which?
- **Harder testing** - Two systems to maintain

**Why Rejected**: Added complexity without clear benefit. Templates can handle all cases with appropriate prompts.

### 4. User-Provided Question Lists

**Approach**: Let users write their own question templates.

**Example**:
```yaml
questions:
  - "What was the main argument?"
  - "Do you agree or disagree?"
  - "What will you do differently?"
```

**Pros**:
- Ultimate control
- Personalized to user
- No API costs
- Fast

**Cons**:
- **High friction** - Users must write questions
- **Defeats purpose** - We're supposed to generate questions
- **Quality varies** - Users may write poor questions
- **No follow-ups** - Static list can't adapt

**Why Rejected**: This is essentially "DIY interview mode" which misses the point. Could be added later as power-user feature, but not the default.

### 5. Question-Level Style Selection

**Approach**: AI chooses which style (reflective/analytical/creative) for each question.

**Example**:
```
Q1: [AI chooses reflective] "What personal connections did you make?"
Q2: [AI chooses analytical] "What evidence supports the main claim?"
Q3: [AI chooses creative] "What if you applied this to a different domain?"
```

**Pros**:
- Best of all styles
- Optimized per question
- More variety
- Adaptive to episode

**Cons**:
- **Unpredictable** - User doesn't know what's coming
- **Inconsistent tone** - Jarring style switches
- **Complex prompting** - AI must meta-reason about style
- **Hard to debug** - Can't isolate style issues
- **No user preference** - User may prefer one style

**Why Rejected**: Users should choose interview style upfront. Mixing styles mid-interview is confusing. Can add "mixed" template later if needed.

## Rationale

**Why Template-Based**:

1. **Quality Control**
   - Prompts are testable and improvable
   - Can iterate based on feedback
   - Consistent behavior per template
   - Known failure modes

2. **User Choice**
   - Clear expectations per style
   - Users can try different approaches
   - Self-selection based on goals
   - Predictable experience

3. **Flexibility Within Structure**
   - Questions still dynamic (not scripted)
   - Adapt to episode content
   - Follow-ups respond to user
   - Context-aware generation

4. **Extensibility**
   - Easy to add new templates
   - Users could provide custom templates later
   - Template marketplace possible
   - A/B testing feasible

5. **Maintainability**
   - Clear separation of concerns
   - Templates are just data
   - Agent logic is generic
   - Easy to debug issues

**Why Three Templates**:

- **Reflective** - Most common use case (personal growth)
- **Analytical** - For critical thinkers
- **Creative** - For brainstormers and innovators
- Three is memorable, not overwhelming
- Covers major interview approaches
- Can add more based on usage

**Why Rich Context**:

- Episode summary provides overall themes
- Quotes give concrete discussion points
- Concepts suggest areas to explore
- Previous questions prevent repetition
- Together, create relevant questions

## Consequences

### Positive

1. **High Question Quality**
   - Relevant to episode content
   - Appropriate for chosen style
   - Contextual and personalized
   - Can be improved iteratively

2. **User Satisfaction**
   - Clear choices
   - Predictable experience
   - Feels intelligent, not robotic
   - Adapts to their responses

3. **Maintainability**
   - Templates are easy to edit
   - Can A/B test variations
   - User feedback directly actionable
   - Clear ownership of prompts

4. **Extensibility**
   - New templates easy to add
   - Custom templates possible
   - Third-party templates feasible
   - Template sharing/marketplace

### Negative

1. **Prompt Engineering Required**
   - Templates need careful design
   - Iteration based on real usage
   - Expertise to write good prompts
   - Ongoing refinement needed

2. **API Costs**
   - Every question costs money (~$0.005)
   - Need to track and optimize
   - Budget limits may be needed
   - Though still very affordable

3. **Latency**
   - Network round-trip per question
   - User waits for generation
   - Mitigated by streaming (74% faster perceived)
   - Still slower than scripts

4. **Limited Customization**
   - Only 3 styles initially
   - Users can't tweak templates (yet)
   - May not fit all use cases
   - Need user feedback to expand

### Neutral

1. **Template Maintenance**
   - Need to update as API evolves
   - Monitor for quality regressions
   - Track which templates used most
   - Collect user feedback per template

2. **Testing Complexity**
   - Must test with mocked API
   - Need diverse test cases
   - Template changes need retesting
   - Real-world validation important

## Implementation Notes

**Template Design Principles**:
1. Clear guidelines for AI behavior
2. Specific instructions for question types
3. Examples of good questions (in prompts)
4. Tone and style guidance
5. Constraints (question length, open-ended, etc.)

**Context Building**:
1. Include episode metadata (title, podcast, duration)
2. Summary for overall themes
3. Top 5 quotes for discussion points
4. Key concepts for exploration areas
5. Previous 3 questions to avoid repetition
6. Progress tracking ("question 2 of 5")

**Quality Metrics** (to track):
1. Question relevance (user feedback)
2. Response length (indicates engagement)
3. Follow-up rate (deeper exploration)
4. Interview completion rate
5. Template preference distribution

**Future Enhancements**:
1. User-provided custom templates
2. Template parameters (e.g., question count)
3. Dynamic style mixing (advanced mode)
4. Template marketplace/sharing
5. AI-suggested template improvements

## Related Decisions

- [ADR-020](./020-interview-framework-selection.md) - Why we use Anthropic SDK
- [ADR-021](./021-interview-state-persistence.md) - How we save session data
- [ADR-022](./022-interview-ui-framework.md) - Terminal UI for interviews
- [ADR-023](./023-interview-template-system.md) - Template-based approach rationale

## References

- Unit 1 Research: claude-agent-sdk-integration.md
- Unit 1 Research: interview-conversation-design.md
- Unit 1 Experiment: interview-question-quality.md (showed detailed prompts 2.2x better)
- Unit 4 Implementation: src/inkwell/interview/agent.py
- Unit 4 Implementation: src/inkwell/interview/templates.py

## Success Criteria

- ✅ Questions are relevant to episode content
- ✅ Three distinct template styles implemented
- ✅ Users can choose interview style
- ✅ Questions avoid repetition
- ✅ Follow-ups respond to user answers
- ✅ Cost per interview < $0.05
- ✅ Template prompts are maintainable
- ✅ System is extensible to new templates

## Review Schedule

**Next Review**: After 100 real interviews
**Review Criteria**:
- Question quality feedback
- Template usage distribution
- Completion rates per template
- User requests for new templates
- Cost per interview trending

**Potential Changes**:
- Add new templates based on usage
- Tune existing template prompts
- Adjust question count defaults
- Enable custom user templates
