# Implementation Checklist: Configuration Fixes

**Date:** 2025-11-18
**Context:** Fix bugs where hardcoded model names don't exist, config not passing from CLI to services, and inconsistent env var names.

## Phase 1: Environment Variable Standardization

- [ ] **Update `src/inkwell/transcription/gemini.py`**
  - [ ] Change `GOOGLE_AI_API_KEY` to `GOOGLE_API_KEY` (line 56)
  - [ ] Update docstring to reflect correct env var name

- [ ] **Verify `src/inkwell/extraction/extractors/gemini.py`**
  - [ ] Confirm it uses `GOOGLE_API_KEY` (line 59)
  - [ ] No changes needed if already correct

- [ ] **Update documentation**
  - [ ] README.md - Environment Variables section
  - [ ] CLAUDE.md - Add env var names if missing
  - [ ] Any setup guides or tutorials

- [ ] **Search for any other instances**
  ```bash
  # Find all GOOGLE_AI_API_KEY references
  grep -r "GOOGLE_AI_API_KEY" src/
  grep -r "GOOGLE_AI_API_KEY" tests/
  ```

## Phase 2: Model Name Updates

- [ ] **Update `src/inkwell/config/schema.py`**
  - [ ] Line 69: Change `transcription_model: str = "gemini-2.0-flash-exp"` to `"gemini-2.5-flash"`
  - [ ] Add `extraction_model: str = "gemini-2.5-flash"` if not present

- [ ] **Update `src/inkwell/transcription/gemini.py`**
  - [ ] Line 43: Change default from `"gemini-1.5-flash"` to `"gemini-2.5-flash"`
  - [ ] Update docstring to reflect new model

- [ ] **Update `src/inkwell/extraction/extractors/gemini.py`**
  - [ ] Line 34: Change `MODEL = "gemini-1.5-flash-latest"` to `MODEL = "gemini-2.5-flash"`
  - [ ] Update docstring/comments

- [ ] **Check for other hardcoded model references**
  ```bash
  # Find all gemini-1.5 references
  grep -r "gemini-1.5" src/
  grep -r "1.5-flash" src/
  ```

## Phase 3: Config Injection Pattern

- [ ] **Update service constructors to accept config**

  **TranscriptionManager:**
  - [ ] Add `model_name: str | None = None` parameter
  - [ ] Use parameter if provided, else fall back to default
  - [ ] Pass model_name to GeminiTranscriber

  **GeminiTranscriber:**
  - [ ] Already accepts `model_name` - verify it's used correctly
  - [ ] Ensure default is `"gemini-2.5-flash"`

  **ExtractionEngine:**
  - [ ] Add `model_name: str | None = None` parameter
  - [ ] Pass to extractor constructors

  **GeminiExtractor:**
  - [ ] Change MODEL constant or make it configurable
  - [ ] Accept model_name in constructor if needed

- [ ] **Update CLI to pass config**

  **Add Typer Context pattern:**
  ```python
  class InkwellContext:
      def __init__(self, config: GlobalConfig):
          self.config = config

  @app.callback()
  def main(ctx: typer.Context, ...):
      config = ConfigManager().load_config()
      ctx.obj = InkwellContext(config=config)
  ```

  **Update commands to use context:**
  - [ ] `transcribe_command`: Pass `config.transcription_model`
  - [ ] `fetch_command`: Pass config to PipelineOrchestrator
  - [ ] Any other commands that create services

- [ ] **Update PipelineOrchestrator**
  - [ ] Accept config in constructor
  - [ ] Pass model names to services it creates
  - [ ] Ensure config flows through entire pipeline

## Phase 4: Testing

- [ ] **Unit Tests**
  - [ ] Test `InkwellSettings` loads from environment
  - [ ] Test default model names are correct
  - [ ] Test config injection into services
  - [ ] Test GOOGLE_API_KEY validation

- [ ] **Integration Tests**
  - [ ] Test transcribe command with config override
  - [ ] Test fetch command uses config correctly
  - [ ] Test CLI context passing works

- [ ] **Manual Testing**
  ```bash
  # Test with environment variable
  export GOOGLE_API_KEY="your-key"
  uv run inkwell config show

  # Test transcription with correct model
  uv run inkwell transcribe <test-url>

  # Test fetch pipeline
  uv run inkwell fetch <test-url>
  ```

## Phase 5: Documentation

- [ ] **Update README.md**
  - [ ] Environment Variables section
  - [ ] Add `GOOGLE_API_KEY` (not GOOGLE_AI_API_KEY)
  - [ ] List supported models

- [ ] **Update CLAUDE.md**
  - [ ] Add env var requirements if missing
  - [ ] Update model names in examples

- [ ] **Create/Update ADR**
  - [ ] Document decision to standardize on GOOGLE_API_KEY
  - [ ] Document config injection pattern
  - [ ] Document model version choices

- [ ] **Update user-facing docs**
  - [ ] Setup guide
  - [ ] Configuration guide
  - [ ] Any tutorials

## Verification Checklist

Run these commands to verify everything works:

```bash
# 1. Check no hardcoded old model names remain
grep -r "gemini-1.5" src/
grep -r "GOOGLE_AI_API_KEY" src/

# 2. Test config loads correctly
uv run inkwell config show

# 3. Test transcription (requires API key)
export GOOGLE_API_KEY="your-key-here"
uv run inkwell transcribe <youtube-url> --output /tmp/test.txt

# 4. Run test suite
uv run pytest tests/

# 5. Test CLI help (should work without API key)
uv run inkwell --help
uv run inkwell transcribe --help
uv run inkwell fetch --help
```

## Files to Modify (Summary)

### Source Code
- [ ] `src/inkwell/config/schema.py` - Update default model names
- [ ] `src/inkwell/transcription/gemini.py` - Update env var and model name
- [ ] `src/inkwell/extraction/extractors/gemini.py` - Update model name
- [ ] `src/inkwell/cli.py` - Add context passing
- [ ] `src/inkwell/pipeline/orchestrator.py` - Accept and use config
- [ ] `src/inkwell/transcription/manager.py` - Accept model_name param

### Optional: New Files
- [ ] `src/inkwell/config/settings.py` - Pydantic Settings class (optional)

### Tests
- [ ] `tests/test_config.py` - Add config injection tests
- [ ] `tests/test_transcription.py` - Update model name expectations
- [ ] `tests/test_extraction.py` - Update model name expectations

### Documentation
- [ ] `README.md` - Update env vars and model names
- [ ] `CLAUDE.md` - Update examples
- [ ] `docs/adr/XXX-config-injection.md` - New ADR

## Notes

- Keep changes minimal and focused
- Don't migrate to new SDK yet (separate effort)
- Test each phase before moving to next
- Update tests as you modify code
- Document decisions in ADR

## Estimated Time

- Phase 1 (Env vars): 30 minutes
- Phase 2 (Model names): 30 minutes
- Phase 3 (Config injection): 2-3 hours
- Phase 4 (Testing): 1-2 hours
- Phase 5 (Documentation): 1 hour

**Total: 5-7 hours**

## Success Criteria

- [ ] No references to `GOOGLE_AI_API_KEY` in codebase
- [ ] No references to `gemini-1.5-flash` in codebase
- [ ] All services accept configuration via constructor
- [ ] CLI passes config through Typer context
- [ ] All tests pass
- [ ] Manual testing confirms fixes work
- [ ] Documentation updated
