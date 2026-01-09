# Plugin Architecture

**Category:** Architecture | DX Improvement
**Quarter:** Q1
**T-shirt Size:** L

## Why This Matters

Inkwell's current architecture is monolithic—all extractors, transcription providers, and output formats are hardcoded. Adding a new LLM provider means modifying core files. Supporting a new output format requires changes to the output manager. This tight coupling limits both the project's growth and community contribution potential.

A plugin architecture transforms Inkwell from a tool into a platform. Third-party developers can add support for new LLM providers (OpenAI, Ollama, local models), custom transcription backends (Whisper, AssemblyAI), export formats (Notion, Roam, Logseq), and specialized extractors for niche podcast categories—all without touching core code.

This is strategically essential for every ambitious initiative in this roadmap. Universal content ingestion (#03), the template marketplace (#08), and multi-export system (#09) all require clean extension points. Building the plugin architecture now prevents massive refactoring later.

## Current State

**Existing abstractions (good foundation):**
- `BaseExtractor` abstract class in `src/inkwell/extraction/extractors/base.py`
- Provider selection logic in extraction engine
- Template system with YAML-based configuration

**Current limitations:**
- Extractors hardcoded: only Claude and Gemini in `extractors/`
- Transcription providers hardcoded: YouTube and Gemini only
- Output formats hardcoded: Markdown only
- Interview templates embedded in `simple_interviewer.py:8,230`
- CLI module at 1,231 lines with 13-parameter `fetch_command`
- No discovery mechanism for extensions
- No lifecycle hooks for plugins

**Code coupling examples:**
- `src/inkwell/extraction/engine.py` directly imports Claude and Gemini extractors
- `src/inkwell/transcription/manager.py` has hardcoded fallback chain
- `src/inkwell/output/manager.py` generates Markdown only

## Proposed Future State

A clean plugin system where:

1. **Plugin types** are clearly defined:
   - `TranscriptionPlugin` - Add new audio transcription backends
   - `ExtractionPlugin` - Add new LLM providers
   - `OutputPlugin` - Add new export formats
   - `ContentPlugin` - Add new content source types
   - `InterviewPlugin` - Add new interview strategies

2. **Discovery is automatic:**
   - Plugins installed via `uv add inkwell-plugin-xxx`
   - Discovered via Python entry points
   - Configured in `~/.config/inkwell/plugins.yaml`

3. **Lifecycle is managed:**
   - `on_load`, `on_configure`, `on_process`, `on_complete` hooks
   - Dependency injection for core services
   - Graceful degradation when plugins fail

4. **CLI is extensible:**
   - Plugins can add subcommands
   - Configuration namespace isolation
   - Help text auto-generated from plugin metadata

## Key Deliverables

- [ ] Design plugin interface specification (RFC document)
- [ ] Create base plugin classes: `InkwellPlugin`, `TranscriptionPlugin`, `ExtractionPlugin`, `OutputPlugin`
- [ ] Implement plugin discovery via `importlib.metadata` entry points
- [ ] Create plugin configuration schema in `~/.config/inkwell/plugins.yaml`
- [ ] Refactor extraction engine to use plugin registry instead of hardcoded imports
- [ ] Refactor transcription manager to use plugin registry
- [ ] Add plugin lifecycle hooks (load, configure, process, complete)
- [ ] Create plugin development guide in documentation
- [ ] Create example plugin repository: `inkwell-plugin-template`
- [ ] Migrate existing extractors (Claude, Gemini) to plugin format
- [ ] Add `inkwell plugins list|install|enable|disable` commands

## Prerequisites

- **Initiative #01 (CI/CD Pipeline Excellence):** Need automated testing before major refactoring

## Risks & Open Questions

- **Risk:** Plugin API instability could break third-party plugins. Mitigation: Use semantic versioning for plugin API, document stability guarantees.
- **Risk:** Performance overhead from plugin discovery. Mitigation: Cache discovered plugins, lazy loading.
- **Risk:** Security concerns with arbitrary plugin code. Mitigation: Plugin sandboxing, permissions model for sensitive operations.
- **Question:** Should plugins have access to all core services or a restricted subset?
- **Question:** How to handle plugin version conflicts?
- **Question:** Should we support runtime plugin loading or require restart?

## Notes

**Inspiration from other tools:**
- `llm` by Simon Willison uses entry points for LLM providers
- `datasette` has a mature plugin ecosystem
- `mkdocs` and `pytest` use entry points for extensibility

**Files to refactor:**
- `src/inkwell/extraction/engine.py` (978 lines) - Extract provider registry
- `src/inkwell/transcription/manager.py` - Extract transcription registry
- `src/inkwell/cli.py` (1,231 lines) - Split into command groups, enable plugin commands
- `src/inkwell/interview/simple_interviewer.py` - Move templates to plugins

**Plugin entry point specification:**
```toml
# Example pyproject.toml for a plugin
[project.entry-points."inkwell.extractors"]
openai = "inkwell_openai:OpenAIExtractor"
```
