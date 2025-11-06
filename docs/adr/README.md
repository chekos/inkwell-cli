# Architecture Decision Records (ADRs)

ADRs document significant technical decisions made in this project. Each ADR captures:
- **Context** - Why we needed to make this decision
- **Decision** - What we chose and why
- **Consequences** - Trade-offs and impacts
- **Alternatives** - What else we considered

## Format

Use the template: [000-template.md](./000-template.md)

## Numbering

ADRs are numbered sequentially with leading zeros:
- 001, 002, 003... (not 1, 2, 3)
- This ensures proper sorting in file listings

## Status Values

- **Proposed** - Under discussion, not yet approved
- **Accepted** - Approved and implemented
- **Superseded by ADR-NNN** - Replaced by a newer decision

## When to Write an ADR

Write an ADR when making decisions that:
- Affect multiple components or the system architecture
- Involve significant trade-offs or risks
- Are difficult or expensive to reverse
- Will impact future development
- Need explanation to future developers (or your future self)

## When NOT to Write an ADR

Don't write ADRs for:
- Minor implementation details (goes in devlog)
- Code style choices (goes in linter config)
- Temporary workarounds
- Decisions that can be easily reversed

## Keep ADRs Brief

**Important:** ADRs document decisions, not implementations.

❌ **Don't include:**
- Full code examples (link to PRs instead)
- Implementation steps (goes in devlog or GitHub issues)
- Detailed metrics tracking (goes in monitoring docs)

✅ **Do include:**
- Why we made the decision
- What alternatives we considered
- What trade-offs we accepted
- Links to relevant resources
