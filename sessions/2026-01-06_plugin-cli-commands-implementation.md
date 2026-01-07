# Plugin CLI Commands Implementation (Phase 5)

**Date:** 2026-01-06
**Objective:** Implement CLI commands for plugin management and plugin override flags for the fetch command

---

## Summary

Successfully implemented Phase 5 of the plugin architecture plan: CLI commands for listing, enabling, disabling, and validating plugins, plus `--extractor` and `--transcriber` flags on the fetch command with environment variable support.

## The Journey

### What Didn't Work

- **Initial import approach**: First attempt imported `cli_plugins` at the top of `cli.py`, causing import ordering lint errors. Fixed by using a lazy import function.

- **Unused import**: Initially imported `load_plugins_into_registry` but didn't need it - removed during lint fix.

### What Worked

- **Typer subcommand architecture**: Created `cli_plugins.py` as a separate module with its own `typer.Typer()` app, then registered it via `app.add_typer()`.

- **Parameter-first override pattern**: Both `TranscriptionManager.transcribe()` and `ExtractionEngine._select_extractor()` now check for explicit parameter override first, then fall back to environment variable.

- **Environment variable binding via Typer**: Used `envvar="INKWELL_EXTRACTOR"` in `typer.Option()` to automatically read from env vars.

## The Solution

### Key Findings

1. **Plugin discovery already existed**: The `discover_all_plugins()` function from Phase 1 provided everything needed for the list command.

2. **Registry methods ready**: `PluginRegistry` already had `enable()`, `disable()`, `all_entries()`, and `get_broken()` methods from Phase 1.

3. **Validation via plugin interface**: Each plugin's `validate()` method (from `InkwellPlugin` base class) handles configuration validation.

### Implementation Structure

```
CLI Layer (cli_plugins.py)
    ↓
Plugin Discovery (discover_all_plugins)
    ↓
Plugin Registry (PluginRegistry per type)
    ↓
Plugin Entries (PluginEntry with status/error/priority)
```

Override Data Flow:
```
--extractor/--transcriber flags (or INKWELL_EXTRACTOR/INKWELL_TRANSCRIBER env vars)
    ↓
PipelineOptions.extractor / PipelineOptions.transcriber
    ↓
PipelineOrchestrator._transcribe() / PipelineOrchestrator._extract_content()
    ↓
TranscriptionManager.transcribe(transcriber_override=...) / ExtractionEngine(extractor_override=...)
    ↓
Plugin selection logic checks override before normal selection
```

### Code Examples

**Plugin list command usage:**
```bash
inkwell plugins list                    # List all plugins
inkwell plugins list --type extraction  # Filter by type
inkwell plugins list --all              # Include disabled
```

**Plugin override usage:**
```bash
inkwell fetch https://... --extractor claude --transcriber youtube
INKWELL_EXTRACTOR=gemini inkwell fetch https://...
```

### Key Insights

1. **Lazy imports avoid circular dependencies**: Moving the `cli_plugins` import inside a function prevented import order issues.

2. **Status not persisted**: The enable/disable commands modify in-memory state only. Users need config file changes for permanent settings.

3. **Broken plugins are informative**: The list command shows error messages and recovery hints for plugins that failed to load.

## Lessons Learned

- When adding CLI subcommands in Typer, consider using lazy imports if the subcommand module imports from the main module.
- Environment variable support in Typer is trivial with the `envvar` parameter.
- Plugin systems benefit from having override mechanisms at both the CLI and API levels.

## Related Resources

- Plan document: `plans/feat-plugin-architecture.md`
- Previous sessions:
  - `sessions/2026-01-06_phase-4-output-plugin-migration.md`
  - `sessions/2026-01-06_plugin-architecture-phase-3-complete.md`
- Test file: `tests/integration/test_cli_plugins.py`

## Files Changed

| File | Type | Description |
|------|------|-------------|
| `src/inkwell/cli_plugins.py` | New | Plugin CLI subcommands |
| `src/inkwell/cli.py` | Modified | Register subcommand, add flags |
| `src/inkwell/pipeline/models.py` | Modified | Add extractor/transcriber fields |
| `src/inkwell/pipeline/orchestrator.py` | Modified | Pass overrides through |
| `src/inkwell/transcription/manager.py` | Modified | Accept transcriber_override |
| `src/inkwell/extraction/engine.py` | Modified | Accept extractor_override |
| `tests/integration/test_cli_plugins.py` | New | 16 integration tests |

## Commits

```
0fdcc0c feat(plugins): Add CLI commands for plugin management (Phase 5)
0a85347 docs: Add session summary for Phase 5 plugin CLI implementation
```
