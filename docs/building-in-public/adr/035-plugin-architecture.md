---
title: ADR 035 - Plugin Architecture
adr:
  author: Claude Code
  created: 06-Jan-2026
  status: accepted
---

# ADR 035: Plugin Architecture

**Date:** 2026-01-06
**Status:** Accepted

## Context

Inkwell started as a monolithic CLI tool with hardcoded providers for extraction (Claude, Gemini), transcription (YouTube, Gemini), and output (Markdown). As the project evolved, we identified the need for extensibility:

1. **Community contributions**: Allow third-party developers to add new providers without modifying core code
2. **Flexibility**: Users can choose providers based on their needs (cost, quality, offline capability)
3. **Future growth**: Enable new plugin types (interview templates, content sources) without refactoring

We needed a plugin system that:
- Discovers plugins automatically (no manual registration)
- Provides clear lifecycle hooks for initialization and cleanup
- Supports configuration via YAML and environment variables
- Handles failures gracefully with recovery hints
- Maintains backward compatibility with existing code

## Decision

We implemented a plugin architecture using Python entry points (`importlib.metadata`) with:

### Three Plugin Types

1. **ExtractionPlugin**: LLM-based content extraction (inherits from `InkwellPlugin`)
2. **TranscriptionPlugin**: Audio-to-text conversion (inherits from `InkwellPlugin`)
3. **OutputPlugin**: Result formatting (inherits from `InkwellPlugin`)

### Entry Point Discovery

Plugins are discovered via standard Python entry points:

```toml
[project.entry-points."inkwell.plugins.extraction"]
claude = "inkwell.extraction.extractors.claude:ClaudeExtractor"
```

### Three Lifecycle Hooks

1. `configure(config, cost_tracker)`: Receive configuration and services
2. `validate()`: Raise `PluginValidationError` if not ready
3. `cleanup()`: Release resources

### Plugin Registry with Priority-Based Selection

- Built-in plugins: priority 100
- Third-party plugins: priority 50
- User overrides: priority 150
- CLI flags and environment variables override priority

### BrokenPlugin Wrapper

Failed plugins become `BrokenPlugin` instances with error details and recovery hints, preventing startup failures.

## Consequences

### Positive

- **Zero-config discovery**: Plugins are found automatically after `pip install`
- **Clean separation**: Plugin types have clear responsibilities
- **Graceful degradation**: Broken plugins don't crash the CLI
- **Testable**: `inkwell.plugins.testing` provides mock utilities
- **Backward compatible**: Existing code works unchanged

### Negative

- **Entry points required**: Plugin authors must configure pyproject.toml correctly
- **Discovery overhead**: Slight startup cost for plugin discovery (~50ms)
- **API stability commitment**: Plugin API changes require migration support

### Neutral

- **No plugin marketplace**: Users install via pip, not a central registry
- **No sandboxing**: Third-party plugins have full Python access

## Alternatives Considered

### 1. pluggy (pytest-style hooks)

**Pros:**
- Mature, battle-tested
- Built-in call ordering

**Cons:**
- Additional dependency
- Hook-based API more complex than class inheritance

**Rejected:** Entry points + base classes are simpler and sufficient for our needs.

### 2. stevedore (OpenStack)

**Pros:**
- Multiple manager patterns
- Good for complex selection logic

**Cons:**
- Additional dependency
- Heavier than needed

**Rejected:** Standard library `importlib.metadata` is sufficient.

### 3. Namespace packages

**Pros:**
- No registration required
- Easy local development

**Cons:**
- Requires specific naming convention
- Less explicit than entry points

**Rejected:** Entry points are more explicit and standard.

### 4. Service locator pattern

**Pros:**
- Flexible service resolution
- Easy to mock in tests

**Cons:**
- Hidden dependencies
- Harder to reason about

**Rejected:** Direct dependency injection via `configure()` is more explicit.

## References

- [Python Packaging - Creating and Discovering Plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [importlib.metadata Documentation](https://docs.python.org/3/library/importlib.metadata.html)
- [Simon Willison's LLM](https://github.com/simonw/llm) - Plugin architecture inspiration
- [Datasette Plugins](https://docs.datasette.io/en/latest/writing_plugins.html) - Mature plugin ecosystem
- Plan document: `plans/feat-plugin-architecture.md`
- Implementation sessions: `sessions/2026-01-06_plugin-architecture-*.md`
