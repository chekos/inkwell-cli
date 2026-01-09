# Research: Interview Conversation Design

**Date**: 2025-11-08
**Author**: Claude Code
**Status**: Research Complete
**Related**: Phase 4 Unit 1

## Overview

This document researches effective interview conversation patterns for podcast episode reflection. The goal is to design a conversation system that helps users extract maximum value from episodes through thoughtful, engaging questions.

---

## Interview Design Principles

### Core Objectives

1. **Facilitate Reflection** - Help users think deeply about content
2. **Extract Insights** - Surface actionable takeaways
3. **Build Connections** - Link to personal experience and past knowledge
4. **Maintain Engagement** - Keep conversation interesting and valuable
5. **Respect Time** - Be concise and focused

### Anti-Patterns to Avoid

❌ **Generic questions** - "What did you think?"
❌ **Yes/no questions** - "Did you enjoy the episode?"
❌ **Too many questions** - Interview fatigue (> 10 questions)
❌ **Repetitive questions** - Asking same thing different ways
❌ **Leading questions** - Assuming user's opinion
❌ **Overly complex questions** - Multiple questions in one

---

## Question Taxonomy

### Question Types

#### 1. Opening Questions (Start the conversation)

**Purpose**: Ease into reflection, identify what resonated

**Examples**:
- "What aspect of this episode surprised you most?"
- "Which idea from the discussion has stuck with you?"
- "What part of this episode challenged your thinking?"

**Characteristics**:
- Open-ended
- Low cognitive load
- No wrong answer
- Focus on subjective experience

#### 2. Deep Dive Questions (Explore thinking)

**Purpose**: Go deeper into specific ideas or responses

**Examples**:
- "Can you elaborate on why that resonated with you?"
- "How does this connect to your experience with [topic]?"
- "What assumptions does this challenge for you?"

**Characteristics**:
- Build on previous responses
- Encourage specific examples
- Invite personal connection
- Higher cognitive engagement

#### 3. Application Questions (Make it actionable)

**Purpose**: Translate insights into action

**Examples**:
- "How might you apply this idea in your work?"
- "What would change if you adopted this perspective?"
- "What's one concrete step you could take based on this?"

**Characteristics**:
- Forward-looking
- Specific and concrete
- Tied to user's context
- Actionable

#### 4. Connection Questions (Link to broader knowledge)

**Purpose**: Relate to other episodes, experiences, ideas

**Examples**:
- "Does this remind you of anything from past episodes?"
- "How does this compare to [related concept] you've encountered?"
- "What parallels do you see between this and [domain]?"

**Characteristics**:
- Cross-referential
- Pattern recognition
- Synthesis across sources
- Broadening perspective

#### 5. Synthesis Questions (Wrap up insights)

**Purpose**: Consolidate learning, identify key takeaways

**Examples**:
- "What's the main insight you're taking away from this discussion?"
- "If you had to summarize your reflection in one sentence, what would it be?"
- "What will you remember about this episode a month from now?"

**Characteristics**:
- Synthesizing
- Concise
- Future-oriented
- Memorable

---

## Interview Flow Patterns

### Pattern 1: Linear Progression

```
Opening → Deep Dive → Application → Synthesis
```

**Use for**: Shorter episodes (< 30 min), single-topic episodes

**Example Flow**:
1. "What surprised you about the discussion of X?"
2. "Can you elaborate on that?"
3. "How might you apply this in your work?"
4. "What's your main takeaway?"

**Pros**: Clear structure, predictable, easy to follow
**Cons**: May feel rigid, misses interesting tangents

### Pattern 2: Depth-First Exploration

```
Opening → Deep Dive → Deeper Dive → Application
              ↓
         (If interesting)
              ↓
         Deep Dive 2 → Application 2
```

**Use for**: Rich episodes with multiple themes

**Example Flow**:
1. "What resonated most?"
2. "Tell me more about that..."
3. "How does that connect to X you mentioned?"
4. "Shifting gears, what about Y from the episode?"
5. "How does that relate to your experience?"

**Pros**: Natural, adaptive, explores interesting threads
**Cons**: Can go off track, harder to manage

### Pattern 3: Theme-Based Clusters

```
Opening → Theme 1 Questions → Theme 2 Questions → Synthesis
```

**Use for**: Multi-topic episodes, interview podcasts

**Example Flow**:
1. "The episode covered A, B, and C. Which interested you most?"
2. [Questions about chosen theme]
3. "Let's discuss [next theme]..."
4. [Questions about that theme]
5. "Looking across these themes, what connects them for you?"

**Pros**: Comprehensive, organized, covers breadth
**Cons**: May feel interview-like vs conversational

### Recommendation: Hybrid Approach

**Start with Pattern 1 (Linear)**, adapt based on responses:
- If response is rich → go depth-first (Pattern 2)
- If multiple themes → use theme clustering (Pattern 3)
- Always end with synthesis question

---

## Conversation Depth Management

### Depth Levels

**Level 0: Opening** (Broad, surface-level)
- "What stood out to you?"
- Low commitment, easy to answer

**Level 1: Exploration** (Specific, focused)
- "Why did that stand out?"
- Moderate thinking required

**Level 2: Analysis** (Deep, reflective)
- "How does this challenge your assumptions?"
- High cognitive engagement

**Level 3: Application** (Concrete, actionable)
- "What will you do differently?"
- Requires commitment

### Follow-up Decision Tree

```
User gives substantive response (>50 words, specific examples)
    ┌─ Current depth < 2?
    │   └─ YES → Generate follow-up question
    │       └─ Increase depth level
    └─ NO → Move to next topic
        └─ Reset depth to 0

User gives brief response (<20 words)
    └─ Move to next topic
        └─ Don't penalize, just move on

User says "skip", "next", "pass"
    └─ Move to next topic
        └─ Respect user's preference
```

### Example Depth Progression

**Level 0 Question**:
> "What aspect of the AI safety discussion surprised you?"

**User**: "I hadn't thought about alignment at small scales."

**Level 1 Follow-up**:
> "Interesting! Can you give an example of what you mean by 'small scales'?"

**User**: "Like in my work, we optimize for metrics without thinking about whether the metrics align with our actual goals..."

**Level 2 Follow-up**:
> "That's a powerful connection. How might you approach metric selection differently going forward?"

**User**: [Detailed response]

**Result**: Depth 2 reached, ready to move to next topic

---

## Question Quality Metrics

### Objective Metrics

| Metric | Good | Needs Improvement |
|--------|------|-------------------|
| Length | 10-30 words | < 5 or > 50 words |
| Structure | Single clear question | Multiple questions |
| Specificity | References episode content | Generic |
| Open-endedness | Invites elaboration | Yes/no answer |

### Subjective Quality Indicators

**High Quality Question**:
- Makes user think (but not too hard)
- Tied to specific episode content
- Personally relevant
- Clear what's being asked
- Worth the time to answer

**Low Quality Question**:
- Too vague or too specific
- No clear connection to episode
- Feels like homework
- Multiple questions packed in one
- User unsure how to answer

### Auto-Assessment Algorithm

```python
def assess_question(question: str, episode_context: dict) -> float:
    """Return quality score 0-1"""
    score = 0.5  # Start neutral

    # Length check
    word_count = len(question.split())
    if 10 <= word_count <= 30:
        score += 0.15
    elif word_count < 5 or word_count > 50:
        score -= 0.2

    # Open-ended check
    open_starters = ["what", "how", "why", "tell", "describe", "explain"]
    if any(question.lower().startswith(s) for s in open_starters):
        score += 0.15

    # Closed-ended penalty
    closed_starters = ["is", "are", "do", "does", "did", "can", "will"]
    if any(question.lower().startswith(s) for s in closed_starters):
        score -= 0.2

    # Specificity check (references episode content)
    episode_keywords = extract_keywords(episode_context)
    if any(keyword.lower() in question.lower() for keyword in episode_keywords):
        score += 0.2

    # Personal relevance
    personal_words = ["you", "your", "think", "feel", "experience"]
    if any(word in question.lower() for word in personal_words):
        score += 0.1

    # Multiple questions penalty
    if question.count("?") > 1:
        score -= 0.15

    return max(0.0, min(1.0, score))
```

---

## Interview Templates (Styles)

### 1. Reflective Interview (Default)

**Goal**: Deep personal reflection and insight

**System Prompt**:
```
You are conducting a reflective interview to help the listener process
a podcast episode. Your questions should:

- Encourage personal connection to the content
- Explore how ideas apply to their life/work
- Surface surprising or challenging insights
- Build on their responses with gentle follow-ups
- Help identify concrete next steps

Be warm, curious, and supportive. Keep questions concise.
```

**Question Examples**:
- "What idea from this episode has been lingering in your mind?"
- "How does this connect to something you're working on?"
- "What surprised or challenged you in this discussion?"

**Best for**: Most episodes, general reflection

### 2. Analytical Interview

**Goal**: Critical thinking and argument evaluation

**System Prompt**:
```
You are conducting an analytical interview to help the listener
critically examine ideas from a podcast episode. Your questions should:

- Encourage evaluation of arguments and evidence
- Explore assumptions and implications
- Consider alternative viewpoints
- Examine logical consistency
- Build intellectual rigor

Be intellectually curious and constructively challenging.
```

**Question Examples**:
- "What's the strongest argument presented in the episode?"
- "What assumptions underlie the main thesis?"
- "How would a critic respond to this argument?"

**Best for**: Debate podcasts, argument-heavy content

### 3. Creative Interview

**Goal**: Novel connections and idea generation

**System Prompt**:
```
You are conducting a creative interview to help the listener make
unexpected connections and generate new ideas. Your questions should:

- Encourage "what if" thinking
- Explore tangential connections
- Spark imagination and possibility
- Play with metaphors and analogies
- Avoid being too analytical

Be playful, imaginative, and open to tangents.
```

**Question Examples**:
- "If you combined this idea with something from your work, what might emerge?"
- "What unexpected connection does this spark for you?"
- "If this concept were a tool, how would you use it?"

**Best for**: Creative content, brainstorming, exploration

### Template Selection Logic

```python
def select_template(
    user_preference: Optional[str],
    episode_category: Optional[str],
) -> str:
    """Select interview template"""

    # User preference always wins
    if user_preference:
        return user_preference

    # Auto-detect based on episode
    if episode_category == "debate":
        return "analytical"
    elif episode_category == "creative":
        return "creative"
    else:
        return "reflective"  # Default
```

---

## Response Quality Assessment

### What Makes a Good User Response?

**Substantive Response** (worth follow-up):
- Length: 50+ words
- Contains specific examples
- Shows personal reflection
- Reveals thinking process
- Raises interesting points

**Brief Response** (move on):
- Length: < 20 words
- Generic ("That's interesting")
- No specifics
- Single word ("Skip")

**Skip Indicators**:
- Explicit: "skip", "next", "pass"
- Implicit: Very brief, off-topic

### Auto-Classification

```python
def classify_response(response: str) -> str:
    """Classify user response"""

    # Explicit skip
    if response.lower().strip() in ["skip", "next", "pass", "n"]:
        return "skip"

    # Word count
    word_count = len(response.split())

    # Very brief
    if word_count < 10:
        return "brief"

    # Substantive
    if word_count >= 50:
        return "substantive"

    # Check for specific indicators
    has_example = any(indicator in response.lower() for indicator in [
        "for example", "such as", "like when", "specifically"
    ])

    if has_example:
        return "substantive"

    # Medium responses default to substantive
    if word_count >= 20:
        return "substantive"

    return "brief"
```

---

## Conversation Exit Conditions

### When to End Interview

1. **Target questions reached**: ~5 questions completed
2. **User explicitly exits**: "done", "finish", "quit"
3. **Max time exceeded**: > 30 minutes
4. **Max cost reached**: > configured limit
5. **User fatigue detected**: Multiple brief/skip responses

### Graceful Exit Flow

```
User indicates done
    ↓
Ask: "Before we finish, any final thoughts?"
    ↓
Generate synthesis question
    ↓
Thank user, show summary
    ↓
Save transcript
```

### Exit Detection

```python
def should_end_interview(
    session: InterviewSession,
    last_response: str,
) -> tuple[bool, str]:
    """Check if interview should end"""

    # Explicit exit
    exit_words = ["done", "finish", "quit", "exit", "end", "stop"]
    if last_response.lower().strip() in exit_words:
        return True, "user_requested"

    # Target reached
    if session.question_count >= session.max_questions:
        return True, "target_reached"

    # Fatigue detection
    recent_responses = session.exchanges[-3:]
    if all(classify_response(e.response.text) == "brief" for e in recent_responses):
        return True, "user_fatigue"

    # Max cost
    if session.total_cost_usd >= session.max_cost:
        return True, "cost_limit"

    return False, ""
```

---

## Interview Quality Metrics

### Post-Interview Assessment

**Automatically collected**:
- Total questions asked
- Average response length
- Substantive response percentage
- Total time spent
- Depth levels reached
- Topics covered

**Quality Indicators**:

```python
def assess_interview_quality(session: InterviewSession) -> float:
    """Score interview quality 0-1"""

    score = 0.5  # Start neutral

    # Substantive response rate
    substantive_rate = session.substantive_response_count / session.question_count
    if substantive_rate >= 0.8:
        score += 0.2
    elif substantive_rate < 0.5:
        score -= 0.2

    # Average response length
    avg_length = session.average_response_length
    if avg_length >= 75:
        score += 0.15
    elif avg_length < 25:
        score -= 0.15

    # Depth reached
    max_depth = max(e.depth_level for e in session.exchanges)
    if max_depth >= 2:
        score += 0.15

    # Completion
    if session.is_complete:
        score += 0.1

    return max(0.0, min(1.0, score))
```

---

## Context-Aware Question Generation

### Using Episode Content

**From Summary**:
```
Episode discussed three main themes: X, Y, Z.

Question: "The episode covered [X, Y, Z]. Which resonated most with you?"
```

**From Quotes**:
```
Notable quote: "Quote text here"

Question: "The speaker said '[quote]'. How does this align with your experience?"
```

**From Key Concepts**:
```
Key concept identified: Concept name

Question: "The concept of [X] came up. How do you see this applying in your work?"
```

### Context Richness Levels

**Level 1: Generic** (No episode specifics)
- "What did you think of the episode?"
❌ Avoid

**Level 2: Topic-aware** (Mentions general topic)
- "What aspects of AI safety surprised you?"
✓ Acceptable

**Level 3: Content-specific** (References specific content)
- "The discussion about alignment problems at scale - how does this relate to your work?"
✓✓ Good

**Level 4: Quote/Example-driven** (Uses actual quotes)
- "When the speaker said 'optimization without alignment leads to perverse outcomes' - can you think of an example from your experience?"
✓✓✓ Excellent

### Implementation Strategy

```python
def generate_question(
    template: InterviewTemplate,
    context: InterviewContext,
    session: InterviewSession,
) -> str:
    """Generate context-aware question"""

    # Select content to reference
    if not session.exchanges:
        # First question - use summary or key concept
        content_ref = context.summary[:200]  # Brief excerpt
    else:
        # Later questions - use quotes or concepts
        if context.key_quotes and random.random() < 0.4:
            quote = random.choice(context.key_quotes)
            content_ref = f'"{quote["text"]}"'
        else:
            concept = random.choice(context.key_concepts)
            content_ref = f"the concept of {concept}"

    # Build prompt
    prompt = f"""Generate interview question that references: {content_ref}

Previous questions asked:
{[e.question.text for e in session.exchanges[-3:]]}

{template.question_generation_guidance}

Question:"""

    return prompt
```

---

## Best Practices Summary

### DO:
✓ Ask one clear question at a time
✓ Reference specific episode content
✓ Build on user's responses
✓ Keep questions concise (10-30 words)
✓ Allow users to skip questions
✓ End with synthesis question
✓ Track conversation depth
✓ Respect user's time

### DON'T:
❌ Ask yes/no questions
❌ Ask multiple questions at once
❌ Repeat similar questions
❌ Ignore user's previous responses
❌ Go too deep too fast
❌ Make questions too complex
❌ Force users to answer
❌ Exceed reasonable length (> 10 questions)

---

## References

- [The Art of Powerful Questions](https://umanitoba.ca/student/media/the_art_of_powerful_questions.pdf)
- [Coaching Questions Handbook](https://www.amazon.com/Coaching-Questions-Handbook-Great-Questions/dp/0991098404)
- Socratic Method and Questioning Techniques
- Motivational Interviewing Principles

---

## Next Steps

1. Create interview template system (reflective, analytical, creative)
2. Implement question quality assessment
3. Design conversation flow state machine
4. Create follow-up generation logic
5. Build exit detection system

---

**Status**: Research complete, patterns identified, ready for implementation
