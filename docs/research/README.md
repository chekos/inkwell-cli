# Research Documentation

Comprehensive external research on frameworks, best practices, and industry patterns that inform technical decisions.

## Format

Use the template: [template.md](./template.md)

## When to Create Research Docs

Create research documentation when:
- Evaluating new frameworks or libraries before adoption
- Gathering best practices for a technology domain
- Comparing industry approaches to a problem
- Preparing for major technical decisions (often precedes ADRs)

## Naming Convention

Use descriptive, topic-based names (not dates):
- `react-19-features.md`
- `ai-partner-onboarding-best-practices.md`
- `multi-tenancy-patterns.md`

## What to Include

- **Purpose** - What decision or implementation this informs
- **Scope** - Specific areas being investigated
- **Findings** - Key discoveries from external sources
- **Recommendations** - Suggested approach based on research
- **References** - Links to all sources (official docs, articles, examples)

## Relationship to ADRs

Research docs often precede ADRs:
1. **Research** - Gather information about options
2. **ADR** - Make decision based on research
3. **Devlog** - Document implementation

Link research docs in ADR references section.

## Keep Research Decision-Focused

Unlike ADRs which must be brief, research docs can be comprehensive. However, they should still be focused on informing a specific decision or implementation, not becoming general reference material.
