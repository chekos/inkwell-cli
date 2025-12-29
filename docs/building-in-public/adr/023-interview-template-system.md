# ADR-023: Interview Template System

**Status**: Accepted
**Date**: 2025-11-08
**Deciders**: Development Team
**Related**: Phase 4 Unit 1, [Research: Interview Conversation Design](../research/interview-conversation-design.md)

## Context

Different users have different reflection styles and goals when processing podcast content. Some want deep personal reflection, others prefer critical analysis, and some enjoy creative exploration. We need a flexible system that allows users to choose interview styles that match their preferences and the episode content.

### Requirements

1. **Multiple Styles** - Support different interview approaches (reflective, analytical, creative)
2. **Easy Selection** - Simple config or CLI flag to choose style
3. **Customizable** - Users can create custom templates
4. **Consistent Quality** - All templates generate thoughtful, contextual questions
5. **Clear Differences** - Each style should feel distinct
6. **Extensible** - Easy to add new templates over time

### Interview Style Examples

**Reflective**: "How does this idea apply to your personal experience with X?"
**Analytical**: "What assumptions underlie this argument?"
**Creative**: "If you combined this concept with Y, what might emerge?"

## Decision

**Implement a template-based interview system** with three built-in styles (reflective, analytical, creative) using Pydantic models and system prompts.

### Implementation

```python
# interview/templates/base.py

from pydantic import BaseModel

class InterviewTemplate(BaseModel):
    """Template for interview style"""
    name: str
    description: str

    # System prompt defines interview character and approach
    system_prompt: str

    # Guidance for different question types
    initial_question_prompt: str
    follow_up_prompt: str
    conclusion_prompt: str

    # Interview parameters
    target_questions: int = 5
    max_depth: int = 3
    temperature: float = 0.7


# Reflective Template
REFLECTIVE_TEMPLATE = InterviewTemplate(
    name="reflective",
    description="Deep personal reflection on episode content",

    system_prompt="""You are conducting a thoughtful interview to help
the listener reflect deeply on a podcast episode. Your role is to ask
open-ended questions that encourage personal connection, introspection,
and actionable insights.

Guidelines:
- Ask about personal connections and applications
- Probe for surprising or challenging ideas
- Encourage connection-making to past experiences
- Focus on "what" and "how" rather than "why"
- Keep questions concise and open-ended
- Be curious and empathetic""",

    initial_question_prompt="""Generate the first interview question.
This should be an open-ended question that helps the listener reflect
on what resonated most with them from the episode. Draw from the
summary and key concepts provided.""",

    follow_up_prompt="""Generate a follow-up question that goes deeper
into their response. Build on what they said to explore their thinking
further.""",

    conclusion_prompt="""Generate a final question that helps the
listener identify concrete actions or next steps based on their
reflections.""",
)

# Analytical Template
ANALYTICAL_TEMPLATE = InterviewTemplate(
    name="analytical",
    description="Critical analysis and evaluation of episode arguments",

    system_prompt="""You are conducting an analytical interview to help
the listener critically examine the ideas presented in a podcast episode.
Your role is to ask questions that encourage critical thinking, argument
evaluation, and intellectual engagement.

Guidelines:
- Ask about logical consistency and evidence
- Probe assumptions and implications
- Encourage comparison with alternative viewpoints
- Focus on "why" and "how" questions
- Challenge thinking constructively
- Maintain intellectual rigor""",

    initial_question_prompt="""Generate the first interview question.
This should ask the listener to critically evaluate one of the main
arguments or claims from the episode.""",

    follow_up_prompt="""Generate a follow-up question that challenges
their analysis or asks them to consider alternative perspectives.""",

    conclusion_prompt="""Generate a final question that asks how this
critical analysis changes their view on the topic.""",
)

# Creative Template
CREATIVE_TEMPLATE = InterviewTemplate(
    name="creative",
    description="Creative connections and idea generation",

    system_prompt="""You are conducting a creative interview to help
the listener make unexpected connections and generate new ideas inspired
by the podcast episode. Your role is to ask questions that spark
creativity, imagination, and novel thinking.

Guidelines:
- Ask about unexpected connections
- Encourage "what if" thinking
- Explore tangential ideas and metaphors
- Focus on possibility and potential
- Be playful and imaginative
- Avoid being too analytical""",

    initial_question_prompt="""Generate the first interview question.
This should ask the listener to make an unexpected connection between
the episode content and something else in their life or work.""",

    follow_up_prompt="""Generate a follow-up question that pushes their
creative thinking further or explores an interesting tangent.""",

    conclusion_prompt="""Generate a final question that asks them to
imagine a creative application or project inspired by the episode.""",
)

# Template Registry
TEMPLATES = {
    "reflective": REFLECTIVE_TEMPLATE,
    "analytical": ANALYTICAL_TEMPLATE,
    "creative": CREATIVE_TEMPLATE,
}

def get_template(name: str) -> InterviewTemplate:
    """Get interview template by name"""
    if name not in TEMPLATES:
        raise ValueError(f"Unknown template: {name}. Choose from: {list(TEMPLATES.keys())}")
    return TEMPLATES[name]
```

### Usage

```bash
# Use default (reflective)
$ inkwell fetch "my-podcast" --latest --interview

# Specify template
$ inkwell fetch "my-podcast" --latest --interview --template analytical

# Configure default in config
$ inkwell config set interview.default_template creative
```

### Configuration

```yaml
# ~/.config/inkwell/config.yaml
interview:
  default_template: "reflective"  # reflective, analytical, creative
```

## Alternatives Considered

### Alternative 1: Single Interview Style

**Description**: One-size-fits-all interview approach

**Pros**:
- Simplest implementation
- No choice paralysis for users
- Easier to test and maintain
- One prompt to optimize

**Cons**:
- Can't adapt to different content types
- Doesn't match user preferences
- Less engaging over time
- Misses opportunity for personalization

**Why Rejected**: Different users have different thinking styles. A tech-focused analytical user would find reflective questions too touchy-feely, while a creative user might find analytical questions dry. Offering choice improves engagement.

### Alternative 2: AI-Determined Style

**Description**: LLM automatically selects interview style based on episode content and user history

**Pros**:
- No user decision needed
- Adapts to content automatically
- Could be "smarter"
- Feels personalized

**Cons**:
- Complex implementation (needs ML or heuristics)
- Users lose control
- Unpredictable (same episode different interview each time)
- Harder to debug
- Additional LLM call cost
- May pick wrong style

**Why Rejected**: Users should have control over their interview experience. Automatic selection removes agency and makes the system less predictable.

### Alternative 3: Question-by-Question Style Selection

**Description**: Let users choose style for each individual question

**Pros**:
- Maximum flexibility
- Can adapt mid-interview
- Very granular control

**Cons**:
- Interrupts flow (extra choice every question)
- Cognitively taxing for users
- Slow interview process
- Complicates conversation coherence
- Most users won't want this

**Why Rejected**: Too much friction. Interview should flow naturally without constant meta-decisions.

### Alternative 4: Complex Template Composition

**Description**: Templates can inherit from each other, compose, mix styles

**Pros**:
- Very flexible
- Could create hybrid styles
- DRY for template authors

**Cons**:
- Much more complex implementation
- Harder for users to understand
- Unclear which template is actually being used
- Testing complexity
- Over-engineering for v1

**Why Rejected**: YAGNI (You Aren't Gonna Need It). Three distinct templates are sufficient to start. Can add composition later if there's actual demand.

### Alternative 5: User-Written Custom Prompts

**Description**: Users write their own interview system prompts entirely

**Pros**:
- Ultimate flexibility
- Advanced users can fine-tune
- No built-in bias

**Cons**:
- Most users won't want this
- Requires prompt engineering expertise
- No guidance or structure
- Quality highly variable
- Harder to support

**Why Rejected**: While we should support custom templates eventually, most users will want to choose from good defaults. We can add custom template support in v0.3+.

## Decision Rationale

### Why Template-Based System is Best

1. **User Agency**
   - Users choose their interview style
   - Predictable experience
   - Can experiment with different templates
   - No AI deciding for them

2. **Clear Differentiation**
   - Each template has distinct personality
   - Users understand what they'll get
   - Can match style to content or mood
   - Different needs at different times

3. **Simple Implementation**
   - Templates are just Pydantic models
   - System prompts are strings
   - No complex composition logic
   - Easy to test

4. **Quality Control**
   - We craft each template carefully
   - Ensure all templates generate good questions
   - Can iterate based on feedback
   - Professional defaults

5. **Extensibility**
   - Easy to add new templates
   - Template structure is simple
   - Can support custom templates later
   - Registry pattern scales well

### Template Design Principles

**Each template should**:
- Have a distinct personality and focus
- Generate high-quality, contextual questions
- Be appropriate for common podcast types
- Feel different from other templates
- Be documented with clear use cases

**Templates should NOT**:
- Overlap significantly with each other
- Be too niche (< 5% use case)
- Require specific episode types
- Be overly complex to understand

### Built-in Template Choices

**Reflective** (Default):
- For most users and most episodes
- Personal growth and application focus
- Open-ended, empathetic questions
- Good for: self-improvement podcasts, interviews, stories

**Analytical**:
- For critical thinkers and debate podcasts
- Argument evaluation and logic focus
- Challenging, rigorous questions
- Good for: debate podcasts, complex topics, controversial content

**Creative**:
- For creative thinkers and ideation
- Connection-making and imagination focus
- Playful, exploratory questions
- Good for: creative podcasts, brainstorming, inspiration

**Why these three?**
- Cover most common thinking styles
- Complementary, not overlapping
- Research-backed (reflective practice, critical thinking, creative thinking)
- Tested and validated

## Consequences

### Positive

- ✅ **User choice** - Users select style that fits them
- ✅ **Clear options** - Three distinct, understandable templates
- ✅ **Simple implementation** - Pydantic models + prompts
- ✅ **Extensible** - Easy to add more templates
- ✅ **Quality control** - We optimize each template
- ✅ **Testable** - Each template can be tested independently
- ✅ **Documented** - Clear descriptions help users choose

### Negative

- ⚠️ **Choice paralysis** - Some users might not know which to pick
  - *Mitigation*: Good default (reflective), clear descriptions
- ⚠️ **Template maintenance** - Three templates to keep updated
  - *Mitigation*: Templates are mostly prompt text, low maintenance
- ⚠️ **Consistency across templates** - Quality might vary
  - *Mitigation*: Testing and user feedback to iterate

### Trade-offs Accepted

- **Three templates over One** - Personalization over simplicity
- **Manual selection over AI** - Control over "smart" automation
- **Built-in over Custom** - Quality over ultimate flexibility (for v1)

## Implementation Details

### Template Loading

```python
def load_template(name: str, config: InterviewConfig) -> InterviewTemplate:
    """Load interview template by name"""

    # Use configured default if no name provided
    if not name:
        name = config.default_template

    # Get built-in template
    template = get_template(name)

    # Future: Check for user custom template override
    # custom_path = config_dir / "interview_templates" / f"{name}.yaml"
    # if custom_path.exists():
    #     template = load_custom_template(custom_path)

    return template
```

### Question Generation with Template

```python
async def generate_question(
    agent: InterviewAgent,
    template: InterviewTemplate,
    context: InterviewContext,
    session: InterviewSession,
) -> Question:
    """Generate question using template"""

    # Select appropriate prompt
    if not session.exchanges:
        prompt_guidance = template.initial_question_prompt
    elif should_conclude(session):
        prompt_guidance = template.conclusion_prompt
    else:
        prompt_guidance = template.follow_up_prompt

    # Build full prompt with context
    full_prompt = f"""{context.to_prompt_context()}

Previous questions asked:
{[e.question.text for e in session.exchanges[-3:]]}

{prompt_guidance}

Generate ONE concise, open-ended question (< 30 words):"""

    # Generate with template's settings
    response = await agent.client.messages.create(
        model=agent.model,
        max_tokens=500,
        temperature=template.temperature,  # Template controls creativity
        system=template.system_prompt,     # Template controls personality
        messages=[{"role": "user", "content": full_prompt}]
    )

    question_text = response.content[0].text.strip()

    return Question(
        id=generate_id(),
        text=question_text,
        question_number=session.current_question_number + 1,
    )
```

### CLI Integration

```python
# In cli.py

@app.command()
def fetch(
    podcast: str,
    latest: bool = True,
    interview: bool = False,
    template: Optional[str] = typer.Option(
        None,
        help="Interview template (reflective, analytical, creative)"
    ),
):
    """Fetch and process podcast episode"""

    if interview:
        # Load template
        template_name = template or config.interview.default_template
        template = load_template(template_name, config.interview)

        # Run interview with template
        result = await run_interview(
            episode_output=output,
            template=template,
            config=config.interview,
        )
```

## Testing Strategy

### Unit Tests

```python
def test_template_loading():
    """Test template loading"""
    template = get_template("reflective")
    assert template.name == "reflective"
    assert template.target_questions == 5

def test_unknown_template():
    """Test unknown template raises error"""
    with pytest.raises(ValueError):
        get_template("unknown")

def test_template_system_prompts():
    """Test each template has distinct system prompt"""
    templates = [get_template(n) for n in ["reflective", "analytical", "creative"]]

    prompts = [t.system_prompt for t in templates]

    # All different
    assert len(set(prompts)) == 3

    # All substantial
    assert all(len(p) > 100 for p in prompts)
```

### Integration Tests

```python
async def test_question_generation_with_templates(mock_api):
    """Test question generation varies by template"""

    context = create_test_context()
    session = create_test_session()

    # Generate with each template
    questions = {}
    for template_name in ["reflective", "analytical", "creative"]:
        template = get_template(template_name)
        question = await generate_question(agent, template, context, session)
        questions[template_name] = question.text

    # Questions should be different
    assert len(set(questions.values())) == 3

    # Reflective should mention "you" or "your" (personal)
    assert any(word in questions["reflective"].lower() for word in ["you", "your"])

    # Analytical should be more objective
    # (harder to assert, but can check for analytical words)
```

### User Testing

- Test each template with real episodes
- Gather feedback on question quality
- Iterate on system prompts
- Ensure distinct personalities

## Future Enhancements

### Custom Templates (v0.3+)

```yaml
# ~/.config/inkwell/interview_templates/stoic.yaml
name: "stoic"
description: "Stoic philosophy-inspired reflection"
system_prompt: |
  You are conducting an interview inspired by Stoic philosophy.
  Focus on what is within the listener's control, virtue,
  and practical wisdom.
target_questions: 5
```

### Template Mixing (v0.4+)

```yaml
# Mix 60% reflective, 40% creative
interview:
  template_mix:
    reflective: 0.6
    creative: 0.4
```

### User-Created Templates

- Template marketplace or sharing
- Community-contributed templates
- Template rating system

## Monitoring & Review

### Success Criteria

- Users understand template differences
- Each template generates distinct questions
- Users have favorite templates
- Quality is consistently high across templates

### Review Trigger

Consider revisiting if:
- Users request new built-in templates frequently
- One template dominates (> 90% usage)
- Quality issues with specific template
- Custom template feature becomes highly requested

## References

- [Research: Interview Conversation Design](../research/interview-conversation-design.md)
- [Socratic Questioning](https://en.wikipedia.org/wiki/Socratic_questioning)
- [Reflective Practice](https://en.wikipedia.org/wiki/Reflective_practice)
- [Critical Thinking](https://en.wikipedia.org/wiki/Critical_thinking)

## Related Decisions

- ADR-020: Interview Framework Selection
- ADR-024: Interview Question Generation (to be created)

---

**Decision**: Template-based interview system with three built-in styles
**Rationale**: Personalization, quality control, simple implementation, user choice
**Status**: ✅ Accepted
