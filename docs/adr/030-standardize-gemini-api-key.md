# ADR-030: Standardize Gemini API Key Environment Variable

## Status

Accepted

## Context

The codebase inconsistently used two different environment variable names for the Google Gemini API key:
- `GOOGLE_AI_API_KEY` in transcription code (`src/inkwell/transcription/gemini.py`)
- `GOOGLE_API_KEY` in extraction code (`src/inkwell/extraction/extractors/gemini.py`) and README

This caused user confusion and tool failures. Users had to set both variables to make the tool work, which was neither documented nor intuitive.

Google's official SDK documentation recommends `GOOGLE_API_KEY` as the primary environment variable name, with `GEMINI_API_KEY` as an alternative.

## Decision

We will standardize on `GOOGLE_API_KEY` as the primary environment variable for Gemini API authentication across all code:

1. **Update transcription code** to check `GOOGLE_API_KEY` first
2. **Maintain backward compatibility** by supporting `GOOGLE_AI_API_KEY` with a deprecation warning
3. **Remove `GOOGLE_AI_API_KEY` support** in v2.0.0 (6 month sunset period)
4. **Update all tests** to use `GOOGLE_API_KEY`

### Implementation

```python
# Try GOOGLE_API_KEY first (standard), then GOOGLE_AI_API_KEY (deprecated)
self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")

# Warn if using deprecated env var
if os.getenv("GOOGLE_AI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    logger.warning(
        "GOOGLE_AI_API_KEY is deprecated. Please use GOOGLE_API_KEY instead. "
        "GOOGLE_AI_API_KEY will be removed in v2.0.0"
    )
```

### Precedence Order

1. Explicit `api_key` parameter (if provided)
2. `GOOGLE_API_KEY` environment variable (standard)
3. `GOOGLE_AI_API_KEY` environment variable (deprecated, with warning)

## Consequences

### Positive

- **Consistent API key naming** across all codebase
- **Matches Google's SDK conventions** and documentation
- **Backward compatible** - existing users with `GOOGLE_AI_API_KEY` still work
- **Clear migration path** with warnings guiding users to update
- **Single env var needed** - users only set `GOOGLE_API_KEY`

### Negative

- **Breaking change in v2.0.0** when deprecated variable is removed
- **Deprecation warnings** may appear in logs for users with old configs
- **Documentation updates required** (minimal - README already correct)

## Migration Path

For users currently using `GOOGLE_AI_API_KEY`:

```bash
# Before (deprecated)
export GOOGLE_AI_API_KEY="your-key"

# After (standard)
export GOOGLE_API_KEY="your-key"
```

No immediate action required - tool will continue to work with deprecation warning until v2.0.0.

## References

- Issue #15: Configuration not passed through service layers
- Google AI SDK docs: https://ai.google.dev/gemini-api/docs/api-key
- Implementation PR: [TBD]
