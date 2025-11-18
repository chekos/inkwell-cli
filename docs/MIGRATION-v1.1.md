# Migration Guide: v1.0 → v1.1

## Overview

Version 1.1 introduces bug fixes for configuration handling and standardizes environment variable naming for the Gemini API.

## Breaking Changes

**None** - This release is backward compatible.

## Deprecations

### Environment Variable: `GOOGLE_AI_API_KEY`

**Status:** Deprecated (will be removed in v2.0.0)
**Timeline:** 6 months from v1.1 release
**Action Required:** Yes (recommended before v2.0.0)

#### What Changed

Previously, the tool used two different environment variable names for the Google Gemini API key:
- Transcription: `GOOGLE_AI_API_KEY`
- Extraction: `GOOGLE_API_KEY`

This caused users to need both variables set, leading to confusion and errors.

#### Migration

**Before (v1.0):**
```bash
# You needed BOTH of these:
export GOOGLE_AI_API_KEY="your-gemini-api-key"
export GOOGLE_API_KEY="your-gemini-api-key"
```

**After (v1.1+):**
```bash
# You only need ONE:
export GOOGLE_API_KEY="your-gemini-api-key"
```

#### Backward Compatibility

`GOOGLE_AI_API_KEY` still works in v1.1 but will show a deprecation warning:

```
WARNING: GOOGLE_AI_API_KEY is deprecated. Please use GOOGLE_API_KEY instead.
GOOGLE_AI_API_KEY will be removed in v2.0.0
```

#### Precedence

If both variables are set, `GOOGLE_API_KEY` takes precedence:

```bash
export GOOGLE_API_KEY="primary-key"
export GOOGLE_AI_API_KEY="deprecated-key"  # This will be ignored
# Tool uses: "primary-key"
```

## Bug Fixes

### Configuration Not Applied

**Fixed:** User's configured `transcription_model` value is now properly used throughout the application.

**Before (v1.0):**
```yaml
# config.yaml
transcription_model: gemini-2.0-flash-exp  # This was ignored!
```

**After (v1.1):**
```yaml
# config.yaml
transcription_model: gemini-2.5-flash  # This is now used!
```

### Model Names Updated

**Fixed:** Updated to current Gemini model names.

**Changed:**
- Default transcription model: `gemini-1.5-flash` → `gemini-2.5-flash`
- Default extraction model: `gemini-1.5-flash-latest` → `gemini-2.5-flash`

**Impact:** More reliable transcription (old models were returning 404 errors).

## Configuration Changes

### Updated Default Values

The default `config.yaml` template now uses:

```yaml
# LLM models to use
transcription_model: gemini-2.5-flash  # Was: gemini-2.0-flash-exp
interview_model: claude-sonnet-4-5      # Unchanged
```

### Existing Configs

Your existing config files are **not automatically updated**. They will continue to work as-is.

To use the new stable model, update your config:

```bash
# Option 1: Edit config file manually
nano ~/.config/inkwell/config.yaml

# Option 2: Use CLI command
inkwell config set transcription_model gemini-2.5-flash
```

## Testing Your Migration

### 1. Update Environment Variables

```bash
# Remove deprecated variable (optional, still works with warning)
unset GOOGLE_AI_API_KEY

# Set standard variable
export GOOGLE_API_KEY="your-gemini-api-key"
```

### 2. Test Transcription

```bash
# This should now work without errors
inkwell transcribe https://youtube.com/watch?v=example
```

### 3. Verify Config

```bash
# Check current configuration
inkwell config show

# Update model if needed
inkwell config set transcription_model gemini-2.5-flash
```

## Troubleshooting

### "Gemini API key not configured"

**Cause:** Neither `GOOGLE_API_KEY` nor `GOOGLE_AI_API_KEY` is set.

**Solution:**
```bash
export GOOGLE_API_KEY="your-key"
```

### "404 models/gemini-1.5-flash is not found"

**Cause:** Using old model name in config.

**Solution:**
```bash
inkwell config set transcription_model gemini-2.5-flash
```

### Deprecation Warning Appears

**Cause:** Still using `GOOGLE_AI_API_KEY` environment variable.

**Solution:**
```bash
unset GOOGLE_AI_API_KEY
export GOOGLE_API_KEY="your-key"
```

## Timeline

- **v1.1.0** (Current): `GOOGLE_AI_API_KEY` deprecated with warning
- **v1.5.0** (3 months): Final warning before removal
- **v2.0.0** (6 months): `GOOGLE_AI_API_KEY` support removed

## Questions?

See:
- [ADR-030: Standardize Gemini API Key](./adr/030-standardize-gemini-api-key.md)
- [Issue #15: Configuration bug fixes](https://github.com/your-repo/inkwell-cli/issues/15)
