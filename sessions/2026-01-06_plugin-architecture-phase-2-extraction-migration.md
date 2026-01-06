# Plugin Architecture Phase 2: ExtractionPlugin Migration

**Date:** 2026-01-06
**Objective:** Implement Phase 2 of the plugin architecture plan - migrate existing extraction system to use the new plugin infrastructure

---

## Summary

Successfully migrated the extraction system (ClaudeExtractor, GeminiExtractor) to inherit from a new `ExtractionPlugin` base class and integrated the plugin registry into `ExtractionEngine`. All 1095 tests pass with full backward compatibility maintained.

## The Journey

### What Didn't Work

1. **Circular import issue**: Initial implementation of `ExtractionPlugin` tried to inherit from both `InkwellPlugin` and `BaseExtractor`. This caused a circular import because:
   - `plugins/types/extraction.py` imported from `extraction/extractors/base.py`
   - `extraction/extractors/claude.py` imported from `plugins/types/extraction.py`
   - `extraction/engine.py` imported from both

   **Fix**: Removed the multiple inheritance approach. `ExtractionPlugin` now only inherits from `InkwellPlugin` and defines the extraction interface directly.

2. **Lazy initialization breaking tests**: Changed `ClaudeExtractor.__init__` to use lazy initialization, but existing tests expected `api_key` attribute to be set immediately on construction.

   **Fix**: Added `lazy_init: bool = False` parameter. Default behavior (immediate initialization) maintains backward compatibility, while plugin system can pass `lazy_init=True`.

3. **Tests failing with plugin registry**: Tests that mocked `ClaudeExtractor`/`GeminiExtractor` at module level failed because the new plugin registry discovery wasn't finding the mocks.

   **Fix**: Added `use_plugin_registry=False` parameter to `ExtractionEngine` for tests that need mocked extractors.

### What Worked

1. **Clean separation of concerns**: `ExtractionPlugin` provides plugin lifecycle management while maintaining the extraction interface
2. **Entry points for discovery**: Using `pyproject.toml` entry points allows third-party plugins to be discovered automatically
3. **Gradual migration path**: Deprecation warnings guide users while existing code continues to work

## The Solution

### Key Findings

**File structure:**
```
src/inkwell/plugins/
├── __init__.py           # Exports ExtractionPlugin
├── base.py               # InkwellPlugin base
├── registry.py           # PluginRegistry
├── discovery.py          # Entry point discovery
└── types/
    ├── __init__.py       # Exports ExtractionPlugin
    └── extraction.py     # NEW: ExtractionPlugin base class
```

**Entry points in pyproject.toml:**
```toml
[project.entry-points."inkwell.plugins.extraction"]
claude = "inkwell.extraction.extractors.claude:ClaudeExtractor"
gemini = "inkwell.extraction.extractors.gemini:GeminiExtractor"
```

### Code Examples

**ExtractionPlugin base class:**
```python
class ExtractionPlugin(InkwellPlugin):
    NAME: ClassVar[str]
    VERSION: ClassVar[str]
    DESCRIPTION: ClassVar[str]
    MODEL: ClassVar[str] = "unknown"

    @abstractmethod
    async def extract(self, template, transcript, metadata, ...) -> str: ...

    @abstractmethod
    def estimate_cost(self, template, transcript_length) -> float: ...

    @abstractmethod
    def supports_structured_output(self) -> bool: ...
```

**Using plugin registry in ExtractionEngine:**
```python
@property
def extraction_registry(self) -> PluginRegistry[ExtractionPlugin]:
    if self._use_plugin_registry and not self._plugins_loaded:
        self._load_extraction_plugins()
    return self._registry
```

**Environment variable override:**
```bash
# Force specific extractor
INKWELL_EXTRACTOR=claude inkwell process ...
```

### Key Insights

1. **Avoid circular imports by using TYPE_CHECKING**: Put imports only needed for type hints under `if TYPE_CHECKING:` block
2. **Backward compatibility through defaults**: `lazy_init=False` and `use_plugin_registry=True` maintain existing behavior
3. **Entry points enable extensibility**: Third-party packages can register their own extractors without modifying inkwell

## Lessons Learned

1. **Plan for circular imports early**: When creating base classes that will be inherited by existing code, map out the import graph first
2. **Tests reveal hidden dependencies**: The failing tests showed that code was depending on immediate initialization even when not explicitly documented
3. **Use feature flags for migration**: `use_plugin_registry` flag allows gradual adoption and easy testing
4. **Deprecation warnings are documentation**: They guide users to new patterns while allowing existing code to work

## Related Resources

- **Plan file**: `plans/feat-plugin-architecture.md`
- **Phase 1 session**: `sessions/2026-01-06_plugin-architecture-phase1-implementation.md`
- **New files created**:
  - `src/inkwell/plugins/types/extraction.py`
  - `tests/unit/plugins/test_extraction_plugin.py`
- **Modified files**:
  - `pyproject.toml` (entry points)
  - `src/inkwell/extraction/engine.py` (registry integration)
  - `src/inkwell/extraction/extractors/claude.py`
  - `src/inkwell/extraction/extractors/gemini.py`
  - `tests/unit/test_batch_extraction.py`

## Next Steps (Phase 3)

- Create `TranscriptionPlugin` base class
- Migrate YouTube and Gemini transcribers to plugin architecture
- Register transcription entry points
