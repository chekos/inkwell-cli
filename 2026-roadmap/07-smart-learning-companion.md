# Smart Learning Companion

**Category:** New Feature | Integration
**Quarter:** Q3
**T-shirt Size:** L

## Why This Matters

Inkwell's vision is to transform passive listening into active learning, but the current workflow ends when notes are generated. Reading notes once doesn't create lasting knowledge—cognitive science shows that spaced repetition, active recall, and application practice are essential for retention.

A Smart Learning Companion extends Inkwell beyond note-taking into actual learning. It prompts you to review key concepts at optimal intervals, generates flashcards from extracted quotes and ideas, asks comprehension questions days after you process an episode, and helps you connect new content to previously learned material.

This is where Inkwell transcends being a "podcast note tool" and becomes a true learning system—one that doesn't just capture what you heard but ensures you remember and can apply it.

## Current State

**Learning-adjacent features:**
- Interview mode asks reflection questions
- Key concepts extraction identifies main ideas
- Quotes extraction captures memorable statements
- My notes capture personal reflections

**What's missing:**
- No spaced repetition scheduling
- No flashcard generation
- No review prompts or reminders
- No active recall testing
- No comprehension verification
- No application suggestions
- No progress tracking

**Related file:**
- `src/inkwell/interview/simple_interviewer.py` - Closest to learning interaction

## Proposed Future State

An intelligent learning companion that:

1. **Generates learning materials:**
   - Auto-create flashcards from key concepts and quotes
   - Generate comprehension questions from summaries
   - Create "apply this" challenges based on content
   - Identify connections to previously learned material

2. **Schedules optimal reviews:**
   - Spaced repetition algorithm (SM-2 or FSRS)
   - Daily review queue: "Review 5 concepts from last week"
   - Priority based on importance and decay

3. **Conducts interactive reviews:**
   - `inkwell learn` for daily review session
   - Active recall prompts (not just re-reading)
   - Comprehension verification
   - Connection prompts across episodes

4. **Tracks learning progress:**
   - Retention metrics per concept
   - Learning streaks and habits
   - Knowledge map showing mastery levels

5. **Integrates with external tools:**
   - Export to Anki deck format
   - Export to RemNote, Mochi
   - Obsidian Spaced Repetition plugin compatibility

## Key Deliverables

- [ ] Design learning item schema (cards, questions, challenges)
- [ ] Implement flashcard generation from extracted content
- [ ] Create comprehension question generator
- [ ] Build spaced repetition scheduler (SM-2 or FSRS algorithm)
- [ ] Create `inkwell learn` command for review sessions
- [ ] Implement active recall testing interface
- [ ] Build learning progress tracking and metrics
- [ ] Create Anki export format (.apkg)
- [ ] Add Obsidian Spaced Repetition plugin compatibility
- [ ] Implement "connect to previous" prompts
- [ ] Create daily review notification system (optional)
- [ ] Add learning streaks and gamification elements
- [ ] Build learning analytics dashboard

## Prerequisites

- **Initiative #04 (Knowledge Graph Engine):** Enables cross-episode connections
- **Initiative #05 (Semantic Search):** Finds related content for connections

## Risks & Open Questions

- **Risk:** Flashcard quality depends on extraction quality. Mitigation: User curation, quality scoring.
- **Risk:** Users may not engage with review system. Mitigation: Low-friction UX, mobile notifications.
- **Risk:** Over-simplification loses nuance. Mitigation: Include context links, source references.
- **Question:** Should learning happen in CLI or web interface?
- **Question:** How to handle skipped reviews—reschedule or forgive?
- **Question:** Should we implement our own SRS or integrate with Anki?

## Notes

**Spaced repetition algorithms:**
- **SM-2:** Classic algorithm, well-understood
- **FSRS:** Modern algorithm, better retention modeling
- Both are open-source and well-documented

**Learning item types:**
```yaml
learning_items:
  flashcard:
    front: "What is the main idea of 'Atomic Habits'?"
    back: "Small improvements compound over time"
    source: "episode-id"
    concept: "habit-formation"

  recall_question:
    question: "Naval discussed a framework for decision-making. What was it?"
    answer_hint: "Related to irreversibility"
    full_answer: "Focus on decisions that are reversible..."

  application_challenge:
    prompt: "Apply the '2-minute rule' to one task today"
    concept: "habit-formation"
    reflection_questions:
      - "What task did you choose?"
      - "How did it go?"
```

**Review interface:**
```bash
# Start daily review
inkwell learn

# Review specific topic
inkwell learn --topic "productivity"

# View learning stats
inkwell learn stats

# Export to Anki
inkwell learn export --format anki --output deck.apkg
```

**Files to create:**
- `src/inkwell/learn/` - Learning module
- `src/inkwell/learn/scheduler.py` - SRS algorithm
- `src/inkwell/learn/generator.py` - Flashcard/question generation
- `src/inkwell/learn/session.py` - Review session management
- `src/inkwell/learn/export.py` - Anki/RemNote export
