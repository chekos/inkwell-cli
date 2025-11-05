# 🧭 Developer Knowledge System (DKS)

Welcome to the Inkwell Developer Knowledge System. This documentation framework captures the **why**, **how**, and **what** of our development work in a structured, searchable, and cumulative way.

## 📚 The Five Pillars

The DKS is organized into five interconnected documentation types:

### 1. 📝 [Engineering Log (`/devlog`)](./devlog)
**Purpose:** Daily/weekly development progress, reasoning, and context
**When to use:** Record ongoing work, decisions made during implementation, blockers encountered
**Cadence:** Frequent (daily or per feature)

### 2. 🏗️ [Architecture Decision Records (`/adr`)](./adr)
**Purpose:** Formal records of significant technical decisions
**When to use:** Major architectural choices, technology selection, design patterns
**Cadence:** As-needed (when making consequential decisions)

### 3. 🔬 [Research & Experiments (`/experiments`)](./experiments)
**Purpose:** Empirical tests, benchmarks, proof-of-concepts, explorations
**When to use:** Performance testing, comparing alternatives, validating approaches
**Cadence:** During research phases or when validating assumptions

### 4. 🔍 [Research Documentation (`/research`)](./research)
**Purpose:** Comprehensive external research on frameworks, best practices, and industry patterns
**When to use:** Before major technical decisions, when adopting new technologies, or researching implementation approaches
**Cadence:** During planning phases, before ADRs, or when exploring new problem domains
**Examples:** Framework capability research, best practices documentation, technology comparisons

### 5. 💡 [Lessons Learned (`/lessons`)](./lessons)
**Purpose:** Retrospectives, insights, post-mortems, and wisdom gained
**When to use:** After completing features, solving complex problems, or project milestones
**Cadence:** Regular retrospectives and after significant events

## 🎯 Goals

- **Scalability:** Replace single-file documentation with a folder-based hierarchy
- **Searchability:** Find decisions, experiments, or lessons by date, tag, or topic
- **Traceability:** Clear lineage between code changes, ADRs, and dev logs
- **Reusability:** Reference previous solutions or experiments in future work
- **Integrability:** Easy to parse or query by tools (GitHub Actions, RAG systems, etc.)

## 🚀 Getting Started

1. **Starting a new day/feature?** → Create a devlog entry
2. **Making a significant decision?** → Document it as an ADR
3. **Testing something?** → Record your experiment
4. **Researching a technology?** → Create a research document
5. **Learned something valuable?** → Capture it as a lesson

Each section has a `README.md` with detailed guidance and a template to copy.

## 🔗 Cross-Referencing

Documents can reference each other using relative links:

```markdown
Related to [ADR-001](../adr/001-nextjs-15-adoption.md)
See [Experiment 2024-12-15](../experiments/2024-12-15-animation-performance.md)
Research findings in [Research: AI Best Practices](../research/ai-partner-onboarding-best-practices.md)
```

## 📋 Naming Conventions

- **Devlog:** `YYYY-MM-DD.md` or `YYYY-MM-DD-brief-description.md`
- **ADR:** `NNNN-decision-title.md` (sequential numbering: 0001, 0002, etc.)
- **Experiments:** `YYYY-MM-DD-experiment-name/` (folder-based with README.md)
- **Research:** `descriptive-topic-name.md` (e.g., `ai-partner-onboarding-best-practices.md`)
- **Lessons:** `YYYY-MM-DD-topic.md`

## 📖 Documentation Philosophy

> "Documentation is a love letter to your future self."

Good documentation:
- Explains **why**, not just what
- Is written **during** development, not after
- Captures **context** that won't be obvious later
- Is **concise** but **complete**
- Includes **examples** and **diagrams** when helpful

## 🔄 Maintenance

- Archive outdated ADRs by updating their status
- Reference superseded documents when writing new ones
- Review lessons periodically to identify patterns
- Keep templates up-to-date with team needs

## 📞 Questions?

If you're unsure where to document something:

- **Daily progress or implementation notes?** → Devlog
- **Big decision with lasting impact?** → ADR
- **Testing or comparing options?** → Experiment
- **External research on frameworks/best practices?** → Research
- **Reflection or insight after the fact?** → Lesson

When in doubt, start with a devlog entry and promote to an ADR if it proves significant.
