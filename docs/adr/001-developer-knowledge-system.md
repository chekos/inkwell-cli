---
title: ADR 001 - Adopt Developer Knowledge System (DKS) for Documentation
adr:
  author: Claude
  created: 05-Nov-2025
  status: accepted
---

# ADR 001: Adopt Developer Knowledge System (DKS) for Documentation

**Date:** 2025-11-05
**Status:** Accepted

## Context

Software projects accumulate critical knowledge—architectural decisions, implementation rationale, experimental results, and lessons learned—but this knowledge often lives only in commit messages, Slack threads, or developers' heads. When team members leave, context is lost. When AI agents join the project, they lack the "why" behind code decisions.

We need a documentation system that:
- Captures the "why" behind decisions, not just the "what"
- Is searchable and traceable
- Scales across years of development
- Supports both human developers and AI agents
- Works with existing tools (git, markdown, GitHub)

## Decision

We will implement a **Developer Knowledge System (DKS)** with five documentation pillars:

1. **📝 Engineering Logs (`/devlog`)** - Daily/weekly development progress and reasoning
2. **🏗️ Architecture Decision Records (`/adr`)** - Significant technical decisions
3. **🔬 Research & Experiments (`/experiments`)** - Empirical tests and benchmarks
4. **🔍 Research Documentation (`/research`)** - External research on frameworks and best practices
5. **💡 Lessons Learned (`/lessons`)** - Retrospectives and insights

Each pillar uses simple markdown templates with minimal structure. Files are named with dates (YYYY-MM-DD) or sequential numbers (ADRs) for easy organization and searchability.

## Consequences

**Positive:**
- Clear separation of concerns - know where to document what
- Searchable by date, topic, or tag
- Scalable folder-based structure
- AI-friendly structured markdown
- Zero cost (standard git + markdown)

**Negative:**
- Requires discipline to maintain
- Multiple places to document (but each has clear purpose)
- Need to keep templates simple to avoid hallucination

## Alternatives Considered

1. **Single ARCHITECTURE.md file** - Doesn't scale, hard to search, becomes unwieldy
2. **Wiki or Notion** - External dependency, harder to version control with code
3. **No formal documentation** - Knowledge loss, poor onboarding, context gaps

## References

- [docs/README.md](../README.md) - DKS overview and guidance
- Similar systems: ADR pattern (Michael Nygard), Engineering Daybook pattern
