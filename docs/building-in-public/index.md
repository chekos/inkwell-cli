# Building in Public

Inkwell is built in public. This section contains our internal engineering documentation—the decisions, experiments, and lessons that shaped the project.

---

## Why Build in Public?

We believe in transparency. By sharing our engineering process, we:

- **Document decisions** for our future selves
- **Help others** learn from our experiences
- **Invite feedback** from the community
- **Build trust** through openness

---

## The Five Pillars

Our Developer Knowledge System (DKS) is organized into five interconnected documentation types:

### [Architecture Decision Records](adr/index.md)
Formal records of significant technical decisions. When we choose a library, design a system, or change our approach—we document why.

**Example:** [ADR-009: Transcription Strategy](adr/009-transcription-strategy.md) explains why we use YouTube transcripts first with Gemini fallback.

### [Engineering Logs](devlog/index.md)
Day-by-day development progress, reasoning, and context. These capture the journey, not just the destination.

**Phases covered:** Phase 1 (MVP), Phase 2 (Transcription), Phase 3 (Extraction), Phase 4 (Interview), Phase 5 (Obsidian)

### [Research](research/index.md)
Deep dives into technologies, patterns, and best practices. We research before we decide.

**Example:** [Transcription APIs Comparison](research/transcription-apis-comparison.md) evaluates options before choosing our approach.

### [Experiments](experiments/index.md)
Benchmarks, proof-of-concepts, and empirical tests. When we need data, we experiment.

**Example:** [Claude vs Gemini Extraction](experiments/2025-11-07-claude-vs-gemini-extraction.md) compares provider quality and costs.

### [Lessons Learned](lessons/index.md)
Retrospectives and insights after completing work. What worked, what didn't, and what we'd do differently.

---

## How We Use This

When starting new work:
1. **Check ADRs** for relevant past decisions
2. **Read research** if exploring new territory
3. **Review lessons** to avoid repeating mistakes

When making decisions:
1. **Create research doc** if comparing options
2. **Run experiments** if we need data
3. **Write ADR** to document the decision

When finishing work:
1. **Update devlog** with progress
2. **Write lessons** about what we learned

---

## Browse the Documentation

- [All ADRs](adr/index.md) - 34 architecture decisions
- [Engineering Logs](devlog/index.md) - Development progress by phase
- [Research](research/index.md) - Technology evaluations
- [Experiments](experiments/index.md) - Benchmarks and tests
- [Lessons Learned](lessons/index.md) - Retrospectives

---

## Contributing

If you're contributing to Inkwell, you're welcome to add to this documentation:

- Starting a feature? Create a devlog entry
- Making a decision? Write an ADR
- Learned something? Add to lessons

See the templates in each section for the format.
