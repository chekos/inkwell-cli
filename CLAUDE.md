# Claude Development Guide

This document contains guidelines for Claude AI when working on this project.

## Documentation: Developer Knowledge System (DKS)

This project uses a structured documentation system in `docs/`. You MUST use it.

### When Working on Tasks:

**During Development:**
- Create a devlog entry in `docs/devlog/YYYY-MM-DD-description.md` when starting new features
- Document implementation decisions, surprises, and next steps as you go
- Link to related ADRs and issues

**When Making Significant Decisions:**
- Create an ADR in `docs/adr/NNN-decision-title.md` (use next sequential number)
- Keep it brief - document the decision and rationale, not implementation details
- Reference any research docs that informed the decision

**When Researching Technologies:**
- Create research doc in `docs/research/topic-name.md` before making decisions
- Include findings, recommendations, and references to external sources
- Link research docs in subsequent ADRs

**After Completing Work:**
- Add lessons learned to `docs/lessons/YYYY-MM-DD-topic.md`
- Update any related ADRs if decisions changed during implementation

### Templates

All templates are in their respective directories:
- `docs/adr/000-template.md`
- `docs/devlog/YYYY-MM-DD-template.md`
- `docs/experiments/YYYY-MM-DD-template.md`
- `docs/research/template.md`
- `docs/lessons/YYYY-MM-DD-template.md`

**IMPORTANT:** Follow templates exactly. Keep ADRs brief to avoid hallucination.

### DKS Overview

See [docs/README.md](./docs/README.md) for full DKS documentation.
