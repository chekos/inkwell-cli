# feat: Plugin Architecture - Transform Inkwell into an Extensible Platform

**Type:** Enhancement | Architecture
**Quarter:** Q1 2026
**Size:** L (Large)
**Priority:** Strategic Foundation

---

## Overview

Transform Inkwell from a monolithic CLI tool into an extensible platform where third-party developers can add support for new LLM providers, transcription backends, export formats, and specialized extractors—all without touching core code.

This initiative establishes the foundational plugin system that enables every other ambitious feature in the 2026 roadmap: universal content ingestion, template marketplace, and multi-export capabilities.

---

## Problem Statement

**Current State:**
Inkwell's architecture is monolithic with tight coupling that limits growth and community contribution:

- **Extractors hardcoded**: Only Claude and Gemini in `src/inkwell/extraction/extractors/`
- **Transcription providers hardcoded**: YouTube and Gemini fallback chain in `TranscriptionManager`
- **Output formats hardcoded**: Markdown-only generation in `MarkdownGenerator`
- **Interview templates embedded**: Hardcoded "reflective" template in `simple_interviewer.py:231-244`
- **No discovery mechanism**: Adding new providers requires modifying core files
- **No lifecycle hooks**: Plugins can't participate in the processing pipeline

**Code Coupling Examples:**
| File | Issue | Lines |
|------|-------|-------|
| `src/inkwell/extraction/engine.py` | Direct imports of Claude/Gemini extractors | 19, 133-152 |
| `src/inkwell/transcription/manager.py` | Hardcoded provider instantiation | 14-18, 77-117 |
| `src/inkwell/output/markdown.py` | Single concrete implementation, no interface | 1-340 |
| `src/inkwell/config/schema.py` | Hardcoded provider literals | 65, 133 |

**Why Now:**
Every Q1 initiative depends on clean extension points. Building plugin architecture now prevents massive refactoring later.

---

## Proposed Solution

A clean plugin system with five distinct plugin types, automatic discovery via Python entry points, lifecycle management, and CLI extensibility.

### Plugin Types

```
┌─────────────────────────────────────────────────────────────────┐
│                      InkwellPlugin (Base)                       │
│  - NAME, VERSION, DESCRIPTION, API_VERSION (class attrs)        │
│  - DEPENDS_ON: list[str] (optional plugin dependencies)         │
│  - configure(), validate(), cleanup() (3 lifecycle hooks)       │
│  - api_version compatibility checking                           │
└─────────────────────────────────────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────┐
│ ExtractionPlugin │  │ TranscriptionPlugin │  │  OutputPlugin   │
│  - extract()     │  │  - transcribe()     │  │  - render()     │
│  - estimate_cost │  │  - HANDLES_URLS[]   │  │  - formats[]    │
│  - structured?   │  │  - CAPABILITIES{}   │  │                 │
└─────────────────┘  └─────────────────────┘  └─────────────────┘
       │                       │                       │
       ▼                       ▼                       ▼
 ClaudeExtractor        YouTubeTranscriber      MarkdownOutput
 GeminiExtractor        GeminiTranscriber       NotionOutput (future)
 OpenAIExtractor (3rd)  WhisperPlugin (3rd)     ObsidianOutput (future)
```

### Discovery Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Plugin Discovery                          │
│                                                                  │
│  Single canonical path: Entry points via importlib.metadata     │
│  (Local development uses `pip install -e .` / `uv add -e .`)    │
│                                                                  │
│  Entry Point Groups:                                             │
│  - inkwell.plugins.extraction    (ExtractionPlugin)             │
│  - inkwell.plugins.transcription (TranscriptionPlugin)          │
│  - inkwell.plugins.output        (OutputPlugin)                 │
│                                                                  │
│  Override via environment variables:                             │
│  - INKWELL_EXTRACTOR=claude      (force specific extractor)     │
│  - INKWELL_TRANSCRIBER=whisper   (force specific transcriber)   │
│                                                                  │
│  Conflict Detection:                                             │
│  - Duplicate plugin names → fail loudly with both sources shown │
│  - Users must resolve conflicts before proceeding                │
└─────────────────────────────────────────────────────────────────┘
```

### Lifecycle Hooks (Simplified)

```
┌───────────────┐    ┌────────────┐    ┌─────────┐    ┌─────────┐
│  configure()  │───▶│ validate() │───▶│  use()  │───▶│cleanup()│
└───────────────┘    └────────────┘    └─────────┘    └─────────┘
       │                   │               │              │
  Receive config      Raise exception   Called by     Release
  + CostTracker       if invalid        Engine/Mgr    resources
  (direct DI)         (PluginValidationError)
```

**Design Decisions (from review feedback):**
- **No `load()` hook** - Python imports already check dependencies; failures become BrokenPlugin
- **Direct dependency injection** - No service locator; CostTracker passed directly to `configure()`
- **Exceptions for validation** - `PluginValidationError` instead of `list[str]` returns
- **All async** - All plugin methods are async; sync plugins use `asyncio.to_thread()` internally

---

## Technical Approach

### Architecture

#### Core Plugin Infrastructure

**New Files:**
```
src/inkwell/plugins/
├── __init__.py           # Public API exports
├── base.py               # InkwellPlugin ABC + PluginValidationError
├── registry.py           # PluginRegistry generic class + PluginEntry
├── discovery.py          # Entry point discovery + conflict detection
├── loader.py             # Safe plugin loading with BrokenPlugin fallback
├── testing.py            # Test helpers for plugin authors (MockServices, fixtures)
├── types/
│   ├── __init__.py
│   ├── extraction.py     # ExtractionPlugin (extends BaseExtractor)
│   ├── transcription.py  # TranscriptionPlugin + TranscriptionRequest
│   └── output.py         # OutputPlugin (new base class)
└── config.py             # Plugin configuration schema
```

**Plugin Base Class:**
```python
# src/inkwell/plugins/base.py
from abc import ABC
from typing import Any, ClassVar
from pydantic import BaseModel

class PluginValidationError(Exception):
    """Raised when plugin configuration is invalid."""
    def __init__(self, plugin_name: str, errors: list[str]):
        self.plugin_name = plugin_name
        self.errors = errors
        super().__init__(f"Plugin '{plugin_name}' validation failed: {', '.join(errors)}")


class InkwellPlugin(ABC):
    """Base class for all Inkwell plugins."""

    # Required metadata (class attributes)
    NAME: ClassVar[str]
    VERSION: ClassVar[str]
    DESCRIPTION: ClassVar[str]
    API_VERSION: ClassVar[str] = "1.0.0"

    # Optional metadata
    AUTHOR: ClassVar[str] = ""
    HOMEPAGE: ClassVar[str | None] = None
    CONFIG_SCHEMA: ClassVar[type[BaseModel] | None] = None
    DEPENDS_ON: ClassVar[list[str]] = []  # Other plugin names this depends on

    def __init__(self):
        self._initialized = False
        self._config: BaseModel | dict[str, Any] = {}
        self._cost_tracker: "CostTracker | None" = None

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        """Called with validated config before first use.

        Args:
            config: Plugin-specific configuration (validated against CONFIG_SCHEMA)
            cost_tracker: Optional cost tracker for API usage (direct DI, no service locator)
        """
        if self.CONFIG_SCHEMA:
            self._config = self.CONFIG_SCHEMA(**config)
        else:
            self._config = config
        self._cost_tracker = cost_tracker
        self._initialized = True

    def validate(self) -> None:
        """Validate plugin state. Raise PluginValidationError if invalid.

        Called after configure() but before first use. Override to add
        custom validation (e.g., check API keys are set, binaries exist).
        """
        pass  # Default: no additional validation

    def cleanup(self) -> None:
        """Called when plugin is no longer needed. Release resources."""
        pass

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def config(self) -> BaseModel | dict[str, Any]:
        """Access validated configuration."""
        if not self._initialized:
            raise RuntimeError(f"Plugin {self.NAME} not configured")
        return self._config
```

**Plugin Registry:**
```python
# src/inkwell/plugins/registry.py
from dataclasses import dataclass
from typing import TypeVar, Generic, Callable, Literal

T = TypeVar('T', bound='InkwellPlugin')

@dataclass
class PluginEntry(Generic[T]):
    """Full plugin entry with status information."""
    name: str
    plugin: T | None  # None if broken
    status: Literal["loaded", "broken", "disabled"]
    error: str | None = None
    priority: int = 0
    source: str = ""  # e.g., "inkwell.plugins.extraction:claude"

    @property
    def is_usable(self) -> bool:
        return self.status == "loaded" and self.plugin is not None


class PluginConflictError(Exception):
    """Raised when two plugins have the same name."""
    def __init__(self, name: str, source1: str, source2: str):
        self.name = name
        self.sources = [source1, source2]
        super().__init__(
            f"Plugin name conflict: '{name}' registered by both:\n"
            f"  1. {source1}\n"
            f"  2. {source2}\n"
            "Resolve by uninstalling one of the conflicting packages."
        )


class PluginRegistry(Generic[T]):
    """Type-safe registry for plugin management with conflict detection."""

    # Standard priority ranges (document for plugin authors)
    PRIORITY_USER_OVERRIDE = 150    # User explicitly wants this plugin
    PRIORITY_BUILTIN = 100          # Built-in defaults
    PRIORITY_THIRDPARTY = 50        # Third-party production plugins
    PRIORITY_EXPERIMENTAL = 0       # Community/experimental plugins

    def __init__(self, plugin_type: type[T]):
        self._plugin_type = plugin_type
        self._entries: dict[str, PluginEntry[T]] = {}

    def register(
        self,
        name: str,
        plugin: T | None,
        priority: int = 0,
        source: str = "",
        error: str | None = None,
    ) -> None:
        """Register a plugin with conflict detection.

        Raises PluginConflictError if a plugin with the same name already exists.
        """
        if name in self._entries:
            existing = self._entries[name]
            raise PluginConflictError(name, existing.source, source)

        status: Literal["loaded", "broken", "disabled"] = "loaded" if plugin else "broken"
        self._entries[name] = PluginEntry(
            name=name,
            plugin=plugin,
            status=status,
            error=error,
            priority=priority,
            source=source,
        )

    def get(self, name: str) -> T | None:
        """Get plugin by name (None if not found, disabled, or broken)."""
        entry = self._entries.get(name)
        if entry and entry.is_usable:
            return entry.plugin
        return None

    def get_entry(self, name: str) -> PluginEntry[T] | None:
        """Get full plugin entry including status information."""
        return self._entries.get(name)

    def get_enabled(self) -> list[tuple[str, T]]:
        """Get all enabled plugins in priority order (highest first)."""
        usable = [(e.name, e.plugin) for e in self._entries.values() if e.is_usable]
        return sorted(usable, key=lambda x: self._entries[x[0]].priority, reverse=True)

    def find_capable(self, predicate: Callable[[T], bool]) -> list[tuple[str, T]]:
        """Find plugins matching predicate, in priority order."""
        return [(n, p) for n, p in self.get_enabled() if predicate(p)]

    def disable(self, name: str) -> None:
        """Disable plugin (keep registered but don't use)."""
        if name in self._entries:
            self._entries[name].status = "disabled"

    def enable(self, name: str) -> None:
        """Re-enable a disabled plugin (if it was loaded successfully)."""
        entry = self._entries.get(name)
        if entry and entry.plugin is not None:
            entry.status = "loaded"

    def all_entries(self) -> list[PluginEntry[T]]:
        """Get all plugin entries for display (e.g., `plugins list`)."""
        return sorted(self._entries.values(), key=lambda e: (-e.priority, e.name))
```

#### Entry Point Configuration

**pyproject.toml additions:**
```toml
# Built-in plugin entry points (using inkwell.plugins.* namespace)
[project.entry-points."inkwell.plugins.extraction"]
claude = "inkwell.extraction.extractors.claude:ClaudeExtractor"
gemini = "inkwell.extraction.extractors.gemini:GeminiExtractor"

[project.entry-points."inkwell.plugins.transcription"]
youtube = "inkwell.transcription.youtube:YouTubeTranscriber"
gemini = "inkwell.transcription.gemini:GeminiTranscriber"

[project.entry-points."inkwell.plugins.output"]
markdown = "inkwell.output.markdown:MarkdownOutput"
```

**Third-party plugin example (separate package):**
```toml
# inkwell-whisper-plugin/pyproject.toml
[project]
name = "inkwell-whisper-plugin"
version = "1.0.0"
dependencies = ["inkwell>=0.11.0", "openai-whisper>=20230314"]

[project.entry-points."inkwell.plugins.transcription"]
whisper = "inkwell_whisper:WhisperTranscriber"

# Optional: Declare plugin metadata for introspection without loading
[tool.inkwell.plugin]
type = "transcription"
min_api_version = "1.0.0"
capabilities = ["offline", "gpu-accelerated"]
```

### Implementation Phases

#### Phase 1: Foundation (Core Infrastructure)

**Tasks:**
- [ ] Create `src/inkwell/plugins/` directory structure
- [ ] Implement `InkwellPlugin` base class with 3 lifecycle hooks (`configure`, `validate`, `cleanup`)
- [ ] Implement `PluginValidationError` and `PluginConflictError` exceptions
- [ ] Implement `PluginRegistry` generic class with `PluginEntry` status tracking
- [ ] Implement plugin discovery via `importlib.metadata` entry points
- [ ] Implement conflict detection (fail loudly on duplicate names)
- [ ] Implement `BrokenPlugin` wrapper for failed loads with recovery hints
- [ ] Add plugin configuration section to `GlobalConfig` schema
- [ ] Create plugin API version checking (major version must match)
- [ ] Implement plugin dependency resolution (`DEPENDS_ON` topological sort)

**Key Files:**
| File | Purpose |
|------|---------|
| `src/inkwell/plugins/base.py` | InkwellPlugin ABC + PluginValidationError |
| `src/inkwell/plugins/registry.py` | PluginRegistry[T] + PluginEntry + PluginConflictError |
| `src/inkwell/plugins/discovery.py` | Entry point discovery + conflict detection |
| `src/inkwell/plugins/loader.py` | Safe loading with BrokenPlugin + recovery hints |
| `src/inkwell/plugins/testing.py` | MockServices and test helpers for plugin authors |
| `src/inkwell/config/schema.py` | Add plugins section |

#### Phase 2: ExtractionPlugin Migration

**Tasks:**
- [ ] Create `ExtractionPlugin` extending both `InkwellPlugin` and `BaseExtractor`
- [ ] Update `ClaudeExtractor` to inherit from `ExtractionPlugin`
- [ ] Update `GeminiExtractor` to inherit from `ExtractionPlugin`
- [ ] Add entry points for built-in extractors in pyproject.toml
- [ ] Refactor `ExtractionEngine` to use `PluginRegistry[ExtractionPlugin]`
- [ ] Update `_select_extractor()` to use registry + capability checking
- [ ] Inject `CostTracker` into plugins via `configure()`
- [ ] Add deprecation warnings for direct extractor imports
- [ ] Update extraction-related tests

**Refactoring Target:**
```python
# BEFORE (src/inkwell/extraction/engine.py:133-152)
self._claude_extractor: ClaudeExtractor | None = None
self._gemini_extractor: GeminiExtractor | None = None

# AFTER
from inkwell.plugins import PluginRegistry, ExtractionPlugin
from inkwell.plugins.discovery import discover_plugins
import os

class ExtractionEngine:
    def __init__(self, cost_tracker: CostTracker | None = None, ...):
        self._cost_tracker = cost_tracker
        self._registry = PluginRegistry[ExtractionPlugin](ExtractionPlugin)
        self._load_extractors()

    def _load_extractors(self):
        for name, plugin, error in discover_plugins("inkwell.plugins.extraction"):
            self._registry.register(name, plugin, error=error)
            if plugin:
                plugin.configure(self._get_plugin_config(name), self._cost_tracker)

    def _select_extractor(self, template: Template) -> ExtractionPlugin:
        # Check environment variable override first
        override = os.environ.get("INKWELL_EXTRACTOR")
        if override:
            plugin = self._registry.get(override)
            if plugin:
                return plugin
            raise ValueError(f"Extractor '{override}' not found (set via INKWELL_EXTRACTOR)")

        # Otherwise use priority-based selection
        for name, plugin in self._registry.get_enabled():
            return plugin
        raise RuntimeError("No extraction plugins available")
```

#### Phase 3: TranscriptionPlugin Migration

**Tasks:**
- [ ] Create `TranscriptionRequest` dataclass for flexible input handling
- [ ] Create `TranscriptionPlugin` base class with:
  - `transcribe(request: TranscriptionRequest) -> str` (async)
  - `can_handle(request: TranscriptionRequest) -> bool`
  - `estimate_cost(duration_seconds: float) -> float`
  - Class-level `HANDLES_URLS` and `CAPABILITIES` declarations
- [ ] Update `YouTubeTranscriber` to inherit from `TranscriptionPlugin`
- [ ] Update `GeminiTranscriber` to inherit from `TranscriptionPlugin`
- [ ] Add entry points for built-in transcribers
- [ ] Refactor `TranscriptionManager` to use `PluginRegistry[TranscriptionPlugin]`
- [ ] Move fallback chain logic to registry-based selection with env var override
- [ ] Handle chunking at manager level (not plugin responsibility)
- [ ] Update transcription-related tests

**New Base Class:**
```python
# src/inkwell/plugins/types/transcription.py
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal
from inkwell.plugins.base import InkwellPlugin

@dataclass
class TranscriptionRequest:
    """Flexible input for transcription plugins.

    Supports URLs, local files, and raw audio bytes. Plugins declare
    which input types they support via CAPABILITIES.
    """
    url: str | None = None
    file_path: Path | None = None
    audio_bytes: bytes | None = None

    @property
    def source_type(self) -> Literal["url", "file", "bytes"]:
        if self.url:
            return "url"
        elif self.file_path:
            return "file"
        return "bytes"

    def __post_init__(self):
        sources = sum(1 for x in [self.url, self.file_path, self.audio_bytes] if x)
        if sources != 1:
            raise ValueError("Exactly one of url, file_path, or audio_bytes must be provided")


class TranscriptionPlugin(InkwellPlugin):
    """Base class for transcription plugins.

    All methods are async. Sync implementations should use asyncio.to_thread().
    """

    # Class-level capability declarations (enables filtering without instantiation)
    HANDLES_URLS: ClassVar[list[str]] = []  # URL patterns, e.g., ["youtube.com", "youtu.be"]
    CAPABILITIES: ClassVar[dict] = {
        "formats": ["mp3", "wav", "m4a", "mp4"],
        "max_duration_hours": None,  # None = no limit
        "requires_internet": True,
        "supports_file": True,
        "supports_url": False,
        "supports_bytes": False,
    }

    @abstractmethod
    async def transcribe(self, request: TranscriptionRequest) -> str:
        """Transcribe audio to text.

        Args:
            request: Input containing URL, file path, or raw bytes

        Returns:
            Transcribed text
        """
        pass

    def can_handle(self, request: TranscriptionRequest) -> bool:
        """Check if this plugin can handle the given request.

        Default implementation checks source type against CAPABILITIES
        and URL patterns against HANDLES_URLS.
        """
        caps = self.CAPABILITIES

        # Check source type support
        if request.source_type == "url":
            if not caps.get("supports_url", False):
                return False
            # Check URL pattern match
            if self.HANDLES_URLS and request.url:
                return any(pattern in request.url for pattern in self.HANDLES_URLS)
            return True
        elif request.source_type == "file":
            return caps.get("supports_file", True)
        else:  # bytes
            return caps.get("supports_bytes", False)

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate cost for transcribing audio of given duration."""
        return 0.0  # Default: free (override for paid services)
```

#### Phase 4: OutputPlugin Foundation

**Tasks:**
- [ ] Create `OutputPlugin` base class with:
  - `render(extracted_data: dict, metadata: dict) -> str`
  - `output_format: str` property
  - `file_extension: str` property
- [ ] Refactor `MarkdownGenerator` to inherit from `OutputPlugin`
- [ ] Create `OutputManager` to orchestrate multiple output plugins
- [ ] Add entry point for markdown output
- [ ] Update output-related tests

**Note:** Full multi-format support is deferred to Initiative #09. This phase establishes the foundation.

#### Phase 5: CLI Plugin Commands

**Tasks:**
- [ ] Implement `inkwell plugins list` command
  - Show installed plugins by type with priority
  - Show enabled/disabled/broken status
  - Show broken plugins with error messages and recovery hints
- [ ] Implement `inkwell plugins enable <name>` command
- [ ] Implement `inkwell plugins disable <name>` command
- [ ] Implement `inkwell plugins validate [name]` command
  - Run plugin's `validate()` method
  - Check config validity
  - If no name given, validate all plugins
- [ ] Add `--extractor` and `--transcriber` flags to `fetch` command
  - Override default plugin selection
  - Validate plugin name exists
- [ ] Support environment variable overrides
  - `INKWELL_EXTRACTOR` - force specific extractor
  - `INKWELL_TRANSCRIBER` - force specific transcriber
  - Useful for CI/CD pipelines where CLI flags are awkward

**Note:** No `inkwell plugins install` command - users install plugins with `uv add <plugin-name>` directly (per ADR-008). This avoids duplicating uv's functionality and keeps the CLI simple.

**CLI Output Example:**
```
$ inkwell plugins list

Extraction Plugins:
  claude (built-in)     ✓ enabled   [priority: 100]  Claude API extractor
  gemini (built-in)     ✓ enabled   [priority: 100]  Google Gemini extractor

Transcription Plugins:
  youtube (built-in)    ✓ enabled   [priority: 100]  YouTube transcript API
  gemini (built-in)     ✓ enabled   [priority: 100]  Gemini audio transcription
  whisper (installed)   ✓ enabled   [priority: 50]   Local Whisper transcription

Output Plugins:
  markdown (built-in)   ✓ enabled   [priority: 100]  Markdown file generation

Broken Plugins:
  broken-plugin         ✗ error     ImportError: No module named 'torch'
                                    Recovery: uv add torch

To install plugins: uv add <plugin-name>
To override selection: --extractor=claude or INKWELL_EXTRACTOR=claude
```

#### Phase 6: Documentation & Developer Experience

**Tasks:**
- [ ] Create plugin development guide in `docs/user-guide/plugins/`
  - Creating your first plugin
  - Plugin lifecycle and hooks
  - Configuration schema
  - Testing plugins
  - Publishing to PyPI
- [ ] Create `inkwell-plugin-template` repository (cookiecutter template)
  - Pre-configured pyproject.toml
  - Example plugin implementations
  - Test fixtures
  - CI/CD setup
- [ ] Update CLI reference documentation
- [ ] Create ADR for plugin architecture decisions
- [ ] Add migration guide for existing users

---

## Alternative Approaches Considered

### 1. pluggy Hook System (pytest-style)

**Approach:** Use `pluggy` library for hook-based plugin system with `@hookspec` and `@hookimpl` decorators.

**Pros:**
- Mature, battle-tested (pytest uses it)
- Built-in call ordering (tryfirst/trylast)
- Hook wrappers for middleware-like behavior

**Cons:**
- Additional dependency
- More complex API surface
- Overkill for current needs (we don't need hook wrappers)

**Decision:** Rejected for v1. Entry points + simple base classes are sufficient. Can add pluggy later if hook ordering becomes critical.

### 2. stevedore Manager Classes

**Approach:** Use OpenStack's `stevedore` library with `DriverManager`, `ExtensionManager`, etc.

**Pros:**
- Multiple manager patterns built-in
- Good for complex plugin selection logic

**Cons:**
- Additional dependency
- Heavier weight than needed
- Less common in CLI tools

**Decision:** Rejected. `importlib.metadata` is standard library and sufficient.

### 3. Namespace Packages

**Approach:** Use `inkwell_plugins_*` naming convention for automatic discovery without entry points.

**Pros:**
- No registration required
- Easier local development

**Cons:**
- Requires specific naming convention
- Less explicit than entry points
- Can't have plugins with arbitrary package names

**Decision:** Rejected as primary mechanism. Entry points are more explicit and standard.

---

## Acceptance Criteria

### Functional Requirements

- [ ] **Plugin Discovery**: Plugins discovered automatically from `importlib.metadata` entry points
- [ ] **Conflict Detection**: Duplicate plugin names fail loudly with both sources shown
- [ ] **Extraction Plugins**: Claude and Gemini extractors work as plugins
- [ ] **Transcription Plugins**: YouTube and Gemini transcribers work as plugins
- [ ] **Plugin Selection**: User can override via `--extractor`/`--transcriber` flags or env vars
- [ ] **Environment Variables**: `INKWELL_EXTRACTOR` and `INKWELL_TRANSCRIBER` override defaults
- [ ] **Plugin Management**: `inkwell plugins list|enable|disable|validate` commands work
- [ ] **Graceful Degradation**: Broken plugins become `BrokenPlugin` with recovery hints
- [ ] **Configuration**: Plugin-specific config in `~/.config/inkwell/config.yaml` under `plugins:` key
- [ ] **Backward Compatibility**: Existing `inkwell fetch` commands work without changes
- [ ] **Plugin Dependencies**: `DEPENDS_ON` resolved via topological sort before loading

### Non-Functional Requirements

- [ ] **Startup Performance**: CLI startup with 10 plugins < 500ms (lazy loading)
- [ ] **API Stability**: Plugin API version tracked (major version must match)
- [ ] **All Async**: All plugin methods are async (sync implementations use `asyncio.to_thread()`)
- [ ] **Direct DI**: CostTracker passed directly to `configure()`, no service locator

### Quality Gates

- [ ] **Test Coverage**: >80% coverage on plugin infrastructure
- [ ] **Documentation**: Plugin development guide complete
- [ ] **Example Plugin**: Working example plugin in separate repository
- [ ] **Migration Tested**: Existing extractors migrated without breaking changes

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Plugin load time (10 plugins) | < 100ms | Benchmark in CI |
| Third-party plugins created | 2+ within 3 months | GitHub search |
| Breaking changes to existing users | 0 | Deprecation warnings only |
| Plugin API documentation completeness | 100% of public API | Doc coverage tool |

---

## Dependencies & Prerequisites

### Required Before Starting

- [x] **CI/CD Pipeline** (Initiative #01): Need automated testing before major refactoring
- [x] **Existing BaseExtractor**: Already exists in `src/inkwell/extraction/extractors/base.py`

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| `BaseExtractor` ABC | Exists | 3 abstract methods, good foundation |
| `ExtractionEngine` | Needs refactor | Remove hardcoded imports |
| `TranscriptionManager` | Needs refactor | Create base class first |
| `ConfigManager` | Exists | Add plugins section to schema |

### External Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `importlib.metadata` | Plugin discovery | stdlib (Python 3.10+) |
| `pydantic` | Config validation | Already in deps |
| `typer` | CLI commands | Already in deps |

---

## Risk Analysis & Mitigation

### High Risk

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking existing user workflows | High | Medium | Deprecation warnings for 2 versions, backward compat tests |
| Plugin API instability | High | Medium | Semantic versioning for plugin API, API version checking |
| Performance regression from eager loading | Medium | High | Lazy loading, startup benchmarks in CI |

### Medium Risk

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Security vulnerabilities from third-party plugins | High | Low | Warning on install, future sandboxing |
| Complex configuration | Medium | Medium | Clear documentation, validation errors |
| Plugin conflicts (same name) | Low | Medium | **Fail loudly** with `PluginConflictError` showing both sources |

### Low Risk

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| No third-party plugins created | Low | Low | Good docs, example plugins, community outreach |

---

## Resource Requirements

### Skills Needed

- Python ABC/Protocol design
- `importlib.metadata` entry points
- Typer CLI extensions
- Pydantic configuration schemas

### Estimated Effort by Phase

| Phase | Focus | Complexity |
|-------|-------|------------|
| Phase 1: Foundation | Core infrastructure | Medium |
| Phase 2: Extraction | Migrate extractors | Medium |
| Phase 3: Transcription | Migrate transcribers | Medium |
| Phase 4: Output | Output plugin base | Low |
| Phase 5: CLI | Plugin commands | Medium |
| Phase 6: Docs | Developer experience | Low |

---

## Future Considerations

### Post-v1 Enhancements

1. **Plugin Marketplace**: Curated registry for discovering plugins
2. **CLI Extension Points**: Plugins adding subcommands (`inkwell youtube download`)
3. **Interview Plugins**: Custom interview strategies and templates
4. **Content Source Plugins**: Universal content ingestion beyond RSS
5. **Plugin Analytics**: Opt-in usage tracking for ecosystem health

### Extensibility for Other Roadmap Items

| Initiative | Plugin Extension |
|------------|------------------|
| #03 Universal Content | ContentSourcePlugin type |
| #08 Template Marketplace | Template discovery via plugins |
| #09 Multi-Export | OutputPlugin implementations |
| #10 Team Features | SharedPlugin registry |

---

## References & Research

### Internal References

- Existing extractor base: `src/inkwell/extraction/extractors/base.py:1-143`
- Engine provider selection: `src/inkwell/extraction/engine.py:612-661`
- Transcription manager: `src/inkwell/transcription/manager.py:14-18, 77-117`
- CLI structure: `src/inkwell/cli.py:32-36`
- Config schema: `src/inkwell/config/schema.py:148-206`
- Roadmap item: `2026-roadmap/02-plugin-architecture.md`

### External References

- [Python Packaging - Creating and Discovering Plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [importlib.metadata Documentation](https://docs.python.org/3/library/importlib.metadata.html)
- [LLM by Simon Willison](https://github.com/simonw/llm) - Plugin architecture inspiration
- [Datasette Plugins](https://docs.datasette.io/en/latest/writing_plugins.html) - Mature plugin ecosystem
- [pluggy Documentation](https://pluggy.readthedocs.io/) - pytest's plugin framework
- [click-plugins](https://github.com/click-contrib/click-plugins) - CLI plugin pattern

### Related ADRs

- ADR-008: Use uv for Python tooling (plugin installation via `uv add`)
- ADR-013: BaseExtractor interface design
- ADR-016: Provider selection logic
- *New ADR needed*: Plugin architecture decisions

---

## Open Questions

### Resolved (from Review Feedback)

1. ~~**Plugin Discovery Priority**~~: **RESOLVED** - Single canonical path via entry points only. Local development uses `pip install -e .` / `uv add -e .` for editable installs.

2. **API Version Compatibility**: Major version must match, minor version backward compatible. ✓

3. **Multiple Plugins Selection**: Highest priority plugin where `can_handle()` returns True. Environment variables (`INKWELL_EXTRACTOR`, `INKWELL_TRANSCRIBER`) provide explicit override. ✓

4. ~~**Plugin Configuration Encryption**~~: **RESOLVED** - Use environment variables for API keys (standard practice) or existing config encryption. No special plugin-specific handling needed.

5. ~~**Async vs Sync**~~: **RESOLVED** - All plugin methods are async. Sync implementations should use `asyncio.to_thread()` internally. Consistency over flexibility.

6. ~~**Cost Tracking Injection**~~: **RESOLVED** - Direct dependency injection via `configure(config, cost_tracker)`. No service locator pattern.

### Remaining Questions (Answer During Implementation)

7. **Plugin CLI Extensions**: Can plugins add subcommands to main CLI?
   - **Proposed**: Defer to post-v1

8. **Plugin Sandboxing**: Any security isolation for third-party plugins?
   - **Proposed**: Defer to post-v1, add warning on install for now

9. **Plugin Testing Utilities**: What test helpers should `inkwell.plugins.testing` provide?
   - **Proposed**: `MockServices`, `mock_cost_tracker`, fixtures for common test scenarios

10. **API Migration Strategy**: How will plugins migrate when API_VERSION goes from 1.0 to 2.0?
    - **Proposed**: Document migration guide, provide adapter classes if needed, deprecation period of 2 minor versions

---

## Appendix: Plugin Interface Specifications

### InkwellPlugin (Base)

```python
class PluginValidationError(Exception):
    """Raised when plugin configuration is invalid."""
    plugin_name: str
    errors: list[str]

class InkwellPlugin(ABC):
    # Required metadata
    NAME: ClassVar[str]
    VERSION: ClassVar[str]
    DESCRIPTION: ClassVar[str]
    API_VERSION: ClassVar[str] = "1.0.0"

    # Optional metadata
    AUTHOR: ClassVar[str] = ""
    HOMEPAGE: ClassVar[str | None] = None
    CONFIG_SCHEMA: ClassVar[type[BaseModel] | None] = None
    DEPENDS_ON: ClassVar[list[str]] = []  # Other plugin names

    # Lifecycle (3 hooks, no load())
    def configure(self, config: dict[str, Any], cost_tracker: CostTracker | None = None) -> None: ...
    def validate(self) -> None: ...  # Raises PluginValidationError if invalid
    def cleanup(self) -> None: ...
```

### ExtractionPlugin

```python
class ExtractionPlugin(InkwellPlugin, ABC):
    @abstractmethod
    async def extract(self, template: Template, transcript: str,
                      metadata: dict, force_json: bool = False,
                      max_tokens_override: int | None = None) -> str: ...

    @abstractmethod
    def estimate_cost(self, template: Template, transcript_length: int) -> float: ...

    @abstractmethod
    def supports_structured_output(self) -> bool: ...
```

### TranscriptionPlugin

```python
@dataclass
class TranscriptionRequest:
    """Flexible input for transcription."""
    url: str | None = None
    file_path: Path | None = None
    audio_bytes: bytes | None = None

    @property
    def source_type(self) -> Literal["url", "file", "bytes"]: ...

class TranscriptionPlugin(InkwellPlugin, ABC):
    # Class-level capability declarations
    HANDLES_URLS: ClassVar[list[str]] = []  # e.g., ["youtube.com", "youtu.be"]
    CAPABILITIES: ClassVar[dict] = {
        "formats": ["mp3", "wav", "m4a", "mp4"],
        "max_duration_hours": None,
        "requires_internet": True,
        "supports_file": True,
        "supports_url": False,
        "supports_bytes": False,
    }

    @abstractmethod
    async def transcribe(self, request: TranscriptionRequest) -> str: ...

    def can_handle(self, request: TranscriptionRequest) -> bool: ...  # Default impl provided

    def estimate_cost(self, duration_seconds: float) -> float:
        return 0.0
```

### OutputPlugin

```python
class OutputPlugin(InkwellPlugin, ABC):
    @abstractmethod
    async def render(self, extracted_data: dict[str, Any],
                     metadata: dict[str, Any]) -> str: ...

    @property
    @abstractmethod
    def output_format(self) -> str: ...  # e.g., "markdown", "html", "pdf"

    @property
    @abstractmethod
    def file_extension(self) -> str: ...  # e.g., ".md", ".html", ".pdf"
```

### PluginRegistry

```python
@dataclass
class PluginEntry(Generic[T]):
    name: str
    plugin: T | None
    status: Literal["loaded", "broken", "disabled"]
    error: str | None = None
    priority: int = 0
    source: str = ""

class PluginConflictError(Exception):
    """Raised when two plugins have the same name."""
    name: str
    sources: list[str]

class PluginRegistry(Generic[T]):
    # Standard priority ranges
    PRIORITY_USER_OVERRIDE = 150
    PRIORITY_BUILTIN = 100
    PRIORITY_THIRDPARTY = 50
    PRIORITY_EXPERIMENTAL = 0

    def register(self, name, plugin, priority=0, source="", error=None) -> None: ...
    def get(self, name: str) -> T | None: ...
    def get_entry(self, name: str) -> PluginEntry[T] | None: ...
    def get_enabled(self) -> list[tuple[str, T]]: ...
    def find_capable(self, predicate: Callable[[T], bool]) -> list[tuple[str, T]]: ...
    def disable(self, name: str) -> None: ...
    def enable(self, name: str) -> None: ...
    def all_entries(self) -> list[PluginEntry[T]]: ...
```

---

## Appendix: Configuration Schema

```yaml
# ~/.config/inkwell/config.yaml
plugins:
  # Per-plugin configuration
  # Priority ranges: 150 (user override), 100 (built-in), 50 (third-party), 0 (experimental)

  whisper:
    enabled: true
    priority: 50  # Third-party default
    config:
      model: base
      device: cuda
      language: auto

  gemini-transcriber:
    enabled: true
    priority: 100  # Built-in default
    # config: uses global gemini_api_key from extraction section

  # Disable a built-in plugin
  youtube-transcriber:
    enabled: false

  # Force a plugin to be preferred over others
  my-custom-extractor:
    enabled: true
    priority: 150  # User override - always selected first
```

**Environment Variable Overrides:**
```bash
# Force specific plugins (useful in CI/CD)
export INKWELL_EXTRACTOR=claude
export INKWELL_TRANSCRIBER=whisper

# These override priority-based selection
inkwell fetch https://example.com/podcast.rss --latest
```

---

## Appendix: Entry Point Examples

**Built-in (pyproject.toml):**
```toml
# Using inkwell.plugins.* namespace for clarity
[project.entry-points."inkwell.plugins.extraction"]
claude = "inkwell.extraction.extractors.claude:ClaudeExtractor"
gemini = "inkwell.extraction.extractors.gemini:GeminiExtractor"

[project.entry-points."inkwell.plugins.transcription"]
youtube = "inkwell.transcription.youtube:YouTubeTranscriber"
gemini = "inkwell.transcription.gemini:GeminiTranscriber"

[project.entry-points."inkwell.plugins.output"]
markdown = "inkwell.output.markdown:MarkdownOutput"
```

**Third-party (inkwell-whisper-plugin/pyproject.toml):**
```toml
[project]
name = "inkwell-whisper-plugin"
version = "1.0.0"
dependencies = ["inkwell>=0.11.0", "openai-whisper>=20230314"]

[project.entry-points."inkwell.plugins.transcription"]
whisper = "inkwell_whisper:WhisperTranscriber"

# Optional: Declare plugin metadata for introspection without loading
[tool.inkwell.plugin]
type = "transcription"
min_api_version = "1.0.0"
capabilities = ["offline", "gpu-accelerated"]
```

---

## Appendix: Review Feedback Integration

This plan was refined based on parallel reviews from three perspectives:

**DHH Review (Challenge the Premise):**
- Pushed back on complexity, advocated for "do nothing" or minimal extension
- Valid concern: Don't build for imaginary contributors
- **Response:** We're building a platform, not just a CLI tool. The extensibility enables ecosystem growth.

**Kieran Review (Technical Excellence):**
- Approved (8/10) with refinements
- Key improvements incorporated:
  - Simplified lifecycle (3 hooks instead of 5)
  - Direct DI instead of service locator
  - All async, no sync/async mixing
  - `TranscriptionRequest` for flexible input types
  - `PluginEntry` for status tracking

**Simplicity Review (Complexity vs Value):**
- Approved with ~15% trimming
- Removed:
  - Local directory discovery (use editable installs instead)
  - `plugins install` command (use uv directly)
  - `load()` lifecycle hook (Python imports check deps)
- Added:
  - Explicit conflict detection (`PluginConflictError`)
  - Environment variable overrides
  - Class-level capability declarations

---

*Generated with [Claude Code](https://claude.ai/code)*
