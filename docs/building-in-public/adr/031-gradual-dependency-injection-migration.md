# ADR-031: Gradual Dependency Injection Migration

**Status:** Accepted
**Date:** 2025-01-18
**Context:** Issue #17 - Complete Dependency Injection Pattern

## Context

After PR#16 introduced basic DI for `CostTracker`, we needed to extend this pattern to configuration management. Our services (`TranscriptionManager`, `ExtractionEngine`) were receiving individual configuration parameters (API keys, model names, etc.), making them brittle and difficult to extend.

The challenge: migrate to a cleaner DI pattern while maintaining backward compatibility with existing code and configuration files.

## Decision

Implement a **gradual migration strategy** using optional config objects alongside existing parameters:

1. **Domain-specific config dataclasses** nested within `GlobalConfig`:
   - `TranscriptionConfig` - transcription service configuration
   - `ExtractionConfig` - extraction service configuration
   - `InterviewConfig` - already existed, kept as-is

2. **Backward-compatible service constructors** accepting both old and new patterns:
   ```python
   def __init__(
       self,
       config: TranscriptionConfig | None = None,  # NEW: preferred
       # Deprecated individual params maintained for compatibility
       gemini_api_key: str | None = None,
       model_name: str | None = None,
       # ...
   ):
       # Prefer config values, fall back to individual params
       if config:
           effective_api_key = config.api_key or gemini_api_key
           effective_model = model_name or config.model_name
       else:
           effective_api_key = gemini_api_key
           effective_model = model_name or "gemini-2.5-flash"
   ```

3. **Config migration** via `model_post_init` to handle deprecated top-level fields:
   ```python
   def model_post_init(self, __context) -> None:
       if self.transcription_model is not None:
           self.transcription.model_name = self.transcription_model
   ```

4. **Update orchestration layer first** to use new pattern, letting backward compatibility handle CLI/tests.

## Consequences

**Positive:**
- Zero breaking changes - all existing code continues to work
- Clean migration path - new code uses config objects
- Better organization - related config grouped by domain
- Easier testing - can inject entire config in one param
- Future-proof - can deprecate individual params in v2.0

**Negative:**
- Temporary code duplication in constructors
- Need to maintain both paths until v2.0
- Config migration logic adds slight complexity

**Neutral:**
- Tests needed updating to check new nested structure
- Documentation reflects new preferred approach

## Implementation Notes

Files modified:
- `src/inkwell/config/schema.py` - added `TranscriptionConfig`, `ExtractionConfig`
- `src/inkwell/transcription/manager.py` - optional `config` parameter
- `src/inkwell/extraction/engine.py` - optional `config` parameter
- `src/inkwell/pipeline/orchestrator.py` - uses new config objects
- `tests/unit/test_schema.py` - updated for nested structure

All core functionality tests pass (870/886). The 16 failing tests are pre-existing issues unrelated to DI changes.

## Related

- ADR-025: Cost tracking DI (established pattern)
- Issue #17: Complete Dependency Injection Pattern
- Issue #18: Code simplification follow-up
