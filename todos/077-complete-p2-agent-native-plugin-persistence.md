---
status: complete
priority: p2
issue_id: "077"
tags: [code-review, agent-native, plugin-architecture]
dependencies: []
---

# Add Programmatic Persistence for Plugin Enable/Disable State

## Problem Statement

The CLI commands `inkwell plugins enable/disable` modify in-memory registry state only. There's no programmatic API to persist plugin enable/disable state. This breaks agent-native principles: agents can call `registry.enable()` but the state is lost on restart.

**Why it matters:** Agents should have parity with human users. Humans can manually edit `config.yaml` to persist plugin state; agents have no equivalent API.

## Findings

**Location:** `src/inkwell/cli_plugins.py:259-262` and `297-300`

```python
console.print(
    "[dim]Note: Plugin state is not persisted. "
    "Use config file to permanently enable/disable plugins.[/dim]"
)
```

**Gap analysis:**
- CLI can enable/disable plugins (runtime only)
- Config file has `plugins.<name>.enabled: bool` field
- No API to modify config file programmatically for plugin state
- Agents must resort to file manipulation to persist state

## Proposed Solutions

### Option A: Add PluginConfigManager (Recommended)
Create a dedicated manager class for plugin configuration that wraps ConfigManager.

**Pros:** Clean separation of concerns, explicit API
**Cons:** New class to maintain
**Effort:** Medium (4-6 hours)
**Risk:** Low

```python
# In src/inkwell/plugins/config.py
class PluginConfigManager:
    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager

    def set_plugin_enabled(self, name: str, enabled: bool) -> None:
        """Persist plugin enabled state to config file."""
        config = self._config.load()
        if name not in config.plugins:
            config.plugins[name] = PluginConfig(enabled=enabled)
        else:
            config.plugins[name].enabled = enabled
        self._config.save(config)

    def get_plugin_config(self, name: str) -> PluginConfig | None:
        """Get plugin configuration from config file."""
        config = self._config.load()
        return config.plugins.get(name)
```

### Option B: Add methods to existing ConfigManager
Extend ConfigManager with plugin-specific methods.

**Pros:** No new class
**Cons:** ConfigManager grows larger
**Effort:** Small (2-3 hours)
**Risk:** Low

### Option C: Add persist parameter to registry methods
Make enable/disable optionally persist to config.

**Pros:** Single call to enable + persist
**Cons:** Couples registry to config, unclear responsibility
**Effort:** Medium (3-4 hours)
**Risk:** Medium (coupling concerns)

## Recommended Action

Use Option A: Add PluginConfigManager with `set_plugin_enabled(name, enabled)` method.

## Technical Details

**Affected files:**
- New: `src/inkwell/plugins/config.py` (if Option A)
- `src/inkwell/config/manager.py` (if Option B)
- `src/inkwell/plugins/registry.py` (if Option C)
- `src/inkwell/cli_plugins.py` (update to use new API)

**Components affected:**
- Plugin configuration system
- CLI plugin commands

**Database changes:** None

## Acceptance Criteria

- [ ] Programmatic API to persist plugin enable/disable state
- [ ] State survives application restart
- [ ] CLI commands optionally use persistence API
- [ ] API is documented for agent use

## Work Log

| Date | Actor | Action | Learnings |
|------|-------|--------|-----------|
| 2026-01-06 | Agent-Native Reviewer | Identified persistence gap | Agents need parity with manual config editing |
| 2026-01-06 | Triage Session | Approved for work (pending → ready) | Agent-native parity is important |

## Resources

- PR #34: Plugin Architecture Implementation
- `src/inkwell/cli_plugins.py:259-262`
- `src/inkwell/config/schema.py:98-112` (PluginConfig model)
