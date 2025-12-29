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

---

## Current Research Documents

### Configuration & Settings
- [Configuration Management Best Practices](./configuration-management-best-practices.md) - Comprehensive guide for Python CLI config using Typer/Pydantic
- [Config Fixes Action Plan](./config-fixes-action-plan.md) - Quick implementation guide for fixing configuration bugs
- [Google GenAI Pydantic Typer Config](./google-genai-pydantic-typer-config.md) - Gemini API configuration patterns

### Testing Strategies
- [Pytest Testing Best Practices](./pytest-testing-best-practices.md) - General pytest patterns and conventions
- [Pytest Async Testing Patterns](./pytest-async-testing-patterns.md) - Testing async code effectively
- [Async Mock Quick Reference](./async-mock-quick-reference.md) - Mocking async functions and coroutines

### Error Handling & Documentation
- [Error Handling Best Practices](./error-handling-best-practices.md) - Exception design and user-facing errors
- [CLI Documentation Best Practices](./cli-documentation-best-practices.md) - Help text, README, and user guides
- [Framework Documentation Patterns](./framework-documentation-patterns.md) - Documenting reusable components

### Audio & Transcription
- [Transcription APIs Comparison](./transcription-apis-comparison.md) - Comparing YouTube, Gemini, Whisper APIs
- [Transcript Caching Strategy](./transcript-caching-strategy.md) - Caching patterns for API responses
- [yt-dlp Audio Extraction](./yt-dlp-audio-extraction.md) - Audio download and format conversion

### Interview & Extraction
- [Claude Agent SDK Integration](./claude-agent-sdk-integration.md) - Building interactive interviews
- [Interview Conversation Design](./interview-conversation-design.md) - UX patterns for CLI conversations
- [Terminal Interview UX](./terminal-interview-ux.md) - Rich terminal UI patterns
- [LLM Extraction Comparison](./llm-extraction-comparison.md) - Comparing Claude vs Gemini for extraction
- [Structured Extraction Patterns](./structured-extraction-patterns.md) - Template-based content extraction

### Templates & Output
- [Template Format Evaluation](./template-format-evaluation.md) - Comparing template formats (JSON, YAML, etc.)
- [Template Schema Design](./template-schema-design.md) - Designing flexible template schemas
- [Obsidian Integration Patterns](./obsidian-integration-patterns.md) - Markdown output for Obsidian

### Documentation Setup
- [MkDocs Material Setup](./mkdocs-material-setup.md) - Documentation site configuration

### Quick References
- [Implementation Checklist](./IMPLEMENTATION-CHECKLIST.md) - Step-by-step implementation guides
- [Quick Reference: Config Fixes](./QUICK-REFERENCE-config-fixes.md) - Fast lookup for config patterns
